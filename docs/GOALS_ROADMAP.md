# GOALS_ROADMAP

## 1. Обозримые цели (6–8 недель)
| Итерация | Цель | Ключевые результаты (KR) | Статус |
| --- | --- | --- | --- |
| A | Validation Center v1 | `src/contracts/{loader,rulebook,profiles,errors,validator}.py`; оркестратор вызывает `assert_valid` на входе/выходе; профили dev/ci/prod; скрипты переведены на ЕВЦ | ☑ In progress |
| B | CandidatePuzzle + Aesthetics | Артефакт CandidatePuzzle v1; стадия `carve.clues`; проверка симметрии; solver принимает Candidate | ☐ Planned |
| C | DifficultyProfile v1 | Артефакт сложности; экспорт оценки; базовый скоринг | ☐ Planned |
| D | Multitask Engine (uniqueness pool) | Пул процессов; политика fan-out; backpressure; timeouts | ☐ Planned |
| E | Sudoku-16×16 Spec | Spec 16×16; запуск конвейера E2E; SLA p95 для uniqueness | ☐ Planned |

## 2. Долговременные принципы (опоры)
- Контракты важнее реализаций: изменения контрактов фиксируются ADR.
- Детерминизм и воспроизводимость: один seed — один результат.
- Стадийность: новая функция оформляется как отдельная стадия или артефакт, а не условный блок в существующей.
- Минимум глобального состояния, максимум явных зависимостей.

**Как обновлять:** любое изменение статуса или цели оформляется отдельным коммитом с сообщением `docs: roadmap status update`.
