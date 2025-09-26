# Changelog

# 2025-09-26 — feat(orchestrator): shadow compare runtime & tooling

- Добавлены runtime-утилиты `contracts.jsoncanon`, `contracts.artifacts`, `contracts.envelope`.
- Реализованы `orchestrator.sampling`, обновлённый `shadow_compare.run_with_shadow` и JSONL-логгер с ротацией.
- Введены CLI-команды `tools.cli.orchestrate` и отчёт `tools.reports.mismatch_report`.
- Добавлена политика авто-регулировки в `policy.shadow` и тесты для канонизации/семплинга/shadow-mode.
- Документация (`README`, `docs/CODEX_GUIDE.md`, `docs/logging/shadowlog_v1.md`) дополнена разделами про shadow-mode.

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
