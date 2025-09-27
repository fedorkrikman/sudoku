from __future__ import annotations

from ports import solver_port


def _spec_payload() -> tuple[dict, dict]:
    spec = {
        "name": "sudoku-9x9",
        "size": 9,
        "block": {"rows": 3, "cols": 3},
        "alphabet": list("123456789"),
        "limits": {"solver_timeout_ms": 1000},
    }
    grid = {
        "grid": (
            "123456789"
            "456789123"
            "789123456"
            "214365897"
            "365897214"
            "897214365"
            "531642978"
            "642978531"
            "978531642"
        )
    }
    return spec, grid


def _shadow(profile: str = "dev", env: dict[str, str] | None = None) -> dict:
    spec, grid = _spec_payload()
    _, resolved = solver_port.check_uniqueness(
        "sudoku-9x9",
        spec,
        grid,
        profile=profile,
        env=env,
    )
    return resolved.config["shadow"]


def test_sample_rate_is_clamped_high() -> None:
    shadow = _shadow(env={"SHADOW_SAMPLE_RATE": "2.5", "SHADOW_ENABLED": "1"})
    assert shadow["sample_rate"] == 1.0


def test_sample_rate_is_clamped_low() -> None:
    shadow = _shadow(env={"SHADOW_SAMPLE_RATE": "-0.5", "SHADOW_ENABLED": "1"})
    assert shadow["sample_rate"] == 0.0


def test_budget_override_accepts_positive_values() -> None:
    shadow = _shadow(env={"CLI_SHADOW_ENABLED": "1", "CLI_SHADOW_BUDGET_MS_P95": "25"})
    assert shadow["budget_ms_p95"] == 25


def test_invalid_boolean_preserves_default() -> None:
    shadow = _shadow(env={"CLI_SHADOW_ENABLED": "maybe"})
    assert shadow["enabled"] is False
