"""Compatibility shim exposing puzzle-first solver ports."""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

from ports.solver_port import check_uniqueness as _check_uniqueness


def check_uniqueness(
    puzzle_kind: str,
    spec: Dict[str, Any],
    grid_or_candidate: Dict[str, Any],
    *,
    options: Optional[Dict[str, Any]] = None,
    profile: str = "dev",
    env: Mapping[str, str] | None = None,
):
    """Delegate uniqueness checks to the shared puzzle router."""

    return _check_uniqueness(
        puzzle_kind,
        spec,
        grid_or_candidate,
        options=options,
        profile=profile,
        env=env,
    )


__all__ = ["check_uniqueness"]
