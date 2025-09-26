from __future__ import annotations

from orchestrator.sampling import hit


def test_zero_rate_never_hits():
    assert hit("salt", "run", "stage", "seed", "module", 0.0) is False


def test_full_rate_always_hits():
    assert hit("salt", "run", "stage", "seed", "module", 1.0) is True


def test_deterministic_decision():
    decision_a = hit("salt", "run", "stage", "seed", "module", 0.5)
    decision_b = hit("salt", "run", "stage", "seed", "module", 0.5)
    assert decision_a == decision_b
