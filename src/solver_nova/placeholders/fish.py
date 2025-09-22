"""Placeholder for fish patterns (X-Wing/Swordfish/Jellyfish)."""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Tuple

from ..state_capsule import StateCapsule

Delta = Mapping[str, Any]
Metrics = Mapping[str, Any]


def step_fish(state: StateCapsule, params: Mapping[str, Any] | None = None) -> Tuple[Iterable[Delta], Metrics]:
    """TODO: implement X-Wing, Swordfish and Jellyfish search."""

    raise NotImplementedError("Fish patterns are not implemented yet.")


__all__ = ["step_fish"]
