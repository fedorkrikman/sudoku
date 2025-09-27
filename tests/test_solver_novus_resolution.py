"""Smoke tests for resolving the novus solver implementation via the router."""

from __future__ import annotations

from orchestrator.router import resolve
from ports import solver_port
from ports._loader import load_module


def _solved_spec() -> tuple[dict, dict]:
    solved_grid = (
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
    spec = {
        "name": "sudoku-9x9",
        "size": 9,
        "block": {"rows": 3, "cols": 3},
        "alphabet": list("123456789"),
        "limits": {"solver_timeout_ms": 1000},
    }
    return spec, {"grid": solved_grid}


def test_novus_solver_resolves_and_exposes_port() -> None:
    env = {"CLI_PUZZLE_SOLVER_IMPL": "novus"}
    resolved = resolve("sudoku-9x9", "solver", "dev", env)

    assert resolved.impl_id == "novus"
    assert resolved.state == "shadow"
    assert not resolved.fallback_used

    module = load_module(resolved)

    assert module.DESCRIPTOR["impl_id"] == "novus"
    handler = getattr(module, "port_check_uniqueness")

    spec, grid = _solved_spec()
    verdict = handler(spec, grid)

    assert verdict["unique"] is True
    trace = verdict.get("trace")
    assert isinstance(trace, dict)
    assert trace["delegated_to"].startswith("legacy@")


def test_solver_port_merges_shadow_policy() -> None:
    spec, grid = _solved_spec()
    payload, resolved = solver_port.check_uniqueness(
        "sudoku-9x9",
        spec,
        grid,
        profile="dev",
        env={"CLI_SHADOW_ENABLED": "1"},
    )

    assert payload["unique"] is True
    assert resolved.impl_id == "legacy"
    shadow_cfg = resolved.config.get("shadow")
    assert shadow_cfg["enabled"] is True
    assert shadow_cfg["secondary"] == "novus"
    assert 0.0 <= shadow_cfg["sample_rate"] <= 1.0
