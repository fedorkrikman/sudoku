"""Box–line interaction heuristics for Nova."""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Tuple

from ..state_capsule import StateCapsule

Delta = Mapping[str, Any]
Metrics = Mapping[str, Any]


def step_box_line(state: StateCapsule, params: Mapping[str, Any] | None = None) -> Tuple[Iterable[Delta], Metrics]:
    """Apply pointing/claiming box–line reductions.

    The real implementation will detect locked candidates (pointing/claiming)
    and return deterministic deltas.  The scaffold raises
    :class:`NotImplementedError` so that the ``StepRunner`` can mark the step as
    skipped in traces.
    """

    raise NotImplementedError("Box–line step is pending porting from legacy solver.")


__all__ = ["step_box_line"]
