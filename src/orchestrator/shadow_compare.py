"""Shadow compare orchestration utilities for solver pipelines.

This module provides sampling, execution and comparison helpers that enable
shadow runs between the primary solver implementation (``novus`` during the
rollout) and the reference ``legacy`` implementation.  The implementation
follows ADR "Shadow sampling & solved_ref" and exposes a minimal API for the
orchestrator as well as unit tests.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import socket
import statistics
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

from orchestrator.router import ResolvedModule, resolve
from ports._loader import load_module
from ports._utils import build_env


# ---------------------------------------------------------------------------
# Data structures and public surface
# ---------------------------------------------------------------------------


@dataclass
class SampleDecision:
    """Describes whether a shadow sample should be executed."""

    sampled: bool
    u64_digest_trunc: str
    hash_salt_set: bool


@dataclass
class ShadowEvent:
    """Structured shadowlog event (schema ``shadowlog/1``)."""

    payload: Dict[str, Any]


@dataclass
class ShadowState:
    """Aggregated state for the current interpreter process."""

    events: List[ShadowEvent] = field(default_factory=list)
    counters: Dict[str, int] = field(default_factory=dict)


@dataclass
class ShadowOutcome:
    """Result tuple returned by :func:`run_shadow_check`."""

    event: ShadowEvent
    counters: Dict[str, int]


_STATE = ShadowState()


# ---------------------------------------------------------------------------
# Helpers for deterministic sampling and hashing
# ---------------------------------------------------------------------------


def reset_state() -> None:
    """Reset the in-memory state (used by tests)."""

    _STATE.events.clear()
    _STATE.counters.clear()


def get_state() -> ShadowState:
    """Return a copy of the accumulated state for inspection."""

    return ShadowState(events=list(_STATE.events), counters=dict(_STATE.counters))


def _seed_to_decimal(seed: str) -> str:
    try:
        return str(int(seed, 16))
    except ValueError:
        return str(int(hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12], 16))


def compute_sample_decision(
    *,
    run_id: str,
    stage: str,
    seed: str,
    module_id: str,
    sample_rate: float,
    hash_salt: str | None,
) -> SampleDecision:
    """Decide whether to sample a run according to the deterministic policy."""

    material = "".join([
        hash_salt or "",
        run_id,
        stage,
        _seed_to_decimal(seed),
        module_id,
    ])
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    u64 = int(digest[:16], 16)
    sampled = sample_rate >= 1.0 or (sample_rate > 0 and u64 / 2**64 < sample_rate)
    return SampleDecision(sampled=sampled, u64_digest_trunc=digest[:16], hash_salt_set=bool(hash_salt))


# ---------------------------------------------------------------------------
# Git / environment fingerprint helpers
# ---------------------------------------------------------------------------


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _current_commit_sha() -> str:
    try:
        output = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=_repo_root())
    except Exception:  # pragma: no cover - defensive guard
        return "none"
    commit = output.decode().strip()
    try:
        status = subprocess.check_output(["git", "status", "--porcelain"], cwd=_repo_root())
    except Exception:  # pragma: no cover - defensive guard
        status = b""
    if status.strip():
        commit = f"{commit}+dirty"
    return commit


def _cpu_model() -> str:
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.exists():
        for line in cpuinfo.read_text().splitlines():
            if line.lower().startswith("model name"):
                return line.split(":", 1)[1].strip()
    return os.environ.get("CPU_MODEL", "unknown")


def _cpu_mhz() -> float:
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.exists():
        for line in cpuinfo.read_text().splitlines():
            if line.lower().startswith("cpu mhz"):
                try:
                    return float(line.split(":", 1)[1].strip())
                except ValueError:
                    continue
    return 0.0


def _mem_total_gb() -> float:
    meminfo = Path("/proc/meminfo")
    if meminfo.exists():
        for line in meminfo.read_text().splitlines():
            if line.lower().startswith("memtotal"):
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        kb = float(parts[1])
                        return round(kb / (1024 * 1024), 2)
                    except ValueError:
                        break
    return 0.0


def _hardware_fingerprint() -> str:
    cpu_model = _cpu_model()
    arch = os.uname().machine
    cores = os.cpu_count() or 1
    mhz = _cpu_mhz()
    mem = _mem_total_gb()
    canonical = json.dumps(
        {
            "cpu_model": cpu_model,
            "arch": arch,
            "cores": cores,
            "base_mhz": round(mhz, 2),
            "mem_gb": mem,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]


# ---------------------------------------------------------------------------
# Shadow execution helpers
# ---------------------------------------------------------------------------


def _load_solver(resolved: ResolvedModule):
    module = load_module(resolved)
    handler = getattr(module, "port_check_uniqueness")
    return handler


def _invoke_solver(
    resolved: ResolvedModule,
    spec: Dict[str, Any],
    complete: Dict[str, Any],
    options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    handler = _load_solver(resolved)
    return handler(spec, complete, options=options)


def _resolve_counterpart(
    *,
    primary: ResolvedModule,
    puzzle_kind: str,
    profile: str,
    env: Mapping[str, str],
) -> Optional[ResolvedModule]:
    counterpart = "legacy" if primary.impl_id != "legacy" else "novus"
    if counterpart == primary.impl_id:
        return None
    env_map = build_env(env)
    env_map["PUZZLE_SOLVER_IMPL"] = counterpart
    if counterpart == "legacy":
        env_map.setdefault("PUZZLE_SOLVER_STATE", "default")
    else:
        env_map.setdefault("PUZZLE_SOLVER_STATE", "shadow")
    return resolve(puzzle_kind, "solver", profile, env_map)


def _verdict_status(payload: Mapping[str, Any]) -> str | None:
    unique = payload.get("unique")
    if unique is True:
        return "ok"
    if unique is False:
        return "unsolved"
    return None


def _compare_payloads(
    primary: Mapping[str, Any],
    shadow: Mapping[str, Any],
    *,
    solved_ref_digest: str | None,
) -> Tuple[str, Dict[str, Any]]:
    """Return (category, details) for the comparison outcome."""

    primary_unique = primary.get("unique")
    shadow_unique = shadow.get("unique")
    if primary_unique != shadow_unique:
        return "C1", {
            "message": "unique flag mismatch",
            "primary_unique": primary_unique,
            "shadow_unique": shadow_unique,
        }

    if primary_unique and shadow_unique:
        p_ref = primary.get("solved_ref")
        s_ref = shadow.get("solved_ref")
        if solved_ref_digest and p_ref and s_ref and (p_ref != solved_ref_digest or s_ref != solved_ref_digest):
            return "C2", {
                "message": "solved grid reference mismatch",
                "primary_ref": p_ref,
                "shadow_ref": s_ref,
                "expected": solved_ref_digest,
            }

    return "OK", {}


def _update_counters(category: str) -> Dict[str, int]:
    counters: Dict[str, int] = {}
    if category == "OK":
        counters["shadow_ok"] = 1
    elif category.startswith("C"):
        counters[f"shadow_mismatch_{category}"] = 1
    elif category.startswith("E"):
        counters[f"shadow_error_{category}"] = 1
    elif category.startswith("M"):
        counters[f"shadow_mismatch_{category}"] = 1
    else:
        counters["shadow_info"] = 1
    for key, value in counters.items():
        _STATE.counters[key] = _STATE.counters.get(key, 0) + value
    return counters


def _compute_event_id(payload: Dict[str, Any]) -> str:
    canonical = json.dumps(
        {k: payload[k] for k in sorted(payload) if k != "event_id"},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:8]


def _deterministic_timestamp(decision: SampleDecision) -> str:
    anchor = datetime(2024, 1, 1, tzinfo=timezone.utc)
    offset_ms = int(decision.u64_digest_trunc, 16) % (24 * 60 * 60 * 1000)
    moment = anchor + timedelta(milliseconds=offset_ms)
    return moment.isoformat(timespec="milliseconds")


def _base_event(
    *,
    decision: SampleDecision,
    run_id: str,
    stage: str,
    module: ResolvedModule,
    profile: str,
    sample_rate: float,
    seed: str,
    solved_ref_digest: str | None,
    time_ms: int,
    verdict_unique: bool | None,
    verdict_status: str | None,
) -> Dict[str, Any]:
    host_id = socket.gethostname().split(".")[0]
    payload = {
        "schema_ver": "shadowlog/1",
        "ts": _deterministic_timestamp(decision),
        "profile": profile,
        "stage": stage,
        "module_id": module.module_id,
        "impl_id": module.impl_id,
        "decision_source": module.decision_source,
        "sampled": decision.sampled,
        "sample_rate": float(sample_rate),
        "hash_salt_set": decision.hash_salt_set,
        "run_id": run_id,
        "seed": seed,
        "u64_digest_trunc": decision.u64_digest_trunc,
        "verdict_unique": verdict_unique,
        "verdict_status": verdict_status,
        "category": "OK",
        "fallback_used": module.fallback_used,
        "time_ms": time_ms,
        "commit_sha": _current_commit_sha(),
        "baseline_sha": "none",
        "baseline_id": "none",
        "solved_ref_digest": solved_ref_digest or "none",
        "time_ms_baseline": None,
        "perf_delta_ms": None,
        "perf_delta_pct": None,
        "host_id": host_id,
        "cpu_info": {"model": _cpu_model()},
        "hw_fingerprint": _hardware_fingerprint(),
        "warmup_runs": None,
        "measure_runs": None,
        "details": None,
    }
    return payload


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
    options: Optional[Dict[str, Any]] = None,
) -> ShadowOutcome:
    """Execute the shadow comparison flow and record a shadowlog event."""

    decision = compute_sample_decision(
        run_id=run_id,
        stage=stage,
        seed=seed,
        module_id=module.module_id,
        sample_rate=sample_rate,
        hash_salt=hash_salt,
    )

    solved_ref_digest = complete_artifact.get("artifact_id")
    verdict_unique = primary_payload.get("unique") if isinstance(primary_payload.get("unique"), bool) else None
    verdict_status = _verdict_status(primary_payload)
    event_payload = _base_event(
        decision=decision,
        run_id=run_id,
        stage=stage,
        module=module,
        profile=profile,
        sample_rate=sample_rate,
        seed=seed,
        solved_ref_digest=solved_ref_digest,
        time_ms=primary_time_ms,
        verdict_unique=verdict_unique,
        verdict_status=verdict_status,
    )

    counters_delta: Dict[str, int]
    if not decision.sampled:
        counters_delta = _update_counters("shadow_info")
    else:
        start = time.perf_counter()
        try:
            counterpart = _resolve_counterpart(
                primary=module,
                puzzle_kind=puzzle_kind,
                profile=profile,
                env=env or {},
            )
            if counterpart is None:
                shadow_payload = dict(primary_payload)
            else:
                shadow_payload = _invoke_solver(counterpart, dict(spec_artifact), dict(complete_artifact), options=options)
        except Exception as exc:  # pragma: no cover - exercised via dedicated tests
            duration_ms = int((time.perf_counter() - start) * 1000)
            event_payload["category"] = "E1"
            event_payload["details"] = {
                "error": type(exc).__name__,
                "message": str(exc),
            }
            event_payload["time_ms"] = primary_time_ms
            event_payload["perf_delta_ms"] = duration_ms
            counters_delta = _update_counters("E1")
        else:
            duration_ms = int((time.perf_counter() - start) * 1000)
            category, details = _compare_payloads(
                primary_payload,
                shadow_payload,
                solved_ref_digest=solved_ref_digest,
            )
            event_payload["category"] = category
            event_payload["details"] = details or None
            event_payload["perf_delta_ms"] = duration_ms
            event_payload["perf_delta_pct"] = None
            counters_delta = _update_counters(category)

    event_payload["event_id"] = _compute_event_id(event_payload)
    event = ShadowEvent(payload=event_payload)
    _STATE.events.append(event)
    return ShadowOutcome(event=event, counters=counters_delta)


# ---------------------------------------------------------------------------
# Performance micro-benchmark helpers (I2 scenario)
# ---------------------------------------------------------------------------


@dataclass
class PerfCase:
    name: str
    grid: str
    difficulty: str


@dataclass
class PerfMetrics:
    name: str
    median_ms: float
    samples: List[float]


def _run_solver_case(grid: str, spec: Mapping[str, Any]) -> None:
    module_env = {"grid": grid, "artifact_id": "sha256-dummy"}
    from sudoku_solver import port_check_uniqueness

    port_check_uniqueness(spec, module_env)


def _ensure_affinity() -> None:
    try:
        os.sched_setaffinity(0, {0})
    except AttributeError:  # pragma: no cover - unsupported platform
        pass
    except PermissionError:  # pragma: no cover - containers without CAP_SYS_NICE
        pass


def _spec_payload() -> Dict[str, Any]:
    return {
        "name": "sudoku-9x9",
        "size": 9,
        "block": {"rows": 3, "cols": 3},
        "alphabet": list("123456789"),
        "limits": {"solver_timeout_ms": 1000},
    }


def run_perf_benchmark(
    cases: Iterable[PerfCase],
    *,
    warmup_runs: int = 1,
    measure_runs: int = 3,
) -> List[PerfMetrics]:
    """Execute a deterministic micro-benchmark over the provided cases."""

    _ensure_affinity()
    spec = _spec_payload()
    metrics: List[PerfMetrics] = []
    for case in cases:
        for _ in range(warmup_runs):
            _run_solver_case(case.grid, spec)
        samples: List[float] = []
        for _ in range(measure_runs):
            start = time.perf_counter()
            _run_solver_case(case.grid, spec)
            samples.append((time.perf_counter() - start) * 1000)
        median_value = statistics.median(samples)
        metrics.append(PerfMetrics(name=case.name, median_ms=median_value, samples=samples))
    return metrics


def write_perf_reports(
    *,
    metrics: List[PerfMetrics],
    output_dir: Path,
    warmup_runs: int,
    measure_runs: int,
) -> Tuple[Path, Path]:
    """Write JSON and Markdown summaries for the benchmark results."""

    output_dir.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "name": metric.name,
            "median_ms": round(metric.median_ms, 4),
            "samples_ms": [round(sample, 4) for sample in metric.samples],
        }
        for metric in metrics
    ]
    meta = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "commit_sha": _current_commit_sha(),
        "hw_fingerprint": _hardware_fingerprint(),
        "warmup_runs": warmup_runs,
        "measure_runs": measure_runs,
    }
    json_payload = {"meta": meta, "cases": rows}
    json_path = output_dir / "perf_i2_dev.json"
    json_path.write_text(json.dumps(json_payload, indent=2))

    md_lines = ["# I2 microbenchmark (dev)", "", "| Case | Median (ms) | Samples (ms) |", "| --- | ---: | --- |"]
    for row in rows:
        samples = ", ".join(f"{value:.4f}" for value in row["samples_ms"])
        md_lines.append(f"| {row['name']} | {row['median_ms']:.4f} | {samples} |")
    md_path = output_dir / "perf_i2_dev.md"
    md_path.write_text("\n".join(md_lines) + "\n")
    return json_path, md_path


__all__ = [
    "SampleDecision",
    "ShadowOutcome",
    "ShadowEvent",
    "ShadowState",
    "compute_sample_decision",
    "get_state",
    "reset_state",
    "run_shadow_check",
    "PerfCase",
    "PerfMetrics",
    "run_perf_benchmark",
    "write_perf_reports",
]

