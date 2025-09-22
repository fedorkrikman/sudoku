"""Branching support for the Nova solver."""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Tuple

from ..state_capsule import StateCapsule

Delta = Mapping[str, Any]
Metrics = Mapping[str, Any]


def step_branch(state: StateCapsule, params: Mapping[str, Any] | None = None) -> Tuple[Iterable[Delta], Metrics]:
    """Perform a branching decision (MRV-based backtracking).

    The implementation will eventually emit either concrete deltas or spawn new
    branching tasks for the orchestrator.  Until the behaviour is ported from
    the legacy solver this stub simply signals a skipped step.
    """

    raise NotImplementedError("Branching step is pending porting from legacy solver.")


__all__ = ["step_branch"]
