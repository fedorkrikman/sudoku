"""Nightly shadow soak runner with deterministic seed selection."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Mapping

try:  # optional PCG64 implementation via numpy
    import numpy as _np  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    _np = None  # type: ignore[assignment]

ROOT = Path(__file__).resolve().parents[2]

if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from orchestrator import orchestrator

_SEED_UPPER = 10_000
_SOAK_BASE = ROOT / "reports" / "soak"
_RETENTION_DAYS = 30
_DIFFICULTY_BUCKETS = (
    (0, 2_500, "easy"),
    (2_500, 5_000, "medium"),
    (5_000, 7_500, "hard"),
    (7_500, _SEED_UPPER, "expert"),
)


def _select_seeds(count: int, epoch_seed: int) -> List[int]:
    size = min(count, _SEED_UPPER)
    if _np is not None:  # pragma: no cover - exercised in acceptance
        rng = _np.random.Generator(_np.random.PCG64(epoch_seed))
        choice = rng.choice(_SEED_UPPER, size=size, replace=False)
        return [int(value) for value in choice]
    # Fallback to deterministic shuffle based on seed
    pool = list(range(_SEED_UPPER))
    step = (epoch_seed * 6364136223846793005 + 1) % (1 << 64)
    for index in range(_SEED_UPPER - 1, 0, -1):
        step = (step * 6364136223846793005 + 1) % (1 << 64)
        swap = step % (index + 1)
        pool[index], pool[swap] = pool[swap], pool[index]
    return pool[:size]


def _difficulty_for(seed: int) -> str:
    for lower, upper, label in _DIFFICULTY_BUCKETS:
        if lower <= seed < upper:
            return label
    return "unknown"


def _rotate_history(base: Path) -> None:
    if not base.exists():
        return
    cutoff = datetime.now(timezone.utc) - timedelta(days=_RETENTION_DAYS)
    for child in base.iterdir():
        if not child.is_dir():
            continue
        try:
            stamp = datetime.strptime(child.name, "%Y%m%d")
        except ValueError:
            continue
        if stamp.replace(tzinfo=timezone.utc) < cutoff:
            shutil.rmtree(child, ignore_errors=True)


def _write_report(payload: Mapping[str, object], out_path: Path, dated_path: Path) -> None:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(canonical, encoding="utf-8")
    dated_path.parent.mkdir(parents=True, exist_ok=True)
    dated_path.write_text(canonical, encoding="utf-8")


def _base_seed_from_date(target: datetime) -> int:
    return int(target.strftime("%Y%m%d"))


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=20_000, help="Number of soak samples to execute")
    parser.add_argument("--out", type=Path, default=_SOAK_BASE / "summary.json", help="Output summary path")
    parser.add_argument("--profile", default="dev", help="Validation profile to use")
    parser.add_argument("--seed", type=int, help="Override base seed (defaults to YYYYMMDD)")
    args = parser.parse_args(list(argv) if argv is not None else None)

    now = datetime.now(timezone.utc)
    base_seed = args.seed if args.seed is not None else _base_seed_from_date(now)
    selected = _select_seeds(args.n, base_seed)

    taxonomy_counter: Counter[str] = Counter()
    difficulty_counter: Counter[str] = Counter()
    failures: List[Dict[str, object]] = []

    processed = 0
    for seed in selected:
        difficulty_counter[_difficulty_for(seed)] += 1
        overrides = {
            "PUZZLE_ROOT_SEED": f"soak-{seed:04d}",
            "CLI_SHADOW_ENABLED": "1",
            "CLI_SHADOW_SAMPLE_RATE": "1.0",
            "PUZZLE_VALIDATION_PROFILE": args.profile,
        }
        try:
            result = orchestrator.run_pipeline(env_overrides=overrides)
        except Exception as exc:  # pragma: no cover - defensive
            failures.append({"seed": seed, "error": str(exc)})
            continue
        shadow = result.get("shadow", {})
        event = shadow.get("event") if isinstance(shadow, Mapping) else None
        if isinstance(event, Mapping) and event.get("type") == "sudoku.shadow_mismatch.v1":
            taxonomy = event.get("taxonomy")
            if isinstance(taxonomy, Mapping):
                code = str(taxonomy.get("code", "C6"))
                taxonomy_counter[code] += 1
                severity = str(taxonomy.get("severity", ""))
                reason = str(taxonomy.get("reason", ""))
                verdict_status = str(event.get("verdict_status", "mismatch"))
                if severity.upper() == "CRITICAL" or verdict_status != "mismatch":
                    failures.append(
                        {
                            "seed": seed,
                            "code": code,
                            "severity": severity,
                            "reason": reason,
                            "verdict_status": verdict_status,
                        }
                    )
        processed += 1

    requested = args.n
    coverage = 0.0 if requested <= 0 else processed / requested
    status = "PASS" if not failures else "WARN"

    skipped = max(0, requested - processed)

    summary: Dict[str, object] = {
        "timestamp": now.isoformat(timespec="seconds"),
        "profile": args.profile,
        "requested": requested,
        "processed": processed,
        "skipped": skipped,
        "unique_seed_pool": _SEED_UPPER,
        "seed_source": "pcg64" if _np is not None else "lcg-fallback",
        "base_seed": base_seed,
        "coverage": round(coverage, 5),
        "difficulty_mix": dict(difficulty_counter),
        "taxonomy": {code: taxonomy_counter.get(code, 0) for code in sorted({*taxonomy_counter.keys(), "C1", "C2", "C3", "C4", "C5", "C6"})},
        "failures": failures,
        "status": status,
    }

    out_path = args.out if args.out.is_absolute() else ROOT / args.out
    date_dir = _SOAK_BASE / now.strftime("%Y%m%d")
    dated_path = date_dir / "summary.json"
    _write_report(summary, out_path, dated_path)
    _rotate_history(_SOAK_BASE)

    print(
        f"Soak run {status}: requested={requested} processed={processed} "
        f"critical={sum(1 for item in failures if item.get('severity', '').upper() == 'CRITICAL')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
