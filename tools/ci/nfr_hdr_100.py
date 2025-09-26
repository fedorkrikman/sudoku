#!/usr/bin/env python3
"""Non-functional latency snapshot using HDR-style percentiles."""

from __future__ import annotations

import argparse
import json
import resource
import random
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from orchestrator import orchestrator

ACCEPTANCE_PATH = ROOT / "data" / "acceptance" / "acceptance_corpus_9x9_v1.json"
REPORT_DEFAULT = ROOT / "reports" / "nfr_hdr_100" / "report.json"

_GUARDRAILS = {
    "dev": 400.0,
    "test": 350.0,
    "prod": 300.0,
}


def _load_seeds(limit: int, offset: int = 0) -> List[str]:
    payload = json.loads(ACCEPTANCE_PATH.read_text("utf-8"))
    seeds = list(payload.get("seeds", []))
    if limit + offset > len(seeds):
        raise ValueError("Acceptance corpus does not contain enough seeds")
    return seeds[offset : offset + limit]


def _quantiles(values: Sequence[float], percentiles: Iterable[float]) -> Dict[float, float]:
    if not values:
        return {p: 0.0 for p in percentiles}
    sorted_vals = sorted(values)
    results: Dict[float, float] = {}
    for p in percentiles:
        if not 0 <= p <= 100:
            raise ValueError("Percentiles must be between 0 and 100")
        rank = (p / 100.0) * (len(sorted_vals) - 1)
        lower = int(rank)
        upper = min(lower + 1, len(sorted_vals) - 1)
        weight = rank - lower
        results[p] = sorted_vals[lower] * (1 - weight) + sorted_vals[upper] * weight
    return results


def _hodges_lehmann(sample: Sequence[float]) -> float:
    if not sample:
        return 0.0
    pairs: List[float] = []
    for i, x in enumerate(sample):
        for y in sample[i:]:
            pairs.append((x + y) / 2)
    pairs.sort()
    mid = len(pairs) // 2
    if len(pairs) % 2 == 1:
        return pairs[mid]
    return 0.5 * (pairs[mid - 1] + pairs[mid])


def _mann_whitney_u(sample_a: Sequence[float], sample_b: Sequence[float]) -> float:
    combined = [(value, 0) for value in sample_a] + [(value, 1) for value in sample_b]
    combined.sort(key=lambda item: item[0])
    ranks: List[float] = []
    i = 0
    while i < len(combined):
        j = i
        while j < len(combined) and combined[j][0] == combined[i][0]:
            j += 1
        rank = (i + j + 1) / 2
        ranks.extend([rank] * (j - i))
        i = j
    rank_a = sum(rank for (rank, (_, group)) in zip(ranks, combined) if group == 0)
    n1 = len(sample_a)
    n2 = len(sample_b)
    u1 = rank_a - n1 * (n1 + 1) / 2
    mean_u = n1 * n2 / 2
    std_u = (n1 * n2 * (n1 + n2 + 1) / 12) ** 0.5
    if std_u == 0:
        return 0.5
    z = (u1 - mean_u) / std_u
    # Two-sided p-value approximation using complementary error function.
    from math import erfc, sqrt

    return erfc(abs(z) / sqrt(2))


def _bootstrap_percentile(values: Sequence[float], percentile: float, samples: int = 1000) -> float:
    if not values:
        return 0.0
    rng = random.Random(0)
    estimates = []
    for _ in range(samples):
        resample = [values[rng.randrange(len(values))] for _ in values]
        estimates.append(_quantiles(resample, [percentile])[percentile])
    estimates.sort()
    mid = len(estimates) // 2
    if len(estimates) % 2 == 1:
        return estimates[mid]
    return 0.5 * (estimates[mid - 1] + estimates[mid])


def _run_once(seed: str, profile: str) -> float:
    overrides = {
        "PUZZLE_ROOT_SEED": seed,
        "PUZZLE_VALIDATION_PROFILE": profile,
    }
    start = time.perf_counter()
    orchestrator.run_pipeline(env_overrides=overrides)
    duration_ms = (time.perf_counter() - start) * 1000.0
    return duration_ms


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default="dev", help="Validation profile")
    parser.add_argument("--out", type=Path, default=REPORT_DEFAULT, help="Path to JSON report")
    parser.add_argument("--baseline", type=Path, help="Optional baseline report to compare against")
    parser.add_argument("--bootstrap", action="store_true", help="Use bootstrap estimate for p95")
    args = parser.parse_args(argv)

    seeds = _load_seeds(103)
    warmup = seeds[:3]
    measurement = seeds[3:103]

    for seed in warmup:
        _run_once(seed, args.profile)

    durations = [
        _run_once(seed, args.profile)
        for seed in measurement
    ]

    rss_bytes = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    percentiles = _quantiles(durations, [50, 95, 99])

    baseline_data: Optional[Dict[str, float]] = None
    if args.baseline:
        baseline_data = json.loads(args.baseline.read_text("utf-8"))

    hl_delta = 0.0
    u_p = 1.0
    if baseline_data and "durations_ms" in baseline_data:
        baseline_values = baseline_data["durations_ms"]
        if isinstance(baseline_values, list) and baseline_values:
            hl_delta = _hodges_lehmann([a - b for a, b in zip(durations, baseline_values[: len(durations)])])
            u_p = _mann_whitney_u(durations, baseline_values[: len(durations)])

    guardrail = _GUARDRAILS.get(args.profile, 400.0)
    p95_ms = percentiles[95]
    passed_guardrail = p95_ms <= guardrail

    if args.bootstrap:
        p95_estimate = _bootstrap_percentile(durations, 95)
    else:
        p95_estimate = p95_ms

    report = {
        "p50_ms": round(percentiles[50], 3),
        "p95_ms": round(p95_ms, 3),
        "p95_bootstrap_ms": round(p95_estimate, 3),
        "p99_ms": round(percentiles[99], 3),
        "rss_peak_bytes": int(rss_bytes),
        "u_p": round(u_p, 6),
        "hl_delta_ms": round(hl_delta, 3),
        "passed_guardrail": bool(passed_guardrail),
        "durations_ms": [round(value, 3) for value in durations],
    }
    report_path = args.out
    report_path.parent.mkdir(parents=True, exist_ok=True)
    canonical = json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    report_path.write_text(canonical + "\n", encoding="utf-8")

    status = "PASS" if passed_guardrail else "WARN"
    print(f"NFR {status}: p95={report['p95_ms']}ms guardrail={guardrail} rss={report['rss_peak_bytes']} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
