# sudoku

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
   сформированы legacy-путём.

   ```bash
   PUZZLE_VALIDATION_PROFILE=dev \
   PUZZLE_SOLVER_STATE=shadow \
   PUZZLE_SOLVER_IMPL=novus \
   PYTHONPATH=src \
   python -m orchestrator.orchestrator \
     --puzzle sudoku-9x9 \
     --output-dir exports_shadow
   ```

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

## Configuration

Все ключевые параметры генерации головоломок и PDF-сборки собраны в файле
[`config.toml`](./config.toml). Изменяйте значения в этом файле, чтобы управлять
поведением скриптов без редактирования исходного кода.