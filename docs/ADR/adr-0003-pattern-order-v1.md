# ADR-0003: Pattern Order v1

## Контекст

Nova-сольвер требует стабильного и документированного порядка применения
эвристик. Это условие необходимо для соблюдения детерминизма при различной
конфигурации исполнителей и для сопоставления трасс между legacy и Nova.

## Решение

- Введён канонический порядок фаз:
  1. PROPAGATE: Peer elimination → Naked Single → Hidden Single
  2. SUBSETS₂: Naked Pair → Hidden Pair
  3. BOX–LINE: Pointing → Claiming
  4. SUBSETS₃/₄: Naked/Hidden Triple → Naked/Hidden Quad
  5. FISH: X-Wing → Swordfish → Jellyfish
  6. WINGS: XY-Wing → XYZ-Wing → W-Wing
  7. UNIQUES: Unique Rectangle (I–IV)
  8. COLOR/CHAINS: Simple Coloring/Bi-coloring → Forcing Chains → 2-String Kite
  9. ALS: ALS, ALS-XZ и производные
  10. BRANCH: Backtracking (MRV; тай-брейки row→col→digit)
- Любое изменение порядка требует обновления версии ADR и согласованной миграции
  фикстур.
- StepRunner обязан исполнять шаги строго в указанной последовательности.

## Последствия

- Трассы Nova становятся воспроизводимыми независимо от backend'а исполнителя.
- Тесты эквивалентности и золотые пары опираются на версию порядка.
- Новые эвристики добавляются только после обновления этого ADR.
