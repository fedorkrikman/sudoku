"""Shadow comparison runtime helpers."""

from __future__ import annotations

import hashlib
import platform
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Mapping, MutableMapping, Tuple

from contracts.envelope import Envelope, envelope_to_dict, make_envelope
from contracts.jsoncanon import jcs_dump, jcs_sha256

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
    sample_rate: Decimal
    sample_rate_str: str
    hash_salt: str | None
    baseline_runner: Callable[[], ShadowRun]
    candidate_runner: Callable[[], ShadowRun]
    sticky: bool = False
    guardrail: Callable[[GuardrailContext], bool] | None = None
    classifier: Callable[[ShadowRun, ShadowRun], Tuple[str, str]] | None = None
    metadata: Mapping[str, Any] | None = None
    allow_fallback: bool = True
    primary_impl: str = "legacy"
    secondary_impl: str = "novus"
    log_mismatch: bool = True
    complete_artifact: Mapping[str, Any] | None = None


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


def _canonical_digest(obj: Any) -> str:
    return hashlib.sha256(jcs_dump(obj)).hexdigest()


def _solve_trace_digest(payload: Mapping[str, Any] | None) -> str:
    trace: Any = {}
    if isinstance(payload, Mapping):
        trace = payload.get("trace", {})
    return _canonical_digest(trace)


def _envelope_digest(envelope: Envelope) -> str:
    return _canonical_digest(envelope_to_dict(envelope))


def _string_to_digits(value: str) -> list[int]:
    digits: list[int] = []
    for char in value:
        if char.isdigit():
            digits.append(int(char))
        elif char == ".":
            digits.append(0)
        if len(digits) == 81:
            break
    return digits


def _grid_from_source(source: Any) -> list[int] | None:
    if isinstance(source, str):
        digits = _string_to_digits(source)
        if len(digits) == 81:
            return digits
        return None
    if isinstance(source, Iterable) and not isinstance(source, (bytes, bytearray, str, Mapping)):
        digits: list[int] = []
        for item in source:
            if isinstance(item, str):
                digits.extend(_string_to_digits(item))
            elif isinstance(item, (int, float)):
                digits.append(int(item))
            if len(digits) >= 81:
                break
        if len(digits) >= 81:
            return digits[:81]
    return None


def _extract_grid_digits(
    payload: Mapping[str, Any] | None,
    complete_artifact: Mapping[str, Any] | None,
) -> list[int]:
    sources: list[Any] = []
    if isinstance(payload, Mapping):
        sources.append(payload.get("grid"))
    if isinstance(complete_artifact, Mapping):
        sources.append(complete_artifact.get("grid"))
    for source in sources:
        digits = _grid_from_source(source)
        if digits is not None:
            padded = digits + [0] * max(0, 81 - len(digits))
            return padded[:81]
    return [0] * 81


def _index_from_label(label: Any) -> int | None:
    if isinstance(label, int):
        if 0 <= label < 81:
            return label
        return None
    if isinstance(label, str):
        stripped = label.strip().lower()
        if stripped.isdigit():
            idx = int(stripped)
            if 0 <= idx < 81:
                return idx
        if stripped.startswith("r") and "c" in stripped:
            try:
                row_str, col_str = stripped[1:].split("c", 1)
            except ValueError:
                return None
            if row_str.isdigit() and col_str.isdigit():
                row = int(row_str) - 1
                col = int(col_str) - 1
                if 0 <= row < 9 and 0 <= col < 9:
                    return row * 9 + col
    return None


def _iter_candidate_digits(values: Any) -> Iterable[int]:
    if isinstance(values, str):
        for char in values:
            if char.isdigit():
                yield int(char)
    elif isinstance(values, Iterable) and not isinstance(values, (bytes, bytearray, str, Mapping)):
        for item in values:
            yield from _iter_candidate_digits(item)
    else:
        try:
            number = int(values)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return
        else:
            yield number


