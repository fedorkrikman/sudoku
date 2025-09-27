# REPORT — ZI-FULL shadow bring-up (2025-09-27)

## Task
Harden the Sudoku shadow pipeline with structured mismatch events, taxonomy counters, guardrails, overhead gating, documentation
checks, and soak reporting while keeping the primary path untouched.

## Environment
- OS: Linux-6.12.13-x86_64-with-glibc2.39
- Python: 3.12.10

## Changes
- Implemented `sudoku.shadow_mismatch.v1` emission with taxonomy C1..C6, guardrail telemetry, and solver identity
  normalisation in `src/orchestrator/shadow_compare.py`.
- Extended CI tooling: schema validator with fallback (`tools/ci/schema_check.py`), overhead guard with baseline persistence
  (`tools/ci/shadow_overhead_guard.py`), soak runner with PCG64 sampling (`tools/ci/soak_run.py`), and documentation guardrails
  (`tools/ci/doc_checks.py`).
- Added JSONSchema and golden samples under `docs/icd/schemas/` and `tests/acceptance/schemas/`; refreshed acceptance tests and
  docs (`README.md`, `docs/icd.md`, `docs/ADR/ShadowSampling.md`, `CHANGELOG.md`).

## Commands
- `PYTHONPATH=src pytest -q tests/acceptance` (exit 0)
- `PYTHONPATH=src python tools/ci/doc_checks.py --expect-date 2025-09-27 --files README.md docs/icd.md docs/ADR/ShadowSampling.md CHANGELOG.md` (exit 0)

## Artifacts
- `docs/icd/schemas/sudoku.shadow_mismatch.v1.schema.json`
- `tests/acceptance/schemas/shadow_mismatch_example.json`
- `tests/acceptance/schemas/shadow_guardrail_example.json`
- `reports/overhead/` (baseline & report written by guard script on demand)
- `reports/soak/` (daily soak summaries)

## Metrics
- **Event/Guardrails:** taxonomy codes map to severities (C1/C2 critical, C3/C4 major, C5/C6 minor); guardrails enforce
  nodes ≤ 200 000, bt_depth ≤ 60, time_ms ≤ 2 000 with `verdict_status="budget_exhausted"`.
- **Overhead:** CI gate requires `p95(delta_ms) ≤ 50 ms` and `p95(shadow)/p95(base) ≤ 1.05`; medians persisted per `(commit, hw, profile)` for 14 days.
- **Soak:** nightly PCG64 selection of up to 20 000 seeds, difficulty tallies, and guardrail/mismatch aggregation with 30-day retention.

## Exit Status
PASS
