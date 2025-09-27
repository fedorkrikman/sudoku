from __future__ import annotations

from orchestrator import orchestrator


def test_shadow_counters_skip_when_rate_zero() -> None:
    overrides = {
        "PUZZLE_ROOT_SEED": "shadow-metrics-skip",
        "CLI_SHADOW_ENABLED": "1",
        "CLI_SHADOW_SAMPLE_RATE": "0.0",
    }
    result = orchestrator.run_pipeline(env_overrides=overrides)

    counters = result["shadow"]["counters"]
    assert counters["shadow_skipped"] == 1


def test_shadow_counters_ok_when_sampled() -> None:
    overrides = {
        "PUZZLE_ROOT_SEED": "shadow-metrics-ok",
        "CLI_SHADOW_ENABLED": "1",
        "CLI_SHADOW_SAMPLE_RATE": "1.0",
    }
    result = orchestrator.run_pipeline(env_overrides=overrides)

    counters = result["shadow"]["counters"]
    assert counters["shadow_ok"] == 1
    shadow_policy = result["modules"]["solver"]["shadow_policy"]
    assert shadow_policy["enabled"] is True
    assert shadow_policy["sample_rate"] == "1.0"
