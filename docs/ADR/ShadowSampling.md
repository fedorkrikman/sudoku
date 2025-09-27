# ADR: ShadowSampling v1

> Status: Accepted  
> Verified on 2025-09-27

## Context

Nova Solver выводится в тень поверх legacy-пайплайна Sudoku-9×9. Требуется
детерминированное сэмплирование, сопоставимые solved_ref артефакты и
наблюдаемость для принятия решения о переключении продакшена.

## Decision

- В оркестраторе работает модуль `shadow_compare`, использующий SHA-256 хэш от
  конкатенации `hash_salt || run_id || "sudoku" || "shadow" || puzzle_digest`
  (при `sticky=true` идентификатор запуска опускается) для выбора сэмплов.
- Сэмплирование конфигурируется по профилям: dev/test → 0.25, pilot → 1.0,
  prod → 0.0 с возможностью динамической корректировки.
- Значения `sample_rate` конфигурируются десятичными строками (точка как
  разделитель, ≤6 знаков после точки). Числовые переопределения работают с
  предупреждением в 2А, но подлежат удалению в следующей итерации.
- При попадании в выборку запускается альтернативный solver, сравниваются
  `CompleteGrid` и `Verdict.unique`, логируется событие `shadowlog/1`.
- Логи нормализуются под `logging/shadowlog_v1.md` и складываются в `logs/shadow`.
- CI использует отчёт `tools/ci/shadow_overhead_guard` для контроля overhead и
  рекомендуемых действий по sample_rate.
- Приоритет конфигурации: **CLI (`CLI_SHADOW_*`) > ENV (`PUZZLE_SHADOW_*`,
  `SHADOW_*`) > TOML (`config.toml` + `config/features.toml`) > built-ins (dev
  профиль)**. Значения кэшируются на время процесса.
- Shadow события формируются как `sudoku.shadow_sample.v1` (совпадение) и
  `sudoku.shadow_mismatch.v1` (расхождение) с полями:
  `{run_id, ts_iso8601, commit_sha, baseline_sha, hw_fingerprint, profile,
  puzzle_digest, solver_primary, solver_shadow, verdict_status, time_ms_primary,
  time_ms_shadow, diff_summary, solved_ref_digest, sample_rate,
  solve_trace_sha256, state_hash_sha256, envelope_jcs_sha256}`.
- `state_hash_sha256 = sha256(bytes(C) || bytes(G))`, где `C` — 81×9 матрица
  флагов кандидатов (0/1), `G` — 81 байт фактической сетки (0..9). Хэш
  вычисляется на стороне тени независимо от наличия `CompleteGrid`.
- Гейт детерминизма сравнивает кортеж `H = (grid_sha256,
  solve_trace_sha256, state_hash_sha256, envelope_jcs_sha256)` для каждого
  сида.

### Parameters

| Field | Source | Notes |
| --- | --- | --- |
| `hash_salt` | env/config | по умолчанию `shadow_compare.hash_salt` |
| `sticky` | env/config | фиксирует выборку на уровне пазла |
| `run_id` | orchestrator | UUID, детерминированный от root seed |
| `stage` | orchestrator | имя стадии (`solver:check_uniqueness`, …) |
| `seed` | orchestrator | производный сид стадии |
| `module_id` | router | идентификатор модуля (`sudoku-9x9:/novus@`) |

### Sample rate per profile

| Profile | Sample rate |
| --- | --- |
| dev | 0.25 |
| test | 0.25 |
| prod | 0.0 |
| pilot | 1.0 |

### Auto regulation policy

- Если `overhead_pct > 5%` три дня подряд → `prod.sample_rate /= 2`.
- Если `mismatch_rate > 0.2%` на 1000 событий → `prod.sample_rate = 0.05` (raise).
- Если `mismatch_rate < 0.02%` на 10k событий → `prod.sample_rate = 0.005` (lower).

## Consequences

- Тени не влияют на основной путь экспорта, но дают сигнал о паритете и
  перформансе.
- Логи канонизированы, могут сравниваться побайтно, что упрощает детерминизм.
- Требуется поддерживать baseline-отчёты и чистить `logs/shadow` от устаревших
  файлов, чтобы гейты оставались быстрыми.
