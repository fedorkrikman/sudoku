"""Shadow comparison runtime helpers."""

from __future__ import annotations

import hashlib
import platform
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, MutableMapping, Tuple

from contracts.envelope import Envelope, envelope_to_dict, make_envelope
from contracts.jsoncanon import jcs_sha256

from . import log, sampling
from .router import ResolvedModule, resolve
from ports._loader import load_module
from ports._utils import build_env

__all__ = [
    "ShadowRun",
    "ShadowTask",
    "ShadowResult",
    "GuardrailContext",
    "classify_mismatch",
    "run_with_shadow",
    "run_shadow_check",
    "ShadowOutcome",
    "ShadowEvent",
]


@dataclass(frozen=True)
class ShadowRun:
    verdict: str
    result_artifact: Any
    metrics: Mapping[str, Any] | None = None
    extra: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class GuardrailContext:
    severity: str
    kind: str
    timings: Mapping[str, float]
    overhead_pct: float


@dataclass(frozen=True)
class ShadowTask:
    envelope: Envelope
    run_id: str
    stage: str
    seed: str
    module_id: str
    profile: str
    sample_rate: float
    hash_salt: str | None
    baseline_runner: Callable[[], ShadowRun]
    candidate_runner: Callable[[], ShadowRun]
    guardrail: Callable[[GuardrailContext], bool] | None = None
    classifier: Callable[[ShadowRun, ShadowRun], Tuple[str, str]] | None = None
    metadata: Mapping[str, Any] | None = None
    allow_fallback: bool = True
    primary_impl: str = "legacy"
    secondary_impl: str = "novus"
    log_mismatch: bool = True


@dataclass(frozen=True)
class ShadowResult:
    sampled: bool
    severity: str
    kind: str
    baseline_digest: str | None
    candidate_digest: str
    returned: ShadowRun
    baseline: ShadowRun | None
    candidate: ShadowRun
    fallback_used: bool
    event_path: Path | None
    timings: Mapping[str, float]
    event: Mapping[str, Any]


@dataclass(frozen=True)
class ShadowEvent:
    payload: Mapping[str, Any]


@dataclass(frozen=True)
class ShadowOutcome:
    event: ShadowEvent
    counters: Mapping[str, int]


@lru_cache(maxsize=1)
def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


@lru_cache(maxsize=1)
def _current_commit_sha() -> str:
    git_dir = _project_root() / ".git"
    head_path = git_dir / "HEAD"
    try:
        head = head_path.read_text("utf-8").strip()
    except OSError:
        return "unknown"
    if head.startswith("ref:"):
        ref = head.split(None, 1)[1]
        ref_path = git_dir / ref
        try:
            return ref_path.read_text("utf-8").strip()[:40]
        except OSError:
            return "unknown"
    return head[:40]


@lru_cache(maxsize=1)
def _hardware_fingerprint() -> str:
    payload = "|".join(str(part) for part in platform.uname())
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return digest[:16]


def _deterministic_timestamp(run_id: str, stage: str) -> str:
    anchor = datetime(2023, 1, 1, tzinfo=timezone.utc)
    material = f"shadow|{run_id}|{stage}"
    offset_ms = uuid.uuid5(uuid.NAMESPACE_OID, material).int % (24 * 60 * 60 * 1000)
    moment = anchor + timedelta(milliseconds=offset_ms)
    return moment.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _extract_solved_ref(payload: Mapping[str, Any]) -> str | None:
    candidate = payload.get("solved_ref")
    if isinstance(candidate, str) and candidate:
        return candidate
    return None


def _build_shadow_event(
    *,
    task: ShadowTask,
    severity: str,
    kind: str,
    timings: Mapping[str, float],
    baseline: ShadowRun,
    candidate: ShadowRun,
) -> Mapping[str, Any]:
    status = "match" if severity == "NONE" else "mismatch"
    event_type = "sudoku.shadow_mismatch.v1" if severity != "NONE" else "sudoku.shadow_sample.v1"
    metadata = task.metadata or {}
    puzzle_digest = metadata.get("puzzle_digest")
    baseline_sha = metadata.get("baseline_sha") or metadata.get("commit_sha") or _current_commit_sha()
    commit_sha = metadata.get("commit_sha") or _current_commit_sha()
    hw_fp = metadata.get("hw_fingerprint") or _hardware_fingerprint()
    solved_ref = _extract_solved_ref(candidate.result_artifact)
    if solved_ref is None and baseline.result_artifact:
        solved_ref = _extract_solved_ref(baseline.result_artifact)
    diff_summary = "none" if severity == "NONE" else f"{kind}:{severity}"

    return {
        "type": event_type,
        "run_id": task.run_id,
        "ts_iso8601": _deterministic_timestamp(task.run_id, task.stage),
        "commit_sha": commit_sha,
        "baseline_sha": baseline_sha,
        "hw_fingerprint": hw_fp,
        "profile": task.profile,
        "puzzle_digest": puzzle_digest,
        "solver_primary": task.primary_impl,
        "solver_shadow": task.secondary_impl,
        "verdict_status": status,
        "time_ms_primary": round(float(timings.get("candidate_ms", 0.0)), 3),
        "time_ms_shadow": round(float(timings.get("baseline_ms", 0.0)), 3),
        "diff_summary": diff_summary,
        "solved_ref_digest": solved_ref,
    }
