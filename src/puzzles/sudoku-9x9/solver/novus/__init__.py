"""Nova solver package for the classic 9x9 Sudoku puzzle."""

from __future__ import annotations

import sys

import importlib

from .delta import (
    Delta,
    DeltaLike,
    DeltaOp,
    DeltaValidationError,
    canonicalise_deltas,
    ensure_delta,
    validate_deltas,
)
from .state_capsule import StateCapsule
from .step_runner import (
    StepHandler,
    StepResult,
    StepRunner,
    StepTraceEntry,
    StepTraceRecorder,
    merge_deltas,
    register_step,
)
from .trace import SolveTrace, SolveTraceEntry as SolveTraceRecord, TraceValidationError

# Trigger step registration on import.
from . import phases as _phases  # noqa: F401
from . import placeholders as _placeholders  # noqa: F401

DESCRIPTOR = {
    "module_id": "sudoku-9x9:solver/novus@1.0.0",
    "puzzle_kind": "sudoku-9x9",
    "role": "solver",
    "impl_id": "novus",
    "module_version": "1.0.0",
    "contracts": "^1.0",
    "capabilities": {"parallelizable": False, "idempotent": True, "stateless": False},
}

__all__ = [
    "DESCRIPTOR",
    "StateCapsule",
    "Delta",
    "DeltaLike",
    "DeltaOp",
    "DeltaValidationError",
    "canonicalise_deltas",
    "ensure_delta",
    "validate_deltas",
    "StepHandler",
    "StepResult",
    "StepRunner",
    "StepTraceEntry",
    "StepTraceRecorder",
    "merge_deltas",
    "register_step",
    "SolveTrace",
    "SolveTraceRecord",
    "TraceValidationError",
    "port_check_uniqueness",
]

NOVUS_MODULE = sys.modules[__name__]
__all__.append("NOVUS_MODULE")


def port_check_uniqueness(
    spec: dict,
    grid_or_candidate: dict,
    *,
    options: dict | None = None,
) -> dict:
    """Temporarily delegate the uniqueness port to the legacy solver."""

    legacy_module = importlib.import_module("sudoku_solver")
    handler = getattr(legacy_module, "port_check_uniqueness")
    return handler(spec, grid_or_candidate, options=options)
