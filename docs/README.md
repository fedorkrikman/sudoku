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

## Validation Center API
- Код Validation Center расположен в [`src/contracts/`](../src/contracts). Экспортируются фасады `contracts.validator.validate`, `assert_valid`, `check_refs` и профили из `contracts.profiles`.
- Профиль строгости выбирается переменной `PUZZLE_VALIDATION_PROFILE` (`dev`|`ci`|`prod`) или передачей имени/конфига в фасад.
- Оркестратор и скрипты вызывают ЕВЦ только на границах стадий: перед сохранением Spec/CompleteGrid/Verdict/ExportBundle и перед рендером PDF — `check_refs`.

## Где искать контракты и артефакты
- Схемы: каталог [`PuzzleContracts/`](../PuzzleContracts), идентификаторы описаны в `catalog.json`.
- Артефакты: хранилище [`artifacts/`](../artifacts) с канонизированными JSON и идентификаторами `sha256-*`.
