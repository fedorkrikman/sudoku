"""Measure shadow overhead against guardrails and persist rolling baselines."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import sys
import time
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[2]

if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from orchestrator import orchestrator


_REPORT_DIR = ROOT / "reports" / "overhead"
_BASELINE_TTL_DAYS = 14


@dataclass
class Sample:
    seed: str
    base_ms: float
    shadow_ms: float

    @property
    def delta_ms(self) -> float:
        return self.shadow_ms - self.base_ms

    @property
    def ratio(self) -> float:
        if self.base_ms <= 0:
            return 0.0
        return self.shadow_ms / self.base_ms


def _read_seeds(path: Path) -> List[str]:
    seeds = [line.strip() for line in path.read_text("utf-8").splitlines() if line.strip()]
    if not seeds:
        raise ValueError(f"seeds file '{path}' is empty")
    return seeds


def _percentile(values: Sequence[float], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = (len(ordered) - 1) * quantile
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return ordered[int(index)]
    fraction = index - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def _median(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def _perf_counter_ms() -> float:
    return time.perf_counter_ns() / 1_000_000


def _run_pipeline(seed: str, profile: str, *, shadow_enabled: bool, sample_rate: float) -> float:
    overrides = {
        "PUZZLE_ROOT_SEED": seed,
        "PUZZLE_VALIDATION_PROFILE": profile,
        "CLI_SHADOW_ENABLED": "1" if shadow_enabled else "0",
        "CLI_SHADOW_SAMPLE_RATE": f"{sample_rate:.8f}",
    }
    start_ms = _perf_counter_ms()
    orchestrator.run_pipeline(env_overrides=overrides)
    return _perf_counter_ms() - start_ms


def _current_commit_sha() -> str:
    git_dir = ROOT / ".git"
    head_path = git_dir / "HEAD"
    try:
        head = head_path.read_text("utf-8").strip()
    except OSError:
        return "0" * 40
    if head.startswith("ref:"):
        ref_path = git_dir / head.split(None, 1)[1]
        try:
            return ref_path.read_text("utf-8").strip()[:40]
        except OSError:
            return "0" * 40
    return head[:40]


def _hardware_fingerprint() -> str:
    payload = "|".join(str(part) for part in platform.uname())
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _collect_samples(
    seeds: Sequence[str],
    profile: str,
    warmup: int,
    samples: int,
) -> List[Sample]:
    if warmup + samples > len(seeds):
        raise ValueError(
            f"requested warmup+samples={warmup + samples} but file only provides {len(seeds)} seeds"
        )

    collected: List[Sample] = []
    for index, seed in enumerate(seeds):
        if index < warmup:
            _run_pipeline(seed, profile, shadow_enabled=False, sample_rate=0.0)
            _run_pipeline(seed, profile, shadow_enabled=True, sample_rate=1.0)
            continue
        if len(collected) >= samples:
            break
        base_ms = _run_pipeline(seed, profile, shadow_enabled=False, sample_rate=0.0)
        shadow_ms = _run_pipeline(seed, profile, shadow_enabled=True, sample_rate=1.0)
        collected.append(Sample(seed=seed, base_ms=base_ms, shadow_ms=shadow_ms))
    return collected


def _summarise(values: Sequence[float]) -> Dict[str, float]:
    return {
        "p50": round(_percentile(values, 0.50), 3),
        "p95": round(_percentile(values, 0.95), 3),
        "p99": round(_percentile(values, 0.99), 3),
    }


def _update_baseline(
    *,
    path: Path,
    commit_sha: str,
    hw_fingerprint: str,
    profile: str,
    current: Mapping[str, Mapping[str, float]],
) -> Mapping[str, object]:
    runs: List[Mapping[str, object]] = []
    if path.exists():
        try:
            payload = json.loads(path.read_text("utf-8"))
            runs = list(payload.get("runs", []))
        except (OSError, json.JSONDecodeError):
            runs = []

    cutoff = datetime.now(timezone.utc).timestamp() - _BASELINE_TTL_DAYS * 86400
    filtered: List[Mapping[str, object]] = []
    for entry in runs:
        ts_str = entry.get("ts")
        try:
            ts_value = datetime.fromisoformat(str(ts_str))
        except ValueError:
            continue
        if ts_value.timestamp() >= cutoff:
            filtered.append(entry)

    enriched_entry: Dict[str, object] = {
        "ts": _now_iso(),
        "base_ms": current["base_ms"],
        "shadow_ms": current["shadow_ms"],
        "delta_ms": current["delta_ms"],
        "ratio": current["ratio"],
    }
    filtered.append(enriched_entry)

    baseline_summary: Dict[str, object] | None = None
    if len(filtered) >= 5:
        def aggregate(key: str, percentile: str) -> float:
            values = [float(entry[key][percentile]) for entry in filtered]
            return round(_median(values), 3)

        baseline_summary = {
            "base_ms": {k: aggregate("base_ms", k) for k in ("p50", "p95", "p99")},
            "shadow_ms": {k: aggregate("shadow_ms", k) for k in ("p50", "p95", "p99")},
            "delta_ms": {k: aggregate("delta_ms", k) for k in ("p50", "p95", "p99")},
            "ratio": {k: aggregate("ratio", k) for k in ("p50", "p95", "p99")},
            "runs": len(filtered),
        }

    payload: Dict[str, object] = {
        "commit_sha": commit_sha,
        "hw_fingerprint": hw_fingerprint,
        "profile": profile,
        "ttl_days": _BASELINE_TTL_DAYS,
        "runs": filtered,
    }
    if baseline_summary is not None:
        payload["baseline"] = baseline_summary

    path.parent.mkdir(parents=True, exist_ok=True)
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    path.write_text(canonical + "\n", encoding="utf-8")

    return baseline_summary or {}


def _write_report(payload: Dict[str, object], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    path.write_text(canonical + "\n", encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default="dev", help="Validation profile")
    parser.add_argument("--seeds-file", type=Path, required=True, help="Path to seeds file")
    parser.add_argument("--warmup", type=int, default=10, help="Number of warmup seeds")
    parser.add_argument("--samples", type=int, default=300, help="Number of measured samples")
    parser.add_argument("--budget-ms-p95", type=float, default=50.0, help="p95 delta budget in ms")
    parser.add_argument("--ratio-p95", type=float, default=1.05, help="p95 ratio budget")
    parser.add_argument("--report", type=Path, default=ROOT / "reports" / "overhead" / "report.json", help="Report path")
    args = parser.parse_args(argv)

    seeds = _read_seeds(args.seeds_file)
    samples = _collect_samples(seeds, args.profile, args.warmup, args.samples)

    base_values = [sample.base_ms for sample in samples]
    shadow_values = [sample.shadow_ms for sample in samples]
    deltas = [sample.delta_ms for sample in samples]
    ratios = [sample.ratio for sample in samples]

    base_summary = _summarise(base_values)
    shadow_summary = _summarise(shadow_values)
    delta_summary = _summarise(deltas)
    ratio_summary = {
        "p50": round(_percentile(ratios, 0.50), 5),
        "p95": round(_percentile(ratios, 0.95), 5),
        "p99": round(_percentile(ratios, 0.99), 5),
    }

    delta_p95 = delta_summary["p95"]
    ratio_p95 = ratio_summary["p95"]

    commit_sha = _current_commit_sha()
    hw_fingerprint = _hardware_fingerprint()

    measurements: Dict[str, Mapping[str, float]] = {
        "base_ms": base_summary,
        "shadow_ms": shadow_summary,
        "delta_ms": delta_summary,
        "ratio": ratio_summary,
    }

    report: Dict[str, object] = {
        "profile": args.profile,
        "warmup": args.warmup,
        "samples": len(samples),
        "commit_sha": commit_sha,
        "hw_fingerprint": hw_fingerprint,
        "base_ms": base_summary,
        "shadow_ms": shadow_summary,
        "delta_ms": delta_summary,
        "ratio": ratio_summary,
        "budget_ms_p95": args.budget_ms_p95,
        "ratio_p95_limit": args.ratio_p95,
        "top_deltas": [
            {
                "seed": sample.seed,
                "delta_ms": round(sample.delta_ms, 3),
                "base_ms": round(sample.base_ms, 3),
                "shadow_ms": round(sample.shadow_ms, 3),
            }
            for sample in sorted(samples, key=lambda s: s.delta_ms, reverse=True)[:10]
        ],
    }
    passed = delta_p95 <= args.budget_ms_p95 and ratio_p95 <= args.ratio_p95
    report["passed"] = passed

    baseline_path = _REPORT_DIR / f"baseline_{commit_sha}_{hw_fingerprint}_{args.profile}.json"
    baseline_summary = _update_baseline(
        path=baseline_path,
        commit_sha=commit_sha,
        hw_fingerprint=hw_fingerprint,
        profile=args.profile,
        current=measurements,
    )
    if baseline_summary:
        report["baseline_path"] = str(baseline_path)
        report["baseline"] = baseline_summary

    _write_report(report, args.report)

    status = "PASS" if report["passed"] else "FAIL"
    print(
        f"Shadow overhead {status}: p95_delta={round(delta_p95, 3)} "
        f"p95_ratio={round(ratio_p95, 5)} samples={len(samples)}"
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
