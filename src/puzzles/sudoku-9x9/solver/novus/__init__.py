"""Nova solver package for the classic 9x9 Sudoku puzzle."""

from __future__ import annotations

import sys

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
    "StepHandler",
    "StepResult",
    "StepRunner",
    "StepTraceEntry",
    "StepTraceRecorder",
    "merge_deltas",
    "register_step",
]

NOVUS_MODULE = sys.modules[__name__]
__all__.append("NOVUS_MODULE")
