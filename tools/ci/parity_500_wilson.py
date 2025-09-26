#!/usr/bin/env python3
"""Parity gate comparing novus against legacy with Wilson interval."""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from artifacts import artifact_store
from orchestrator import orchestrator

ACCEPTANCE_PATH = ROOT / "data" / "acceptance" / "acceptance_corpus_9x9_v1.json"
REPORT_DEFAULT = ROOT / "reports" / "parity_500" / "report.json"


@dataclass
class RunOutcome:
    seed: str
    profile: str
    solver: str
    complete_id: str
    verdict_id: str
    canonical_hash: str
    unique: Optional[bool]


@dataclass
class Mismatch:
    seed: str
    severity: str
    reason: str
    baseline_id: str
    candidate_id: str


def _load_seeds(sample: int, *, rng_seed: int = 0) -> List[str]:
    payload = json.loads(ACCEPTANCE_PATH.read_text("utf-8"))
    seeds = list(payload.get("seeds", []))
    if sample > len(seeds):
        raise ValueError(f"requested {sample} seeds but corpus only has {len(seeds)} entries")
    rng = random.Random(rng_seed)
    return [seeds[i] for i in rng.sample(range(len(seeds)), sample)]


def _extract_complete_hash(artifact_id: str) -> str:
    artifact = artifact_store.load_artifact(artifact_id)
    digest = artifact.get("canonical_hash")
    if not isinstance(digest, str):
        digest = artifact_store.compute_artifact_id(artifact)
    return digest


def _extract_unique(verdict_id: str) -> Optional[bool]:
    artifact = artifact_store.load_artifact(verdict_id)
    unique = artifact.get("unique")
    if unique is not None and not isinstance(unique, bool):
        return None
    return unique


def _run(seed: str, profile: str, solver: Optional[str]) -> RunOutcome:
    overrides = {
        "PUZZLE_ROOT_SEED": seed,
        "PUZZLE_VALIDATION_PROFILE": profile,
    }
    if solver == "novus":
        overrides["PUZZLE_SOLVER_IMPL"] = "novus"
        overrides["PUZZLE_SOLVER_STATE"] = "default"
    else:
        overrides["PUZZLE_SOLVER_IMPL"] = "legacy"
        overrides["PUZZLE_SOLVER_STATE"] = "default"
    result = orchestrator.run_pipeline(env_overrides=overrides)
    complete_id = result.get("complete_id")
    verdict_id = result.get("verdict_id")
    if not isinstance(complete_id, str) or not isinstance(verdict_id, str):
        raise RuntimeError("pipeline did not return required artifact identifiers")
    digest = _extract_complete_hash(complete_id)
    unique = _extract_unique(verdict_id)
    return RunOutcome(
        seed=seed,
        profile=profile,
        solver=solver or "legacy",
        complete_id=complete_id,
        verdict_id=verdict_id,
        canonical_hash=digest,
        unique=unique,
    )


def _classify(baseline: RunOutcome, candidate: RunOutcome) -> Optional[Mismatch]:
    if baseline.canonical_hash != candidate.canonical_hash:
        return Mismatch(
            seed=candidate.seed,
            severity="critical",
            reason="grid digest differs",
            baseline_id=baseline.complete_id,
            candidate_id=candidate.complete_id,
        )
    if baseline.unique != candidate.unique:
        return Mismatch(
            seed=candidate.seed,
            severity="major",
            reason="uniqueness flag differs",
            baseline_id=baseline.verdict_id,
            candidate_id=candidate.verdict_id,
        )
    return None


def _wilson_lower_bound(successes: int, trials: int) -> float:
    if trials == 0:
        return 0.0
    if successes >= trials:
        return 1.0
    z = 1.959963984540054  # 95% two-sided z-score
    phat = successes / trials
    denominator = 1 + (z ** 2) / trials
    centre = phat + (z ** 2) / (2 * trials)
    margin = z * math.sqrt((phat * (1 - phat) + (z ** 2) / (4 * trials)) / trials)
    return max(0.0, (centre - margin) / denominator)


def _report(mismatches: List[Mismatch], matches: int, total: int) -> Dict[str, object]:
    critical = sum(1 for m in mismatches if m.severity == "critical")
    major = sum(1 for m in mismatches if m.severity == "major")
    ci_lower = _wilson_lower_bound(matches, total)
    payload: Dict[str, object] = {
        "n": total,
        "matches": matches,
        "ci_lower": round(ci_lower, 6),
        "critical": critical,
        "major": major,
        "passed": ci_lower >= 0.995 and critical == 0 and major <= 3,
    }
    if mismatches:
        first = mismatches[0]
        payload["top_mismatch"] = {
            "seed": first.seed,
            "severity": first.severity,
            "reason": first.reason,
            "baseline_id": first.baseline_id,
            "candidate_id": first.candidate_id,
        }
    else:
        payload["top_mismatch"] = None
    return payload


def _write_report(report: Dict[str, object], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    canonical = json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    path.write_text(canonical + "\n", encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default="dev", help="Validation profile to use")
    parser.add_argument("--n", type=int, default=500, help="Number of samples")
    parser.add_argument("--out", type=Path, default=REPORT_DEFAULT, help="Path to JSON report")
    parser.add_argument("--seed", type=int, default=0, help="PRNG seed for sampling")
    args = parser.parse_args(argv)

    seeds = _load_seeds(args.n, rng_seed=args.seed)
    mismatches: List[Mismatch] = []
    matches = 0

    for seed in seeds:
        baseline = _run(seed, args.profile, solver="legacy")
        candidate = _run(seed, args.profile, solver="novus")
        mismatch = _classify(baseline, candidate)
        if mismatch is None:
            matches += 1
        else:
            mismatches.append(mismatch)

    report = _report(mismatches, matches, len(seeds))
    _write_report(report, args.out)

    status = "PASS" if report["passed"] else "FAIL"
    print(
        f"Parity {status}: matches={report['matches']}/{report['n']} ci_lower={report['ci_lower']} "
        f"critical={report['critical']} major={report['major']}"
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
