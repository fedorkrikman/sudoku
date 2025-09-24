# ADR: Shadow sampling & solved_ref validation

- Status: Accepted
- Date: 2025-09-24

## Context

Nova Solver rollout for Sudoku-9x9 requires deterministic sampling between the
existing legacy pipeline and the upcoming implementation.  Previous smoke runs
validated functional parity but lacked structured logging, solved grid
comparison and continuous performance tracking.  The rollout must not change
public ports and should keep the legacy path as the only side effect surface
for exports.

## Decision

* Introduce a ``shadow_compare`` module inside the orchestrator that performs
  deterministic sampling per ``run_id``, ``stage`` and ``module_id`` using the
  SHA-256 policy described in the rollout plan.  On sampling hits the module
  executes the counterpart solver implementation, compares the payload (unique
  verdict, solved grid reference) and emits a canonical ``shadowlog/1`` event
  while updating aggregate counters.
* Log emission follows the ``shadowlog v1`` schema with deterministic event IDs
  and hardware fingerprints.  The module records ``shadow_ok`` as well as
  mismatch/error counters so that CI jobs can detect regressions.
* Provide a dedicated micro-benchmark (I2, dev profile) that runs 60 Sudoku
  samples (30 easy, 30 hard) under CPU affinity, warm-up and repeated
  measurements.  Results are written to JSON and Markdown reports and compared
  against a stored baseline.
* Extend documentation with interface details (ICD), logging schema
  specification and an illustrative log example.  CI gains two new workflows:
  ``shadow-smoke`` for functional parity and ``perf-gates/i2_dev`` for the
  performance guardrails.

## Consequences

* Shadow runs operate transparently with deterministic sampling, enabling safe
  comparisons between Nova and legacy without impacting export behaviour.
* The micro-benchmark artefacts and counters unblock perf gating in CI.  The
  deterministic event IDs allow reproducibility checks and baseline binding.
* Additional maintenance is required to keep the I2 baseline fresh (TTL 30
  days) and to adjust thresholds when hardware profiles change.
