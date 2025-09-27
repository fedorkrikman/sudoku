"""Nova solver package for the classic 9x9 Sudoku puzzle."""

from __future__ import annotations

import importlib.util
import sys
from functools import lru_cache
from pathlib import Path

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


@lru_cache(maxsize=1)
def _legacy_commit_sha() -> str:
    repo_root = Path(__file__).resolve().parents[5]
    head_path = repo_root / ".git" / "HEAD"
    try:
        head = head_path.read_text("utf-8").strip()
    except OSError:
        return "unknown"
    if head.startswith("ref:"):
        ref = head.split(None, 1)[1]
        ref_path = repo_root / ".git" / ref
        try:
            return ref_path.read_text("utf-8").strip()[:40]
        except OSError:
            return "unknown"
    return head[:40]


def _load_legacy_module():
    module_name = "puzzle_sudoku_9x9_solver_legacy"
    if module_name in sys.modules:
        return sys.modules[module_name]
    legacy_path = Path(__file__).resolve().parents[1] / "legacy" / "__init__.py"
    spec = importlib.util.spec_from_file_location(module_name, legacy_path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise ImportError(f"Could not load legacy solver from {legacy_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def port_check_uniqueness(
    spec: dict,
    grid_or_candidate: dict,
    *,
    options: dict | None = None,
) -> dict:
    """Temporarily delegate the uniqueness port to the legacy solver."""

    legacy_module = _load_legacy_module()
    handler = getattr(legacy_module, "port_check_uniqueness")
    verdict = handler(spec, grid_or_candidate, options=options)
    if isinstance(verdict, dict):
        payload = dict(verdict)
        trace = payload.get("trace")
        if not isinstance(trace, dict):
            trace_map: dict[str, str] = {}
        else:
            trace_map = dict(trace)
        trace_map.setdefault("delegated_to", f"legacy@{_legacy_commit_sha()}")
        payload["trace"] = trace_map
        return payload
    return verdict
