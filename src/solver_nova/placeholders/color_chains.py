"""Placeholder for colouring and forcing chain techniques."""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Tuple

from ..state_capsule import StateCapsule

Delta = Mapping[str, Any]
Metrics = Mapping[str, Any]


def step_color_chains(state: StateCapsule, params: Mapping[str, Any] | None = None) -> Tuple[Iterable[Delta], Metrics]:
    """TODO: implement colouring/forcing chain logic."""

    raise NotImplementedError("Coloring and forcing chain heuristics are not implemented yet.")


__all__ = ["step_color_chains"]
