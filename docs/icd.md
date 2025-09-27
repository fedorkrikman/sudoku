# Interface Control Document – Shadow Compare Integration

> Verified on 2025-09-27

**Compatibility:** schema `sudoku.shadow_mismatch.v1` (draft-07) — см. раздел Counters and events.

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

* Несоответствия логируются событием ``sudoku.shadow_mismatch.v1`` (см. [schema](./schemas/sudoku.shadow_mismatch.v1.schema.json)).
  Поля включают:
  - ``run_id``, ``stage``, ``seed`` — детерминированные идентификаторы запуска.
  - ``commit_sha``, ``baseline_sha`` — SHA-1/256 коммита и baseline (hex lower).
  - ``hw_fingerprint`` — 16-символьный SHA-256 дайджест ``platform.uname``.
  - ``time_ms_primary`` и ``time_ms_shadow`` — целочисленные миллисекунды.
  - ``taxonomy`` — структура ``{code, severity, reason}`` с кодами ``C1``..``C6``.
  - ``diff_summary`` — ``<CODE>:<reason>`` для удобства агрегации.
  - ``sample_rate`` + дайджесты ``solve_trace_sha256``, ``state_hash_sha256``, ``envelope_jcs_sha256``.
  - При срабатывании защитных лимитов (``nodes`` > 200k, ``bt_depth`` > 60, ``time_ms`` > 2000) добавляются поля
    ``nodes``, ``bt_depth``, ``time_ms``, ``limit_hit`` и статус ``verdict_status = budget_exhausted`` (таксономия ``C4``).
* Совпадения фиксируются ``sudoku.shadow_sample.v1`` (те же поля без ``taxonomy`` и защитных метрик).
* Агрегированные счётчики:
  - ``shadow_ok`` – совпадение primary и shadow.
  - ``shadow_mismatch_{CODE}`` – количество несоответствий по коду ``C1``..``C6``.
  - ``shadow_skipped`` – попадание в выборку, которое не было выполнено (sample miss).
* ``run_pipeline`` возвращает событие и счётчики в ``results['shadow']`` для CI и офлайн-отчётов.

### Taxonomy ``C1`` – ``C6``

| Code | Severity  | Описание |
| ---- | --------- | -------- |
| ``C1`` | CRITICAL | Несовпадение флага ``unique``/вердикта |
| ``C2`` | CRITICAL | Отличия в решённой сетке |
| ``C3`` | MAJOR    | Расхождение trace/solve trace |
| ``C4`` | MAJOR    | Срабатывание guardrail (узлы/время/глубина) |
| ``C5`` | MINOR    | Отличия канонического представления (например, кандидаты) |
| ``C6`` | MINOR    | Прочие детерминированные расхождения |