def _execute_runner(runner: Callable[[], ShadowRun]) -> tuple[ShadowRun, float]:
    start = time.perf_counter()
    result = runner()
    duration_ms = (time.perf_counter() - start) * 1000
    return result, duration_ms


def _load_solver(resolved: ResolvedModule):
    module = load_module(resolved)
    handler = getattr(module, "port_check_uniqueness")
    return handler


def _invoke_solver(
    resolved: ResolvedModule,
    spec: Mapping[str, Any],
    complete: Mapping[str, Any],
    *,
    options: Mapping[str, Any] | None = None,
) -> Mapping[str, Any]:
    handler = _load_solver(resolved)
    return handler(dict(spec), dict(complete), options=options)


def _resolve_counterpart(
    *,
    primary: ResolvedModule,
    puzzle_kind: str,
    profile: str,
    env: Mapping[str, str],
) -> ResolvedModule | None:
    counterpart_impl = "legacy" if primary.impl_id != "legacy" else "novus"
    if counterpart_impl == primary.impl_id:
        return None
    env_map = build_env(env)
    env_map["PUZZLE_SOLVER_IMPL"] = counterpart_impl
    env_map.setdefault("PUZZLE_SOLVER_STATE", "shadow")
    return resolve(puzzle_kind, "solver", profile, env_map)


def classify_mismatch(baseline: ShadowRun, candidate: ShadowRun) -> tuple[str, str]:
    if baseline.verdict != candidate.verdict:
        return "nondeterminism", "CRITICAL"

    if baseline.result_artifact == candidate.result_artifact:
        return "none", "NONE"

    base_payload = baseline.result_artifact
    cand_payload = candidate.result_artifact

    if isinstance(base_payload, Mapping) and isinstance(cand_payload, Mapping):
        base_core = {k: v for k, v in base_payload.items() if k != "trace"}
        cand_core = {k: v for k, v in cand_payload.items() if k != "trace"}
        if base_core == cand_core:
            return "none", "NONE"
        if base_payload.get("grid") != cand_payload.get("grid"):
            return "value", "CRITICAL"
        if base_payload.get("candidates") != cand_payload.get("candidates"):
            return "candidates", "MAJOR"
        return "trace", "MINOR"

    return "value", "MAJOR"


def _build_event(
    *,
    task: ShadowTask,
    severity: str,
    kind: str,
    baseline: ShadowRun,
    candidate: ShadowRun,
    baseline_digest: str,
    candidate_digest: str,
    timings: Mapping[str, float],
) -> Mapping[str, Any]:
    payload: MutableMapping[str, Any] = {
        "event": "shadow_compare.completed",
        "envelope": envelope_to_dict(task.envelope),
        "run_id": task.run_id,
        "stage": task.stage,
        "seed": task.seed,
        "module_id": task.module_id,
        "profile": task.profile,
        "sample_rate": task.sample_rate,
        "severity": severity,
        "kind": kind,
        "digests": {
            "baseline": baseline_digest,
            "candidate": candidate_digest,
        },
        "verdict": {
            "baseline": baseline.verdict,
            "candidate": candidate.verdict,
        },
        "timings": {
            "baseline_ms": round(timings.get("baseline_ms", 0.0), 3),
            "candidate_ms": round(timings.get("candidate_ms", 0.0), 3),
            "delta_ms": round(timings.get("delta_ms", 0.0), 3),
            "overhead_pct": round(timings.get("overhead_pct", 0.0), 5),
        },
    }
    if task.metadata:
        payload["metadata"] = dict(task.metadata)
    return payload


