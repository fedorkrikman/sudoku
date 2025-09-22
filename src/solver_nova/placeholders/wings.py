"""Placeholder for wing-based heuristics."""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Tuple

from ..state_capsule import StateCapsule

Delta = Mapping[str, Any]
Metrics = Mapping[str, Any]


def step_wings(state: StateCapsule, params: Mapping[str, Any] | None = None) -> Tuple[Iterable[Delta], Metrics]:
    """TODO: implement XY-Wing, XYZ-Wing and W-Wing detection."""

    raise NotImplementedError("Wing patterns are not implemented yet.")


__all__ = ["step_wings"]
