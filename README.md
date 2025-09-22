# sudoku

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

## Contracts and artifacts

Схемы первого поколения лежат в каталоге [`PuzzleContracts/`](./PuzzleContracts).
Ключевые схемы: `Spec`, `CompleteGrid`, `Verdict` и `ExportBundle`. Общий конверт
поля описан в `_common/envelope-1.0.0.json`, а актуальные версии перечислены в
`catalog.json`.

Хранилище артефактов располагается в [`artifacts/`](./artifacts). Сохранение и
загрузка выполняются через `artifacts/artifact_store.py`, который канонизирует
JSON, вычисляет `artifact_id` вида `sha256-<hex>` и обеспечивает стабильные
пути хранения.

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