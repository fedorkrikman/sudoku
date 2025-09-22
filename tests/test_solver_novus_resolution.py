"""Smoke tests for resolving the novus solver implementation via the router."""

from __future__ import annotations

from orchestrator.router import resolve
from ports._loader import load_module


def test_novus_solver_resolves_and_exposes_port() -> None:
    env = {"PUZZLE_SOLVER_IMPL": "novus"}
    resolved = resolve("sudoku-9x9", "solver", "dev", env)

    assert resolved.impl_id == "novus"
    assert resolved.state == "shadow"
    assert not resolved.fallback_used

    module = load_module(resolved)

    assert module.DESCRIPTOR["impl_id"] == "novus"
    handler = getattr(module, "port_check_uniqueness")

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
    verdict = handler(spec, {"grid": solved_grid})

    assert verdict["unique"] is True
