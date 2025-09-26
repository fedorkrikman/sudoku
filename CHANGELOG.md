# Changelog

## 2025-09-26 — docs: mini-repair + strategy anchor

- README обновлён: раздел «How to verify locally», якорь совместимости и дата проверки.
- Добавлен `docs/STRATEGY.md` с целями (guardrail/SLO/North-Star) и принципами.
- Обновлён `docs/GOALS_ROADMAP.md` (acceptance-гейты итерации).
- `docs/CODEX_GUIDE.md` дополнен правилами ведения документации и примерами Envelope/ArtifactRef.
- ADR `docs/ADR/ShadowSampling.md` зафиксировал статус Accepted и авто-регулировку sample_rate.
- Обновлена спецификация `docs/logging/shadowlog_v1.md` (нормализация, severity-map).
- Добавлен immutable acceptance-корпус `data/acceptance/acceptance_corpus_9x9_v1.json` и генератор.
- Внесены CI-скрипты `tools/ci/*` и workflow'ы для determinism/parity/NFR/shadow отчётов.
- Добавлен `.markdownlint.json` и doc-линт в `docs` workflow.
