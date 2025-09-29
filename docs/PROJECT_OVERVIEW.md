# Project Overview — Puzzle Platform (v1)

## Зачем
Мы строим офлайн-платформу для генерации и проверки головоломок (старт: Sudoku 9×9; далее 16×16 и новые виды).
Цель: **детерминизируемый пайплайн** с артефактами JSON и чёткими контрактами между стадиями, чтобы расширять систему без переписывания.

## Что входит (Scope)
- Сквозной поток: **Spec → CompleteGrid → Verdict → Export (PDF)**.
- Контракты v1 в `PuzzleContracts/`, локальная валидация (ЕВЦ), локальное хранилище артефактов `artifacts/`.
- Оркестратор как «мозг процесса»; модули генератора/сольвера/экспорта как «исполнители».
- Детерминизм по (`Spec`,`seed`,`config`): одинаковые входы ⇒ одинаковые `artifact_id`.

## Чего нет (Non-Goals)
- Сетевых URL/онлайн-зависимостей.
- «Скрытых» обменов данными (только через артефакты).
- Разнородных правок в одном PR.

## Архитектурная стойка
Мы выбрали **вариант C**: скелет-пайплайн с централизованными контрактами.
Основные блоки:
- **Validation Center (`src/contracts/`)** — единственная точка проверок: JSON-Schema + инварианты + cross-refs. Профили: `dev|ci|prod`.
- **Artifact Store (`src/artifacts/`)** — канонизация JSON, `artifact_id = sha256-<hex>`, запись/чтение (`artifacts/<Type>/sha256-<hex>.json`).
- **Orchestrator (`src/orchestrator/`)** — сценарии стадий, `run_id`, дисциплина `seed`, метрики.
- **Generator / Solver / Export** — портовые адаптеры принимают/возвращают **только** артефакты.
- **Multitask Engine** — план (следующие итерации): пул процессов для «тяжёлых» стадий (uniqueness).

## Контракты артефактов v1
- **Spec** — топология пазла, алфавит, лимиты (обязателен Envelope).
- **CompleteGrid** — полное решение (row-major string + `canonical_hash`).
- **Verdict** — результат проверки уникальности/решения.
- **ExportBundle** — только ссылки (`*_ref`) + параметры рендера.
Все схемы имеют `$id = urn:puzzle:schemas/<type>:1.0.0`. Envelope обязателен.

## Детерминизм и Seed
`artifact_id` вычисляется из **канонизированного** JSON без `artifact_id`.
Seed выводится как `derive_seed(root_seed, stage, parent_id)` и сохраняется в Envelope.

## Рабочие профили
- **dev** — полная проверка; WARN не валит.
- **ci** — как dev, но WARN=ERROR.
- **prod** — Envelope + ключевые инварианты + cross-refs, тяжёлые проверки как WARN.

## Дерево проекта (кратко)
PuzzleContracts/ (схемы, fixtures, catalog.json)
artifacts/ (контент-адресные JSON файлы)
src/
artifacts/ (artifact_store.py)
contracts/ (loader, rulebook, profiles, errors, validator)
orchestrator/ (orchestrator.py)
scripts/ (check_contracts.py, smoke_determinism.py)
docs/ (Guide, Roadmap, ADR)


## Как развиваем
- Новая функция = новая стадия/артефакт, а не `if` в существующей.
- Слом схем/контрактов оформляется через ADR + миграцию; по умолчанию живём в линии **v1.x**.
- PR обязателен к прохождению офлайн-проверок (см. `scripts/`).

Связанные документы: [`docs/CODEX_GUIDE.md`](./CODEX_GUIDE.md), [`docs/GOALS_ROADMAP.md`](./GOALS_ROADMAP.md), ADR-0001/0002.