def run_with_shadow(task: ShadowTask) -> ShadowResult:
    candidate, cand_ms = _execute_runner(task.candidate_runner)
    candidate_digest = jcs_sha256(candidate.result_artifact)

    sampled = sampling.hit(
        task.hash_salt,
        task.run_id,
        task.stage,
        task.seed,
        task.module_id,
        task.sample_rate,
    )

    if not sampled:
        timings = {"candidate_ms": cand_ms, "baseline_ms": 0.0, "delta_ms": cand_ms, "overhead_pct": 0.0}
        event_payload: Mapping[str, Any] = {
            "event": "shadow_compare.skipped",
            "run_id": task.run_id,
            "stage": task.stage,
            "seed": task.seed,
            "module_id": task.module_id,
            "profile": task.profile,
            "sample_rate": task.sample_rate,
            "severity": "NONE",
            "kind": "none",
            "sampled": False,
            "digests": {"baseline": None, "candidate": candidate_digest},
            "timings": timings,
        }
        return ShadowResult(
            sampled=False,
            severity="NONE",
            kind="none",
            baseline_digest=None,
            candidate_digest=candidate_digest,
            returned=candidate,
            baseline=None,
            candidate=candidate,
            fallback_used=False,
            event_path=None,
            timings=timings,
            event=event_payload,
        )

    baseline, base_ms = _execute_runner(task.baseline_runner)
    baseline_digest = jcs_sha256(baseline.result_artifact)

    classifier = task.classifier or classify_mismatch
    kind, severity = classifier(baseline, candidate)

    delta_ms = cand_ms - base_ms
    overhead_pct = 0.0 if base_ms <= 0 else delta_ms / base_ms
    timings = {
        "baseline_ms": base_ms,
        "candidate_ms": cand_ms,
        "delta_ms": delta_ms,
        "overhead_pct": overhead_pct,
    }

    event_payload = _build_shadow_event(
        task=task,
        severity=severity,
        kind=kind,
        timings=timings,
        baseline=baseline,
        candidate=candidate,
    )
    event_path: Path | None = None
    if severity != "NONE" and task.log_mismatch:
        event_path = log.append_event(event_payload)

    fallback = False
    if task.guardrail is not None:
        fallback = task.guardrail(GuardrailContext(severity=severity, kind=kind, timings=timings, overhead_pct=overhead_pct))
    elif severity == "CRITICAL" and task.allow_fallback:
        fallback = True

    returned = baseline if fallback else candidate

    return ShadowResult(
        sampled=True,
        severity=severity,
        kind=kind,
        baseline_digest=baseline_digest,
        candidate_digest=candidate_digest,
        returned=returned,
        baseline=baseline,
        candidate=candidate,
        fallback_used=fallback,
        event_path=event_path,
        timings=timings,
        event=event_payload,
    )


def _verdict_from_payload(payload: Mapping[str, Any]) -> str:
    unique = payload.get("unique")
    if unique is True:
        return "ok"
    if unique is False:
        return "unsolved"
    return "unknown"


def run_shadow_check(
    *,
    puzzle_kind: str,
    run_id: str,
    stage: str,
    seed: str,
    profile: str,
    module: ResolvedModule,
    sample_rate: float,
    hash_salt: str | None,
    spec_artifact: Mapping[str, Any],
    complete_artifact: Mapping[str, Any],
    primary_payload: Mapping[str, Any],
    primary_time_ms: int,
    env: Mapping[str, str] | None = None,
    options: Mapping[str, Any] | None = None,
    shadow_config: Mapping[str, Any] | None = None,
) -> ShadowOutcome:
    env = env or {}
    shadow_config = shadow_config or {}

    candidate_run = ShadowRun(
        verdict=_verdict_from_payload(primary_payload),
        result_artifact=dict(primary_payload),
        metrics={"time_ms": primary_time_ms},
    )

    def candidate_runner() -> ShadowRun:
        return candidate_run

    def baseline_runner() -> ShadowRun:
        counterpart = _resolve_counterpart(
            primary=module,
            puzzle_kind=puzzle_kind,
            profile=profile,
            env=env,
        )
        if counterpart is None:
            return candidate_run
        payload = _invoke_solver(counterpart, spec_artifact, complete_artifact, options=options)
        return ShadowRun(verdict=_verdict_from_payload(payload), result_artifact=payload)

    envelope = make_envelope(
        profile=profile,
        solver_id=module.module_id,
        commit_sha=_current_commit_sha(),
        baseline_sha=None,
        run_id=run_id,
    )

    puzzle_digest: str | None = None
    if isinstance(complete_artifact, Mapping):
        digest_candidate = complete_artifact.get("artifact_id")
        if isinstance(digest_candidate, str) and digest_candidate:
            puzzle_digest = digest_candidate
        else:
            puzzle_digest = jcs_sha256(dict(complete_artifact))

    metadata: Dict[str, Any] = {
        "puzzle_kind": puzzle_kind,
        "puzzle_digest": puzzle_digest,
        "commit_sha": _current_commit_sha(),
        "baseline_sha": shadow_config.get("baseline_sha"),
    }

    task = ShadowTask(
        envelope=envelope,
        run_id=run_id,
        stage=stage,
        seed=seed,
        module_id=module.module_id,
        profile=profile,
        sample_rate=sample_rate,
        hash_salt=hash_salt,
        baseline_runner=baseline_runner,
        candidate_runner=candidate_runner,
        metadata=metadata,
        allow_fallback=module.allow_fallback,
        primary_impl=module.impl_id,
        secondary_impl=str(shadow_config.get("secondary", "novus")),
        log_mismatch=bool(shadow_config.get("log_mismatch", True)),
    )

    result = run_with_shadow(task)

    counters: MutableMapping[str, int] = {}
    if not result.sampled:
        counters["shadow_skipped"] = 1
    elif result.severity == "NONE":
        counters["shadow_ok"] = 1
    else:
        counters[f"shadow_{result.severity.lower()}_{result.kind}"] = 1

    return ShadowOutcome(event=ShadowEvent(payload=result.event), counters=counters)
