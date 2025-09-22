#!/usr/bin/env python3
"""Smoke-test deterministic behaviour of the offline pipeline."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from orchestrator import orchestrator


def _run_with_seed(seed: str) -> dict:
    previous = os.environ.get("PUZZLE_ROOT_SEED")
    try:
        os.environ["PUZZLE_ROOT_SEED"] = seed
        return orchestrator.run_pipeline()
    finally:
        if previous is None:
            os.environ.pop("PUZZLE_ROOT_SEED", None)
        else:
            os.environ["PUZZLE_ROOT_SEED"] = previous


def main() -> int:
    first = _run_with_seed("deterministic-seed")
    second = _run_with_seed("deterministic-seed")

    for key in ("spec_id", "complete_id", "verdict_id"):
        if first[key] != second[key]:
            print(f"determinism failed for {key}: {first[key]} vs {second[key]}")
            return 1

    third = _run_with_seed("different-seed")
    for key in ("spec_id", "complete_id", "verdict_id"):
        if first[key] == third[key]:
            print(f"different seed produced identical {key}: {first[key]}")
            return 1

    print("Determinism smoke-test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
