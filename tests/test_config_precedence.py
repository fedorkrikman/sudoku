from __future__ import annotations

from ports import solver_port


def _payload() -> tuple[dict, dict]:
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


def _shadow_settings(profile: str = "dev", env: dict[str, str] | None = None) -> dict:
    spec, grid = _payload()
    _, resolved = solver_port.check_uniqueness(
        "sudoku-9x9",
        spec,
        grid,
        profile=profile,
        env=env,
    )
    return resolved.config["shadow"]


def test_config_precedence_defaults() -> None:
    shadow = _shadow_settings()
    assert shadow["enabled"] is False
    assert shadow["secondary"] == "novus"
    assert shadow["primary"] == "legacy"
    assert shadow["sample_rate"] == 0.0


def test_environment_overrides_toml() -> None:
    shadow = _shadow_settings(env={"SHADOW_ENABLED": "1", "SHADOW_SAMPLE_RATE": "0.9"})
    assert shadow["enabled"] is True
    assert shadow["sample_rate"] == 0.9


def test_cli_overrides_environment() -> None:
    env = {
        "SHADOW_ENABLED": "0",
        "SHADOW_SAMPLE_RATE": "0.75",
        "CLI_SHADOW_ENABLED": "1",
        "CLI_SHADOW_SAMPLE_RATE": "0.5",
    }
    shadow = _shadow_settings(env=env)
    assert shadow["enabled"] is True
    assert shadow["sample_rate"] == 0.5


def test_profile_defaults_for_prod() -> None:
    shadow = _shadow_settings(profile="prod")
    assert shadow["sample_rate"] == 0.0
    assert shadow["enabled"] is False
