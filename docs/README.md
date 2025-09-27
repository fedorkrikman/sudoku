# Документация Sudoku Codex

## Быстрые ссылки
- [CODEX_GUIDE](./CODEX_GUIDE.md) — правила работы Codex с репозиторием.
- [GOALS_ROADMAP](./GOALS_ROADMAP.md) — цели, итерации и статус.
- [ADR](./ADR) — архитектурные решения (ADR-0001, ADR-0002 и последующие).

## Локальные проверки
1. `scripts/check_contracts.py` — проверка артефактов и фикстур по контрактам.
2. `scripts/smoke_determinism.py` — дымовой тест детерминизма пайплайна.

Запускать из корня репозитория:
```
./scripts/check_contracts.py
./scripts/smoke_determinism.py
```

## Solver implementations и режимы трассировки

- Переключатель `SOLVER_IMPL` управляет выбором между `legacy`, `nova` и
  `shadow` режимами SolverPort. По умолчанию активен `legacy`.
- Уровень трассировки задаётся через `TRACE_LEVEL` (`none`|`steps`|`full`) и
  влияет на формирование артефакта `SolveTrace` в Nova.
- Настройки по умолчанию заданы в секции `[solver.runtime]` файла
  [`config.toml`](../config.toml) и могут быть переопределены переменными
  окружения.

### Shadow solver bring-up

- Shadow-режим конфигурируется через `[shadow]` в `config/features.toml` и
  поддерживает приоритеты **CLI > ENV > TOML > built-ins**.
- CLI-флаги: `--shadow-enabled`, `--shadow-sample-rate`,
  `--shadow-log-mismatch`, `--shadow-budget-ms-p95` (для `python -m
  tools.cli.orchestrate run-one`).
- ENV-переменные: `CLI_SHADOW_*` (имитация CLI), `PUZZLE_SHADOW_*` и
  `SHADOW_*`.
- Значения по умолчанию: dev/test → 0.25, pilot → 1.0, prod → 0.0, primary →
  `legacy`, secondary → `novus`, `log_mismatch=true`, `budget_ms_p95=50`.
- События shadow фиксируются в `logs/shadow` с типом
  `sudoku.shadow_mismatch.v1` (mismatch) и `sudoku.shadow_sample.v1` (match),
  включая поля `run_id`, `ts_iso8601`, `commit_sha`, `baseline_sha`,
  `hw_fingerprint`, `puzzle_digest`, `solver_primary`, `solver_shadow`,
  `verdict_status`, `time_ms_primary`, `time_ms_shadow`, `diff_summary`,
  `solved_ref_digest`.

## Canonical Pattern Order v1

Новая архитектура Nova использует фиксированный порядок эвристик для
детерминированного воспроизведения результатов:

1. PROPAGATE: Peer elimination → Naked Single → Hidden Single
2. SUBSETS₂: Naked Pair → Hidden Pair
3. BOX–LINE: Pointing → Claiming
4. SUBSETS₃/₄: Naked/Hidden Triple → Naked/Hidden Quad
5. FISH: X-Wing → Swordfish → Jellyfish
6. WINGS: XY-Wing → XYZ-Wing → W-Wing
7. UNIQUES: Unique Rectangle (I–IV)
8. COLOR/CHAINS: Simple Coloring/Bi-coloring → Forcing Chains → 2-String Kite
9. ALS: ALS, ALS-XZ и производные
10. BRANCH: Backtracking (MRV; тай-брейки row→col→digit)

Изменения порядка требуют отдельного ADR с bump версии.

## Validation Center API
- Код Validation Center расположен в [`src/contracts/`](../src/contracts). Экспортируются фасады `contracts.validator.validate`, `assert_valid`, `check_refs` и профили из `contracts.profiles`.
- Профиль строгости выбирается переменной `PUZZLE_VALIDATION_PROFILE` (`dev`|`ci`|`prod`) или передачей имени/конфига в фасад.
- Оркестратор и скрипты вызывают ЕВЦ только на границах стадий: перед сохранением Spec/CompleteGrid/Verdict/ExportBundle и перед рендером PDF — `check_refs`.

## Где искать контракты и артефакты
- Схемы: каталог [`PuzzleContracts/`](../PuzzleContracts), идентификаторы описаны в `catalog.json`.
- Артефакты: хранилище [`artifacts/`](../artifacts) с канонизированными JSON и идентификаторами `sha256-*`.
