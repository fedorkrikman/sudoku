# sudoku

> Verified on 2025-09-27

## Читайте в первую очередь

- [docs/CODEX_GUIDE.md](docs/CODEX_GUIDE.md)
- [docs/GOALS_ROADMAP.md](docs/GOALS_ROADMAP.md)

## Offline pipeline

Пайплайн выполняется локально и состоит из четырёх шагов: Spec → CompleteGrid →
Verdict → ExportBundle. Каждый шаг формирует артефакт, валидируется офлайн и
попадает в хранилище `artifacts/<Type>/<artifact_id>.json`. Для запуска
оркестратора:

```bash
PYTHONPATH=src python -m orchestrator.orchestrator
```

Корневой сид задаётся переменной окружения `PUZZLE_ROOT_SEED`. Один и тот же
сид даёт идентичные идентификаторы артефактов (Spec, CompleteGrid, Verdict),
что позволяет воспроизводить сборки офлайн.

### Запуск через оркестратор

Рекомендуемый способ генерации и экспорта PDF — выполнение оркестратора. Ниже
приведены основные сценарии:

1. **Базовый (legacy) конвейер** — используется по умолчанию и в CI, весь
   пайплайн проходит через проверенные legacy-модули.

   ```bash
   PYTHONPATH=src \
   python -m orchestrator.orchestrator \
     --puzzle sudoku-9x9 \
     --output-dir exports
   ```

2. **Dev-shadow** — запускает проверенный legacy-конвейер, одновременно
   подключая Nova Solver в «тени» для сбора метрик. Артефакты экспорта будут
   сформированы legacy-путём. Рекомендуемый запуск — через CLI-обёртку, чтобы
   явно указать профиль и параметры shadow.

   ```bash
   PYTHONPATH=src \
   python -m tools.cli.orchestrate run-one \
     --seed 42 \
     --profile dev \
     --enable-shadow \
     --shadow-rate 0.25
   ```

   Параметр `--shadow-rate` переопределяет значение из `config.toml`
   (по умолчанию 0.25 для профиля `dev`). Аналогичный эффект достигается
   переменными окружения `PUZZLE_SHADOW_MODE_ENABLED=1` и
   `PUZZLE_SHADOW_RATE=<0..1>`.

3. **Полный Nova-конвейер** — включает Nova Solver как основной. Используйте
   после успешного shadow-прогона.

   ```bash
   PUZZLE_VALIDATION_PROFILE=dev \
   PUZZLE_SOLVER_STATE=default \
   PUZZLE_SOLVER_IMPL=novus \
   PYTHONPATH=src \
   python -m orchestrator.orchestrator \
     --puzzle sudoku-9x9 \
     --output-dir exports_novus
   ```

## Shadow mode (overview)

- **Фича-флаг.** Shadow-путь активируется через `config/features.toml`
  (`shadow_mode.enabled`) или временно командой `run-one --enable-shadow`.
- **Опция sample-rate.** Настраивается переменной `PUZZLE_SHADOW_RATE`
  (по умолчанию 0.25 в профиле `dev`, 0.0 в остальных). Прод использует ≤ 0.01.
- **Разовый прогон.** `PYTHONPATH=src python -m tools.cli.orchestrate run-one --seed <hex> --profile dev --enable-shadow`.
- **Пакет сидов.** `PYTHONPATH=src python -m tools.cli.orchestrate batch-seeds seeds.txt --profile dev --enable-shadow`.
- **Отчёт по логам.** `PYTHONPATH=src python -m tools.cli.orchestrate report-shadow logs/shadow --top 10` — агрегирует
  `severity`/`kind` и вычисляет канонический дайджест сводки.
- **Ротация логов.** Shadow-лог сохраняется в `logs/shadow/YYYYMMDD/shadow_<nn>.jsonl`,
  ротируется при 100 MiB. Используйте `policy.shadow.recommend_action` для
  интерпретации метрик `overhead_pct` и `mismatch_rate`.

## Compatibility notes

- События рассогласований теперь описываются схемой [`docs/icd/schemas/sudoku.shadow_mismatch.v1.schema.json`](docs/icd/schemas/sudoku.shadow_mismatch.v1.schema.json).
  При превышении защитных лимитов (узлы, глубина бэктрекинга, время) они получают статус `budget_exhausted` и включают
  целочисленные поля `nodes`, `bt_depth`, `time_ms`, `limit_hit` вместе с таксономией кодов `C1…C6`.