def _candidate_matrix(payload: Mapping[str, Any] | None) -> list[list[int]] | None:
    if not isinstance(payload, Mapping):
        return None
    raw = payload.get("candidates")
    if raw is None:
        return None

    matrix: list[list[int]] = [[0] * 9 for _ in range(81)]
    applied = False

    def apply(idx: int, values: Any) -> None:
        nonlocal applied
        if not (0 <= idx < 81):
            return
        cell = matrix[idx]
        for digit in _iter_candidate_digits(values):
            if 1 <= digit <= 9:
                cell[digit - 1] = 1
                applied = True

    if isinstance(raw, Mapping):
        for key, values in raw.items():
            idx = _index_from_label(key)
            if idx is None:
                continue
            apply(idx, values)
    elif isinstance(raw, Iterable) and not isinstance(raw, (bytes, bytearray, str)):
        entries = list(raw)
        if len(entries) == 81:
            for idx, values in enumerate(entries):
                apply(idx, values)
    else:
        return None

    return matrix if applied else None


def _state_hash_digest(
    payload: Mapping[str, Any] | None,
    complete_artifact: Mapping[str, Any] | None,
) -> str:
    digits = _extract_grid_digits(payload, complete_artifact)
    matrix = _candidate_matrix(payload)
    if matrix is None:
        matrix = [[0] * 9 for _ in range(81)]
        for idx, digit in enumerate(digits[:81]):
            if 1 <= digit <= 9:
                matrix[idx][digit - 1] = 1

    flags = [value for row in matrix for value in row]
    if len(flags) < 81 * 9:
        flags.extend([0] * (81 * 9 - len(flags)))
    elif len(flags) > 81 * 9:
        flags = flags[: 81 * 9]

    grid_bytes = bytes(max(0, min(9, int(digit))) for digit in digits[:81])
    candidate_bytes = bytes(flags)
    return hashlib.sha256(candidate_bytes + grid_bytes).hexdigest()


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
        "sample_rate": task.sample_rate_str,
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

    metadata = task.metadata or {}
    puzzle_digest = metadata.get("puzzle_digest")
    puzzle_digest_str = puzzle_digest if isinstance(puzzle_digest, str) else None

    solve_trace_digest = _solve_trace_digest(
        candidate.result_artifact if isinstance(candidate.result_artifact, Mapping) else None
    )
    state_hash_digest = _state_hash_digest(
        candidate.result_artifact if isinstance(candidate.result_artifact, Mapping) else None,
        task.complete_artifact,
    )
    envelope_digest = _envelope_digest(task.envelope)

    sampled = sampling.hit(
        hash_salt=task.hash_salt,
        run_id=task.run_id,
        puzzle_digest=puzzle_digest_str,
        rate=task.sample_rate,
        sticky=task.sticky,
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
            "sample_rate": task.sample_rate_str,
            "severity": "NONE",
            "kind": "none",
            "sampled": False,
            "digests": {"baseline": None, "candidate": candidate_digest},
            "timings": timings,
        }
        if puzzle_digest_str:
            event_payload = {**event_payload, "puzzle_digest": puzzle_digest_str}
        event_payload = {
            **event_payload,
            "solve_trace_sha256": solve_trace_digest,
            "state_hash_sha256": state_hash_digest,
            "envelope_jcs_sha256": envelope_digest,
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
    if puzzle_digest_str:
        event_payload = {**event_payload, "puzzle_digest": puzzle_digest_str}
    event_payload = {
        **event_payload,
        "sample_rate": task.sample_rate_str,
        "solve_trace_sha256": solve_trace_digest,
        "state_hash_sha256": state_hash_digest,
        "envelope_jcs_sha256": envelope_digest,
    }
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
    sample_rate: Decimal,
    sample_rate_str: str,
    hash_salt: str | None,
    sticky: bool,
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
            puzzle_digest = digest_candidate.split("-", 1)[1] if digest_candidate.startswith("sha256-") else digest_candidate
        else:
            fallback_digest = jcs_sha256(dict(complete_artifact))
            puzzle_digest = fallback_digest.split("-", 1)[1]

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
        sample_rate_str=sample_rate_str,
        hash_salt=hash_salt,
        sticky=sticky,
        baseline_runner=baseline_runner,
        candidate_runner=candidate_runner,
        metadata=metadata,
        allow_fallback=module.allow_fallback,
        primary_impl=module.impl_id,
        secondary_impl=str(shadow_config.get("secondary", "novus")),
        log_mismatch=bool(shadow_config.get("log_mismatch", True)),
        complete_artifact=complete_artifact,
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
