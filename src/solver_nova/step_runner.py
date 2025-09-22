"""Execution scaffold for Nova solver steps."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Mapping, MutableMapping, Optional, Tuple

from .state_capsule import StateCapsule

StepHandler = Callable[[StateCapsule, Mapping[str, Any] | None], Tuple[Iterable[Mapping[str, Any]], Mapping[str, Any]]]


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
    deltas: Tuple[Mapping[str, Any], ...]
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


def merge_deltas(state: StateCapsule, deltas: Iterable[Mapping[str, Any]]) -> StateCapsule:
    """Merge produced deltas into a new state capsule.

    The scaffold keeps the merge logic trivial – deltas are not applied yet and
    the state is returned verbatim.  Future iterations will implement
    deterministic, key-based merging once the delta protocol is formalised.
    """

    _ = tuple(deltas)  # Force iteration for determinism even without applying.
    return state


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

        deltas = tuple(raw_deltas)
        new_state = merge_deltas(state, deltas)
        result = StepResult(state=new_state, deltas=deltas, metrics=dict(metrics))
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
