"""Propagation phase entry points for Nova solver."""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Tuple

from ..state_capsule import StateCapsule

Delta = Mapping[str, Any]
Metrics = Mapping[str, Any]


def step_propagate(state: StateCapsule, params: Mapping[str, Any] | None = None) -> Tuple[Iterable[Delta], Metrics]:
    """Execute basic propagation routines (peer elimination, singles).

    Parameters
    ----------
    state:
        Immutable solver state capsule.
    params:
        Optional execution hints.  The scaffold ignores them for now.

    Returns
    -------
    Tuple[Iterable[Delta], Metrics]
        A sequence of deltas describing state changes and metrics gathered
        during execution.

    Notes
    -----
    The actual implementation will be ported from the legacy solver.  Until
    then the function raises :class:`NotImplementedError` which is interpreted
    by the ``StepRunner`` as a skipped step.
    """

    raise NotImplementedError("Propagation step is pending porting from legacy solver.")


__all__ = ["step_propagate"]
