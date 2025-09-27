# CODEX_GUIDE

> Verified on 2025-09-27

## 1. Назначение и область действия
Документ адресован Codex, работающему в IDE над изменениями в этом репозитории. Руководство описывает ожидания к структуре PR, проверкам и артефактам. В объём не входят сетевые вызовы или добавление URL, самостоятельные переименования без соответствующего ADR и задачи вне этого репозитория.

## 2. Инварианты архитектуры (не нарушать)
- Артефакты создаются только через Artifact Store, идентификатор имеет вид `sha256-…`, JSON канонизируется.
- Все стыки проходят через Единый Валидационный Центр: `validate`/`assert_valid` вызываются на входе и выходе стадий.
- Порты стадий детерминированы, не имеют сайд-эффектов и принимают/возвращают только артефакты по утверждённым схемам.
- `ExportBundle` содержит только ссылки (`*_ref`), рендер читает данные исключительно через стор.
- Кросс-ссылочные проверки в Rulebook разрешено выполнять только через `artifact_store.load_artifact`.
- Имена файлов Windows-safe: символ `:` недопустим.
- Никаких разнородных правок в одном PR: один смысл — один PR.

## 3. Контракты и версии
- Схемы расположены в `PuzzleContracts/schemas/**`, каждая имеет `$id = urn:puzzle:schemas/<type>:<version>`.
- Envelope обязателен: все артефакты несут поля `artifact_id`, `artifact_type`, `artifact_version`, `created_at` и `payload`.
- Любая несовместимая правка требует ADR и миграции; базовая линия — версия v1.x.

## 4. Профили валидации
- Профили: `dev` (по умолчанию), `ci` (интерпретирует WARN как ERROR), `prod` (облегчённые второстепенные проверки).
- Переключение выполняется через переменную окружения `PUZZLE_VALIDATION_PROFILE` или параметр фасадов Validation Center; пустое значение приравнивается к `dev`.

## 4.1 Validation Center API
- Код ЕВЦ расположен в `src/contracts/` и состоит из слоёв: `loader`, `rulebook`, `profiles`, `errors`, `validator`.
- Основные фасады: `contracts.validator.validate`, `contracts.validator.assert_valid`, `contracts.validator.check_refs` и `contracts.profiles.get_profile`.
- Вызовы выполняются только на границах стадий (вход/выход артефактов и быстрый `check_refs` перед рендером PDF). Дополнительная валидация внутри стадий запрещена.
- Rulebook хранит полный набор правил версии v1: инварианты по артефактам и кросс-ссылки, опирающиеся на `artifact_store`.

## 5. Оркестратор и многозадачность — границы
- Оркестратор не содержит доменной логики; он управляет типами артефактов и стадиями.
- Многозадачность — способ исполнения. Вход задачи имеет форму `{stage, input_artifact_id, seed, options}`.

## 6. Правила ветвления/коммитов/PR
- Ветки называются `codex/<feature-kebab>`.
- Коммиты — в императивном наклонении, небольшими партиями и без смешения смыслов.
- Каждый PR включает описание цели, ссылки на разделы этого руководства и `docs/GOALS_ROADMAP.md`, а также чек-лист DoD (см. шаблон PR).

## 7. [HANDOFF] блок в описаниях PR
Формируйте [HANDOFF] из 3–6 пунктов с конкретными шагами для Codex: создание файлов, добавление портов, обновление README/ADR и т. п. Без кода и Git-деталей.

## 8. Запрещено
- Менять схемы без обновления `catalog.json` и соответствующего ADR.
- Встраивать логику валидации внутрь стадий: все проверки проходят через ЕВЦ.
- Добавлять сетевые зависимости или URL.

## 9. Мини-чек-лист для каждого PR
- Валидация артефактов проходит (`scripts/check_contracts.py`).
- Детерминизм проверен (`scripts/smoke_determinism.py`).
- Скрипты из пунктов выше прогнаны минимум в профилях `dev` и `ci`.
- README и ADR обновлены при изменении инвариантов или процессов.
- Нет смешения несвязанных изменений.

## 10. Документация: правила ведения

- Ключевые файлы стратегии/процессов содержат строку `> Verified on YYYY-MM-DD`
  с датой последней проверки.
- Каждая док-страница отвечает на вопросы **what / why / how-to-verify** и
  содержит ссылки на артефакты/репорты.
- Док-PR сопровождается записью в CHANGELOG и ссылкой на секцию roadmap/strategy.
- Нарушение правил фиксируется в ADR и в `MIGRATIONS.md`, если затрагивается
  совместимость.
- Markdown оформляется под правила `.markdownlint.json`; прогонять
  `docs`-workflow локально перед пушем.

### Envelope и ArtifactRef

```json
{
  "ts":"2025-09-26T03:31:30.000Z",
  "run_id":"12b52c61-5f3a-4d7d-a7cb-cc1bb4d0f2e1",
  "profile":"dev",
  "solver_id":"novus-sudoku",
  "commit_sha":"9b4f1b7c...",
  "baseline_sha":"8123cc5a...",
  "hw_fingerprint":"3d45ce…",
  "seq":1
}
```

```json
{
  "kind":"json",
  "digest":"sha256-411605a5…",
  "uri":"artifacts/CompleteGrid/sha256-411605a5….json",
  "size":2048,
  "media_type":"application/json",
  "compression":"none"
}
```

### JCS-канонизация

| До | После |
| --- | --- |
| `{"b":2,"a":1}` | `{"a":1,"b":2}` |
| `{"text":"Ä"}` | `{"text":"Ä"}` |

Используем `artifact_store.canonicalize` либо `json.dumps(..., sort_keys=True,
separators=(",", ":"), ensure_ascii=False)` для отчётов и артефактов.

### Shadow-mode dev-loop

- Активировать тень можно флагом `--enable-shadow` (CLI) или установкой
  `shadow_mode.enabled=true` в `config/features.toml`.
- Для единичного прогона используйте `python -m tools.cli.orchestrate run-one --seed <hex> --profile dev --enable-shadow [--shadow-rate <r>]`.
- Для серии сидов: `python -m tools.cli.orchestrate batch-seeds seeds.txt --profile dev --enable-shadow`.
- Сводку по логам собирает `python -m tools.cli.orchestrate report-shadow logs/shadow --top 10`.
- Ключевые метрики: `severity`, `kind`, `timings.overhead_pct`. Если `overhead_pct`
  стабильно > 0.05 — уменьшить `sample_rate` или проверить `policy.shadow.recommend_action`.