- В JSONL-логах shadow значения `time_ms_primary` и `time_ms_shadow` фиксируются как целые миллисекунды; проверка
  `tools/ci/doc_checks.py` гарантирует отсутствие дробных секунд и валидирует 64-символьные hex-дайджесты.

## Contracts and artifacts

Схемы первого поколения лежат в каталоге [`PuzzleContracts/`](./PuzzleContracts).
Ключевые схемы: `Spec`, `CompleteGrid`, `Verdict` и `ExportBundle`. Общий конверт
поля описан в `_common/envelope-1.0.0.json`, а актуальные версии перечислены в
`catalog.json`.

Хранилище артефактов располагается в [`artifacts/`](./artifacts). Сохранение и
загрузка выполняются через `artifacts/artifact_store.py`, который канонизирует
JSON, вычисляет `artifact_id` вида `sha256-<hex>` и обеспечивает стабильные
пути хранения.

## Validation Center

Единый валидационный центр находится в [`src/contracts/`](./src/contracts).
Основные точки входа — функции `validator.validate` и `validator.assert_valid`,
которые проверяют артефакты по JSON-Schema, доменным инвариантам и
кросс-ссылкам. Оркестратор вызывает эти функции на границах стадий перед
записью артефактов, а `scripts/check_contracts.py` использует тот же API для
офлайн-проверок.

Профиль строгости выбирается через переменную окружения
`PUZZLE_VALIDATION_PROFILE` (`dev`|`ci`|`prod`). Профиль `dev` выполняет все
проверки и не валит пайплайн по WARN, `ci` трактует WARN как ошибки, `prod`
оставляет ключевые правила строгими, а второстепенные проверки (например
`verdict.cutoff.invalid`) переводит в WARN.

Дополнительные детали и ссылки собраны в [docs/ADR/adr-0002-validation-center.md](docs/ADR/adr-0002-validation-center.md)
и разделе «Validation Center API» в [docs/README.md](docs/README.md) и
[docs/CODEX_GUIDE.md](docs/CODEX_GUIDE.md).

## Local checks

Минимальный офлайн-CI доступен в директории [`scripts/`](./scripts):

- `scripts/check_contracts.py` — валидирует все валидные и невалидные
  фикстуры, а также артефакты из локального хранилища.
- `scripts/smoke_determinism.py` — дважды запускает пайплайн с одинаковым сидом
  и убеждается в совпадении идентификаторов, после чего проверяет, что другой
  сид приводит к отличающимся артефактам.

Запуск:

```bash
./scripts/check_contracts.py
./scripts/smoke_determinism.py
```

## How to verify locally

Проверочные скрипты из каталога `tools/ci` прогоняются локально перед PR и в
CI. Они пишут отчёты в `reports/**` в каноническом JSON (JCS) и выводят краткое
резюме в stdout.

1. Проверка детерминизма (50 сидов × 3 прогона):

   ```bash
   python -m tools.ci.determinism_50x3 \
     --profile dev \
     --seeds 50 \
     --runs 3 \
     --out reports/determinism_50x3/report.json
   ```

2. Проверка паритета новуса с легаси (выборка 500 пазлов, интервал Уилсона):

   ```bash
   python -m tools.ci.parity_500_wilson \
     --profile dev \
     --n 500 \
     --out reports/parity_500/report.json
   ```

Полученные артефакты и статусы PASS/FAIL прикладываются к PR. Дополнительные
NFR и shadow-отчёты описаны в [docs/STRATEGY.md](docs/STRATEGY.md) и
`docs/CODEX_GUIDE.md` (раздел «what/why/how-to-verify»).

## Configuration

Все ключевые параметры генерации головоломок и PDF-сборки теперь собраны в файле [`config.toml`](./config.toml).
Изменяйте значения в этом файле, чтобы управлять поведением скриптов без редактирования исходного кода.

## Compatibility notes

Сводка по политике совместимости и миграциям вынесена в файл
[`MIGRATIONS.md`](MIGRATIONS.md). Новые несовместимые изменения требуют ADR и
документирования шагов миграции до релиза.

> Verified on 2025-09-27

- Shadow comparison artifacts emit `sha256` hex digests (64 lowercase characters)
  for puzzle, trace, state and envelope fingerprints. Legacy `sha1` digests are
  no longer produced.
- Shadow sampling configuration now expects decimal strings (dot separator,
  ≤6 fractional digits). Numeric overrides continue to work with a deprecation
  warning during the transition period.
## Documentation

- [Стратегия развития](./docs/STRATEGY.md)
- [Puzzle Aesthetics Playbook v0](./docs/PUZZLE_AESTHETICS_PLAYBOOK.md)
