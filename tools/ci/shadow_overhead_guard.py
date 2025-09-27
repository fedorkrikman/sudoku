"""Measure shadow overhead against guardrails (delta and ratio percentiles)."""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence

ROOT = Path(__file__).resolve().parents[2]

if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from orchestrator import orchestrator


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


def _run_pipeline(seed: str, profile: str, *, shadow_enabled: bool, sample_rate: float) -> float:
    overrides = {
        "PUZZLE_ROOT_SEED": seed,
        "PUZZLE_VALIDATION_PROFILE": profile,
        "CLI_SHADOW_ENABLED": "1" if shadow_enabled else "0",
        "CLI_SHADOW_SAMPLE_RATE": f"{sample_rate:.8f}",
    }
    start = time.perf_counter()
    orchestrator.run_pipeline(env_overrides=overrides)
    return (time.perf_counter() - start) * 1000


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

    deltas = [sample.delta_ms for sample in samples]
    ratios = [sample.ratio for sample in samples]

    delta_p95 = _percentile(deltas, 0.95)
    ratio_p95 = _percentile(ratios, 0.95)

    report = {
        "profile": args.profile,
        "warmup": args.warmup,
        "samples": len(samples),
        "delta_ms": {
            "p50": round(_percentile(deltas, 0.50), 3),
            "p95": round(delta_p95, 3),
            "p99": round(_percentile(deltas, 0.99), 3),
        },
        "ratio": {
            "p50": round(_percentile(ratios, 0.50), 5),
            "p95": round(ratio_p95, 5),
            "p99": round(_percentile(ratios, 0.99), 5),
        },
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
    report["passed"] = delta_p95 <= args.budget_ms_p95 and ratio_p95 <= args.ratio_p95

    _write_report(report, args.report)

    status = "PASS" if report["passed"] else "FAIL"
    print(
        f"Shadow overhead {status}: p95_delta={round(delta_p95, 3)} "
        f"p95_ratio={round(ratio_p95, 5)} samples={len(samples)}"
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
