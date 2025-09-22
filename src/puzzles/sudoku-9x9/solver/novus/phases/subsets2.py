"""Pair-based subset heuristics for Nova."""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Tuple

from ..state_capsule import StateCapsule

Delta = Mapping[str, Any]
Metrics = Mapping[str, Any]


def step_subsets2_pairs(
    state: StateCapsule, params: Mapping[str, Any] | None = None
) -> Tuple[Iterable[Delta], Metrics]:
    """Detect and apply Naked/Hidden Pair patterns.

    The concrete algorithm will be extracted from the legacy solver during a
    dedicated iteration.  Until then the step is marked as skipped by raising
    :class:`NotImplementedError`.
    """

    raise NotImplementedError("Subsets-2 step is pending porting from legacy solver.")


__all__ = ["step_subsets2_pairs"]
