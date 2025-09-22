"""Placeholder for ALS (Almost Locked Sets) techniques."""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Tuple

from ..state_capsule import StateCapsule

Delta = Mapping[str, Any]
Metrics = Mapping[str, Any]


def step_als(state: StateCapsule, params: Mapping[str, Any] | None = None) -> Tuple[Iterable[Delta], Metrics]:
    """TODO: implement ALS/ALS-XZ detectors."""

    raise NotImplementedError("ALS family heuristics are not implemented yet.")


__all__ = ["step_als"]
