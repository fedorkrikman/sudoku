"""Backward-compatible shim for the legacy Sudoku solver module."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_TARGET_MODULE = "puzzle_sudoku_9x9_solver_legacy"
_TARGET_PATH = (
    Path(__file__).resolve().parent
    / "puzzles"
    / "sudoku-9x9"
    / "solver"
    / "legacy"
    / "__init__.py"
)

_spec = importlib.util.spec_from_file_location(_TARGET_MODULE, _TARGET_PATH)
if _spec is None or _spec.loader is None:  # pragma: no cover - defensive guard
    raise ImportError(f"Unable to load legacy solver from '{_TARGET_PATH}'")

_module = importlib.util.module_from_spec(_spec)
sys.modules[_TARGET_MODULE] = _module
_spec.loader.exec_module(_module)

globals().update({name: getattr(_module, name) for name in dir(_module) if not name.startswith("_")})

__all__ = [name for name in globals() if not name.startswith("_")]
