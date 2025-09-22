# GOALS_ROADMAP

## 1. Обозримые цели (6–8 недель)

| Итерация | Цель | Ключевые результаты (KR) | Acceptance (проверка) | Статус |
| --- | --- | --- | --- | --- |
| A | Validation Center v1 — **polish** | `src/contracts/{loader,rulebook,profiles,errors,validator}.py` на месте и импортируются; оркестратор вызывает `assert_valid` на входе/выходе; профили `dev/ci/prod`; скрипты переведены на ЕВЦ | `check_contracts.py` зелёный в `dev` и падает на WARN в `ci`; `smoke_determinism.py` зелёный; grep показывает вызовы `assert_valid` на всех границах | ☑ In progress |
| B | CandidatePuzzle + Aesthetics | Артефакт `CandidatePuzzle v1` и схема; стадия `carve.clues` (политика симметрии); solver принимает `CandidatePuzzle`; экспорт включает ссылку на `CandidatePuzzle` | Валидация `CandidatePuzzle` проходит; Aesthetics-проверки фильтруют несимметричные; пайплайн G→S→P использует `CandidatePuzzle` | ☐ Planned |
| C | DifficultyProfile v1 | Артефакт `DifficultyProfile v1` и схема; базовый скоринг; экспорт сложности | Валидация `DifficultyProfile`; экспорт PDF включает оценку; солвер умеет выдавать данные для скоринга | ☐ Planned |
| D | Multitask Engine (uniqueness pool) | Пул процессов; политика fan-out/backpressure; тайм-ауты; метрики пула | Uniqueness выполняется через пул; стабильный результат; ускорение p95 ≥ X% на локальной машине | ☐ Planned |
| E | Sudoku-16×16 Spec | `Spec` 16×16 (алфавит 0–9,A–F, блок 4×4); E2E прогон; SLA p95 для uniqueness | Пайплайн 16×16 проходит end-to-end; фиксированные артефакты в `artifacts/`; SLA задокументирован | ☐ Planned |

## 2. Долговременные принципы (опоры)
- Контракты важнее реализаций: изменения контрактов фиксируются ADR.
- Детерминизм и воспроизводимость: один seed — один результат.
- Стадийность: новая функция — отдельная стадия/артефакт, а не условный блок.
- Минимум глобального состояния, максимум явных зависимостей.

## 3. Dependencies & Risks
- B зависит от завершения A (ЕВЦ на границах). Риск: появление проверок вне ЕВЦ.
- D зависит от стабильных портов Solver и дисциплины seed. Риск: недетерминизм при параллелизме.
- E зависит от генератора/солвера, масштабируемых под 16×16. Риск: время uniqueness.

**Как обновлять:** любое изменение статуса/KR/acceptance — отдельный коммит: `docs: roadmap status update`.
