from __future__ import annotations

from ports import solver_port


def _shadow_settings(profile: str = "dev", env: dict[str, str] | None = None) -> dict:
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
    _, resolved = solver_port.check_uniqueness(
        "sudoku-9x9",
        spec,
        grid,
        profile=profile,
        env=env,
    )
    return resolved.config["shadow"]


def test_cli_decimal_string_preserved() -> None:
    shadow = _shadow_settings(
        env={
            "CLI_SHADOW_ENABLED": "1",
            "CLI_SHADOW_SAMPLE_RATE": "0.333333",
        }
    )
    assert shadow["sample_rate"] == "0.333333"


def test_cli_decimal_string_too_precise_ignored() -> None:
    shadow = _shadow_settings(
        env={
            "CLI_SHADOW_ENABLED": "1",
            "CLI_SHADOW_SAMPLE_RATE": "0.1234567",
        }
    )
    # Fallback to profile default because the override is invalid.
    assert shadow["sample_rate"] == "0.25"
