"""Execution scaffold for Nova solver steps."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Mapping, MutableMapping, Optional, Tuple

from .delta import Delta, canonicalise_deltas, ensure_delta
from .state_capsule import StateCapsule

StepHandler = Callable[[StateCapsule, Mapping[str, Any] | None], Tuple[Iterable[Delta | Mapping[str, Any]], Mapping[str, Any]]]


@dataclass(frozen=True)
class StepTraceEntry:
    """Single record emitted for a solver step.

    The scaffold keeps the structure intentionally flexible.  Concrete
    implementations will extend ``meta`` with pattern identifiers, affected
    cells and other metrics required by the deterministic trace protocol.
    """

    step_kind: str
    step_name: str
    meta: Mapping[str, Any]


@dataclass(frozen=True)
class StepResult:
    """Container with the outcome of a step execution."""

    state: StateCapsule
    deltas: Tuple[Delta, ...]
    metrics: Mapping[str, Any]


@dataclass
class StepTraceRecorder:
    """In-memory trace accumulator respecting ``TRACE_LEVEL`` semantics."""

    trace_level: str = "none"
    entries: List[StepTraceEntry] = field(default_factory=list)

    def record(self, entry: StepTraceEntry) -> None:
        if self.trace_level == "none":
            return
        self.entries.append(entry)

    def snapshot(self) -> Tuple[StepTraceEntry, ...]:
        return tuple(self.entries)

    def reset(self) -> None:
        self.entries.clear()


_STEP_REGISTRY: Dict[str, Dict[str, StepHandler]] = {
    "PROPAGATE": {},
    "HEURISTICS": {},
    "BRANCH": {},
}


def register_step(step_kind: str, name: str, handler: StepHandler) -> None:
    """Register a step handler for the Nova runner.

    The helper enables modules to register their detectors without creating
    import cycles.  The registry is intentionally simple; complex ordering and
    capability rules will be added together with real implementations.
    """

    if step_kind not in _STEP_REGISTRY:
        raise ValueError(f"Unsupported step kind: {step_kind!r}")
    _STEP_REGISTRY[step_kind][name] = handler


def merge_deltas(state: StateCapsule, deltas: Iterable[Delta | Mapping[str, Any]]) -> Tuple[StateCapsule, Tuple[Delta, ...]]:
    """Merge produced deltas into a new state capsule.

    Even though the current Nova scaffold does not yet mutate the solver state,
    we already enforce the canonical ordering described in the Delta v1
    contract.  This keeps the deterministic behaviour stable for downstream
    consumers (trace writers, difficulty scoring) and reduces the surface for
    subtle bugs once mutations are implemented.

    Parameters
    ----------
    state:
        Immutable :class:`StateCapsule` describing the solver state prior to
        applying the deltas.  The capsule is returned unchanged – the actual
        merge logic will be introduced together with the full solver port.
    deltas:
        Arbitrary iterable of delta descriptors.  Handlers may yield either
        :class:`Delta` instances or plain mappings that contain ``op``,
        ``cell`` and ``digit`` keys.  The helper normalises them and returns a
        tuple sorted according to the canonical ordering rules
        (``ELIM`` < ``PLACE``; then by ``cell`` and ``digit``).

    Returns
    -------
    Tuple[StateCapsule, Tuple[Delta, ...]]
        The untouched state capsule and the canonicalised deltas.
    """

    canonical = canonicalise_deltas(ensure_delta(delta) for delta in deltas)
    return state, canonical


class StepRunner:
    """Coordinator that executes Nova solver steps sequentially."""

    def __init__(
        self,
        *,
        trace_level: str = "none",
        trace_recorder: Optional[StepTraceRecorder] = None,
    ) -> None:
        self.trace_recorder = trace_recorder or StepTraceRecorder(trace_level=trace_level)

    def run_step(
        self,
        state: StateCapsule,
        step_kind: str,
        *,
        params: Mapping[str, Any] | None = None,
    ) -> StepResult:
        """Execute a single solver step and return the resulting state.

        Parameters
        ----------
        state:
            Current immutable capsule representing the solver state.
        step_kind:
            One of ``"PROPAGATE"``, ``"HEURISTICS"`` or ``"BRANCH"``.  The
            specific callable is resolved via :func:`register_step`.
        params:
            Optional configuration passed to the underlying handler.  The
            scaffold expects a ``name`` field designating the registered step.
        """

        params = params or {}
        step_name = str(params.get("name", "undefined"))
        handler = _STEP_REGISTRY.get(step_kind, {}).get(step_name)
        if handler is None:
            return self._skip(state, step_kind, step_name, reason="unregistered")

        try:
            raw_deltas, metrics = handler(state, params)
        except NotImplementedError:
            return self._skip(state, step_kind, step_name, reason="not-implemented")

        new_state, deltas = merge_deltas(state, raw_deltas)
        metrics_payload: Mapping[str, Any] | None = metrics
        metrics_dict = dict(metrics_payload) if metrics_payload is not None else {}
        result = StepResult(state=new_state, deltas=deltas, metrics=metrics_dict)
        self._record(step_kind, step_name, {"status": "ok", **result.metrics})
        return result

    # Internal helpers -------------------------------------------------

    def _skip(
        self,
        state: StateCapsule,
        step_kind: str,
        step_name: str,
        *,
        reason: str,
    ) -> StepResult:
        metrics: MutableMapping[str, Any] = {"status": "skipped", "reason": reason}
        self._record(step_kind, step_name, metrics)
        return StepResult(state=state, deltas=tuple(), metrics=metrics)

    def _record(self, step_kind: str, step_name: str, meta: Mapping[str, Any]) -> None:
        entry = StepTraceEntry(step_kind=step_kind, step_name=step_name, meta=dict(meta))
        self.trace_recorder.record(entry)


__all__ = [
    "StepHandler",
    "StepResult",
    "StepRunner",
    "StepTraceEntry",
    "StepTraceRecorder",
    "merge_deltas",
    "register_step",
]
