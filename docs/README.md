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

## Где искать контракты и артефакты
- Схемы: каталог [`PuzzleContracts/`](../PuzzleContracts), идентификаторы описаны в `catalog.json`.
- Артефакты: хранилище [`artifacts/`](../artifacts) с канонизированными JSON и идентификаторами `sha256-*`.
