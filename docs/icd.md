# Interface Control Document – Shadow Compare Integration

## Overview

The orchestrator drives Sudoku puzzle generation through generator, solver and
printer ports.  Shadow sampling introduces an additional coordination layer
that executes comparison runs between the active solver implementation (Nova)
and the baseline legacy solver without changing public contracts.

## Orchestrator → ShadowCompare

* ``run_shadow_check`` is called immediately after the solver stage completes.
  Inputs include:
  - ``puzzle_kind`` – currently ``sudoku-9x9``.
  - ``run_id`` / ``stage`` / ``seed`` – used for deterministic sampling.
  - ``profile`` – environment profile (``dev``/``ci``/``prod``).
  - ``module`` – ``ResolvedModule`` describing the primary solver implementation.
  - ``sample_rate`` – float in ``[0, 1]`` obtained from the router policy.
  - ``hash_salt`` – optional UTF-8 salt (``PUZZLE_SHADOW_HASH_SALT``).
  - ``spec_artifact`` and ``complete_artifact`` – canonical payloads used for
    the shadow call (complete grid must carry ``artifact_id`` for solved_ref).
  - ``primary_payload`` and ``primary_time_ms`` – results from the main solver.
  - ``env`` / ``options`` – propagated environment overrides.
* Output is a ``ShadowOutcome`` exposing a structured event (``shadowlog/1``)
  and the delta counters that must be aggregated in telemetry or CI reports.

## Shadow sampling algorithm

* ``hash_material = hash_salt || run_id || stage || seed_dec || module_id``
  (where ``seed_dec`` is the integer interpretation of the hexadecimal seed).
* ``sampled = first_8_bytes(sha256(hash_material)) / 2^64 < sample_rate``.
* On sampling hits the module resolves the counterpart solver (legacy when the
  primary is Nova and vice versa) using the router with environment overrides.
  The comparison checks ``unique`` flags and ``solved_ref`` digests.

## Counters and events

* Event schema ``shadowlog/1`` includes deterministic ``event_id`` (sha256 hash
  of the canonical JSON without ``event_id``), solver metadata and optional
  comparison ``details``.  ``ts`` is derived deterministically from the sample
  digest to keep event IDs stable across replays.
* Aggregated counters:
  - ``shadow_ok`` – exact match between primary and shadow.
  - ``shadow_mismatch_{CODE}`` – mismatches for ``C*``/``M*`` codes.
  - ``shadow_error_{CODE}`` – exceptions during shadow execution (``E*``).
  - ``shadow_info`` – sampling miss bookkeeping.
* ``run_pipeline`` attaches the event payload and counters under the
  ``results['shadow']`` key for diagnostics and CI pipelines.
