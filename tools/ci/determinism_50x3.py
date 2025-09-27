#!/usr/bin/env python3
"""Determinism gate: seeds from file × R runs with canonical comparisons."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from artifacts import artifact_store
from orchestrator import orchestrator

REPORT_DEFAULT = ROOT / "reports" / "determinism_50x3" / "report.json"

_ARTIFACT_TYPES = {
    "Spec": "spec_id",
    "CompleteGrid": "complete_id",
    "Verdict": "verdict_id",
    "ExportBundle": "exportbundle_id",
}


@dataclass
class RunSnapshot:
    seed: str
    run_id: str
    artifacts: Dict[str, bytes]
    logs: List[Dict[str, object]]


def _read_seeds_file(path: Path) -> Sequence[str]:
    content = path.read_text("utf-8").splitlines()
    seeds = [line.strip() for line in content if line.strip()]
    if not seeds:
        raise ValueError(f"seeds file '{path}' is empty")
    return seeds


def _canonical_artifact(artifact_id: str) -> bytes:
    artifact = artifact_store.load_artifact(artifact_id)
    return artifact_store.canonicalize(artifact)


def _normalise_log_entry(entry: Dict[str, object]) -> Dict[str, object]:
    ignore_keys = {"timestamp", "ts", "host", "host_id", "pid", "duration_ms", "time_ms", "perf_delta_ms", "perf_delta_pct", "hw_fingerprint", "event_id"}
    numeric_round = {"perf_delta_ms", "perf_delta_pct", "time_ms_baseline", "sample_rate"}
    result: Dict[str, object] = {}
    for key, value in sorted(entry.items()):
        if key in ignore_keys:
            continue
        if isinstance(value, float) and key in numeric_round:
            result[key] = round(value, 3)
            continue
        if isinstance(value, dict):
            result[key] = _normalise_log_entry(value)  # type: ignore[arg-type]
            continue
        if isinstance(value, list):
            result[key] = [
                _normalise_log_entry(item) if isinstance(item, dict) else item
                for item in value
            ]
            continue
        result[key] = value
    return result


def _load_shadow_logs(run_id: str) -> List[Dict[str, object]]:
    shadow_dir = ROOT / "logs" / "shadow"
    if not shadow_dir.exists():
        return []
    matched: List[Dict[str, object]] = []
    pattern = f"{run_id}*"
    for path in sorted(shadow_dir.glob(pattern)):
        if path.suffix not in {".json", ""}:
            continue
        try:
            data = json.loads(path.read_text("utf-8"))
        except json.JSONDecodeError:
            continue
        if isinstance(data, list):
            entries: Iterable[Dict[str, object]] = [
                item for item in data if isinstance(item, dict)
            ]
        elif isinstance(data, dict):
            entries = [data]
        else:
            continue
        for entry in entries:
            matched.append(_normalise_log_entry(entry))
    return matched


def _snapshot(seed: str, profile: str, *, env: Dict[str, str] | None = None) -> RunSnapshot:
    overrides = {
        "PUZZLE_ROOT_SEED": seed,
        "PUZZLE_VALIDATION_PROFILE": profile,
    }
    if env:
        overrides.update(env)
    result = orchestrator.run_pipeline(env_overrides=overrides)
    artifacts = {}
    for name, key in _ARTIFACT_TYPES.items():
        artifact_id = result.get(key)
        if isinstance(artifact_id, str):
            artifacts[name] = _canonical_artifact(artifact_id)
    logs = _load_shadow_logs(result.get("run_id", ""))
    return RunSnapshot(seed=seed, run_id=result.get("run_id", "unknown"), artifacts=artifacts, logs=logs)


def _compare_snapshots(reference: RunSnapshot, candidate: RunSnapshot) -> List[Dict[str, object]]:
    disagreements: List[Dict[str, object]] = []
    for name in _ARTIFACT_TYPES:
        ref_bytes = reference.artifacts.get(name)
        cand_bytes = candidate.artifacts.get(name)
        if ref_bytes is None or cand_bytes is None:
            if ref_bytes != cand_bytes:
                disagreements.append({
                    "seed": candidate.seed,
                    "kind": "artifact",
                    "details": {"artifact": name, "message": "missing artifact"},
                })
            continue
        if ref_bytes != cand_bytes:
            disagreements.append({
                "seed": candidate.seed,
                "kind": "artifact",
                "details": {"artifact": name, "message": "payload mismatch"},
            })
    if reference.logs or candidate.logs:
        if len(reference.logs) != len(candidate.logs):
            disagreements.append({
                "seed": candidate.seed,
                "kind": "log",
                "details": {"message": "shadow log length mismatch", "expected": len(reference.logs), "actual": len(candidate.logs)},
            })
        else:
            for index, (ref_entry, cand_entry) in enumerate(zip(reference.logs, candidate.logs)):
                if ref_entry != cand_entry:
                    disagreements.append({
                        "seed": candidate.seed,
                        "kind": "log",
                        "details": {"index": index, "message": "shadow log entry mismatch"},
                    })
                    break
    return disagreements


def run(profile: str, seeds: Sequence[str], runs: int) -> Dict[str, object]:
    disagreements: List[Dict[str, object]] = []
    for seed in seeds:
        baseline = _snapshot(seed, profile)
        for attempt in range(1, runs):
            candidate = _snapshot(seed, profile)
            disagreements.extend(_compare_snapshots(baseline, candidate))
            if disagreements:
                break
        if disagreements:
            break
    return {"passed": not disagreements, "disagreements": disagreements}


def _write_report(report: Dict[str, object], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    canonical = json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    path.write_text(canonical + "\n", encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default="dev", help="Validation profile (dev/test/prod)")
    parser.add_argument("--seeds-file", type=Path, required=True, help="Path to file with newline-separated seeds")
    parser.add_argument("--runs", type=int, default=3, help="Number of runs per seed")
    parser.add_argument("--report", type=Path, default=REPORT_DEFAULT, help="Path to JSON report")
    args = parser.parse_args(argv)

    seeds = _read_seeds_file(args.seeds_file)
    report = run(args.profile, seeds, args.runs)
    _write_report(report, args.report)

    status = "PASS" if report["passed"] else "FAIL"
    print(
        f"Determinism {status}: seeds={len(seeds)} runs={args.runs} "
        f"disagreements={len(report['disagreements'])}"
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
