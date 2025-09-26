# ADR: ShadowSampling v1

> Status: Accepted  
> Verified on 2025-09-26

## Context

Nova Solver выводится в тень поверх legacy-пайплайна Sudoku-9×9. Требуется
детерминированное сэмплирование, сопоставимые solved_ref артефакты и
наблюдаемость для принятия решения о переключении продакшена.

## Decision

- В оркестраторе работает модуль `shadow_compare`, использующий SHA-256 хэш от
  `(hash_salt, run_id, stage, module_id, seed)` для выбора сэмплов.
- Сэмплирование конфигурируется по профилям: dev/test — полный поток,
  prod/pilot — регулируемая доля.
- При попадании в выборку запускается альтернативный solver, сравниваются
  `CompleteGrid` и `Verdict.unique`, логируется событие `shadowlog/1`.
- Логи нормализуются под `logging/shadowlog_v1.md` и складываются в `logs/shadow`.
- CI использует отчёт `tools/ci/shadow_overhead_guard` для контроля overhead и
  рекомендуемых действий по sample_rate.

### Parameters

| Field | Source | Notes |
| --- | --- | --- |
| `hash_salt` | env/config | по умолчанию `shadow_compare.hash_salt` |
| `run_id` | orchestrator | UUID, детерминированный от root seed |
| `stage` | orchestrator | имя стадии (`solver:check_uniqueness`, …) |
| `seed` | orchestrator | производный сид стадии |
| `module_id` | router | идентификатор модуля (`sudoku-9x9:/novus@`) |

### Sample rate per profile

| Profile | Sample rate |
| --- | --- |
| dev | 1.0 |
| test | 0.3 |
| prod | 0.01 (авто-регулируется) |
| pilot | policy-based |

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
