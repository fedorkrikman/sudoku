"""Placeholder for unique rectangle heuristics."""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Tuple

from ..state_capsule import StateCapsule

Delta = Mapping[str, Any]
Metrics = Mapping[str, Any]


def step_uniques(state: StateCapsule, params: Mapping[str, Any] | None = None) -> Tuple[Iterable[Delta], Metrics]:
    """TODO: implement Unique Rectangle types I–IV."""

    raise NotImplementedError("Unique Rectangle heuristics are not implemented yet.")


__all__ = ["step_uniques"]
