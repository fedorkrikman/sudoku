from __future__ import annotations

from decimal import Decimal

from orchestrator.sampling import hit


def test_zero_rate_never_hits():
    assert hit("salt", "run", "puzzle", Decimal("0"), sticky=False) is False


def test_full_rate_always_hits():
    assert hit("salt", "run", "puzzle", Decimal("1"), sticky=False) is True


def test_deterministic_decision():
    decision_a = hit("salt", "run", "puzzle", Decimal("0.5"), sticky=False)
    decision_b = hit("salt", "run", "puzzle", Decimal("0.5"), sticky=False)
    assert decision_a == decision_b
