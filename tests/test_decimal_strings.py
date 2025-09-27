from decimal import Decimal

import pytest

from orchestrator import orchestrator
from ports import solver_port


def test_shadow_sample_rate_uses_decimal_strings() -> None:
    overrides = {
        "PUZZLE_ROOT_SEED": "decimal-strings-1",
        "CLI_SHADOW_ENABLED": "1",
        "CLI_SHADOW_SAMPLE_RATE": "0.333333",
    }
    result = orchestrator.run_pipeline(env_overrides=overrides)
    policy = result["modules"]["solver"]["shadow_policy"]
    assert policy["sample_rate"] == "0.333333"
    assert isinstance(policy["sample_rate"], str)


def test_numeric_shadow_sample_rate_emits_warning() -> None:
    with pytest.warns(RuntimeWarning):
        value = solver_port._parse_decimal(0.5)  # type: ignore[attr-defined]
    assert isinstance(value, Decimal)
