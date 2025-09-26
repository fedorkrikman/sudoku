"""Command line helpers for orchestrator workflows."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Iterable, List

from orchestrator.orchestrator import run_pipeline
from tools.reports import mismatch_report


def _build_shadow_env(enable: bool, rate: float | None) -> Dict[str, str]:
    env: Dict[str, str] = {}
    if enable:
        env["PUZZLE_SHADOW_MODE_ENABLED"] = "1"
    if rate is not None:
        env["PUZZLE_SHADOW_RATE"] = str(rate)
    return env


def _run_one(
    seed: str,
    *,
    puzzle: str | None,
    profile: str,
    shadow_env: Dict[str, str] | None,
) -> dict:
    env = {
        "PUZZLE_ROOT_SEED": seed,
        "PUZZLE_VALIDATION_PROFILE": profile,
    }
    if puzzle:
        env["PUZZLE_KIND"] = puzzle
    if shadow_env:
        env.update(shadow_env)
    result = run_pipeline(puzzle_kind=puzzle, env_overrides=env)
    return result


def cmd_run_one(args: argparse.Namespace) -> int:
    shadow_env = _build_shadow_env(args.enable_shadow, args.shadow_rate)
    result = _run_one(
        args.seed,
        puzzle=args.puzzle,
        profile=args.profile,
        shadow_env=shadow_env,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def _iter_seeds(path: Path) -> Iterable[str]:
    for line in path.read_text().splitlines():
        value = line.strip()
        if not value or value.startswith("#"):
            continue
        yield value


def cmd_batch_seeds(args: argparse.Namespace) -> int:
    seeds = list(_iter_seeds(Path(args.file)))
    summaries: List[dict] = []
    shadow_env = _build_shadow_env(args.enable_shadow, args.shadow_rate)
    for seed in seeds:
        summaries.append(
            _run_one(
                seed,
                puzzle=args.puzzle,
                profile=args.profile,
                shadow_env=shadow_env,
            )
        )
    print(json.dumps(summaries, indent=2, sort_keys=True))
    return 0


def cmd_report_shadow(args: argparse.Namespace) -> int:
    base_dir = Path(args.path)
    files = sorted(base_dir.glob("**/*.jsonl"))
    if not files:
        raise SystemExit(f"No JSONL logs found under {base_dir}")
    summary = mismatch_report.aggregate(files, top=args.top)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Shadow orchestrator helpers")
    sub = parser.add_subparsers(dest="command", required=True)

    run_one = sub.add_parser("run-one", help="Execute a single orchestrator run")
    run_one.add_argument("--seed", required=True)
    run_one.add_argument("--profile", default="dev")
    run_one.add_argument("--puzzle", default=None)
    run_one.add_argument(
        "--enable-shadow",
        action="store_true",
        help="Enable shadow comparison for this run",
    )
    run_one.add_argument(
        "--shadow-rate",
        type=float,
        default=None,
        help="Override shadow sampling rate (0.0-1.0)",
    )
    run_one.set_defaults(func=cmd_run_one)

    batch = sub.add_parser("batch-seeds", help="Execute orchestrator runs for seeds from file")
    batch.add_argument("file")
    batch.add_argument("--profile", default="dev")
    batch.add_argument("--puzzle", default=None)
    batch.add_argument(
        "--enable-shadow",
        action="store_true",
        help="Enable shadow comparison for all seeds",
    )
    batch.add_argument(
        "--shadow-rate",
        type=float,
        default=None,
        help="Override shadow sampling rate for all seeds",
    )
    batch.set_defaults(func=cmd_batch_seeds)

    report = sub.add_parser("report-shadow", help="Aggregate shadow mismatch statistics")
    report.add_argument("path", help="Directory containing JSONL logs")
    report.add_argument("--top", type=int, default=5)
    report.set_defaults(func=cmd_report_shadow)

    return parser


def main(argv: List[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
