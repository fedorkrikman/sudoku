# REPORT — ZI-FULL shadow bring-up (2025-09-27)

## Task
Launch Sudoku-9x9 novus solver in dev profile under shadow state with delegation to legacy, document run instructions, and capture supporting checks.

## Environment
- OS: Linux-6.12.13-x86_64-with-glibc2.39
- Python: 3.12.10

## Changes
- README.md — updated shadow CLI usage, feature flag notes, verification stamp.
- docs/STRATEGY.md — recorded dev shadow bring-up milestone and updated stamp.
- docs/GOALS_ROADMAP.md — marked iteration A complete, refreshed acceptance guidance.
- docs/CODEX_GUIDE.md — aligned shadow-mode instructions with CLI workflow.
- CHANGELOG.md — added Unreleased entry summarising shadow bring-up.

## Commands
- `PYTHONPATH=src pytest -q tests/test_solver_novus_resolution.py` (exit 0)
- `PYTHONPATH=src pytest -q tests/test_sampling.py tests/test_shadow_classifier.py tests/test_feature_flags.py` (exit 0)
- `PYTHONPATH=src python -m tools.cli.orchestrate run-one --seed 42 --profile dev --enable-shadow --shadow-rate 0.25` (exit 0)

## Artifacts
- `logs/shadow/20250926/shadow_00.jsonl` — shadow skip event (existing rotation, 1.6 KB).
- `exports/3b3e0c8f-fb28d5f6.pdf` — generated during CLI run (legacy primary path).

## Assumptions Applied
- A1 (level A): novus `port_check_uniqueness` delegates to legacy during shadow bring-up; parity enforcement handled in next iteration.

## Exit Status
PASS
