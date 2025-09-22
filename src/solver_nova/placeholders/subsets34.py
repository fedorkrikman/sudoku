"""Placeholder for triple/quad subset heuristics."""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Tuple

from ..state_capsule import StateCapsule

Delta = Mapping[str, Any]
Metrics = Mapping[str, Any]


def step_subsets34(state: StateCapsule, params: Mapping[str, Any] | None = None) -> Tuple[Iterable[Delta], Metrics]:
    """TODO: implement Naked/Hidden Triple/Quad detection."""

    raise NotImplementedError("Subsets-3/4 heuristics are not implemented yet.")


__all__ = ["step_subsets34"]
