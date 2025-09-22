"""Compatibility shim for the relocated Nova solver package."""

from __future__ import annotations

import importlib.util
import logging
import sys
from pathlib import Path
from types import ModuleType

_LOGGER = logging.getLogger(__name__)
_TARGET_MODULE_NAME = "puzzle_sudoku_9x9_solver_novus"
_TARGET_MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "puzzles"
    / "sudoku-9x9"
    / "solver"
    / "novus"
    / "__init__.py"
)


def _load_target() -> ModuleType:
    cached = sys.modules.get(_TARGET_MODULE_NAME)
    if cached is not None:
        return cached

    spec = importlib.util.spec_from_file_location(_TARGET_MODULE_NAME, _TARGET_MODULE_PATH)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive guard
        raise ImportError(f"Unable to load Nova solver from '{_TARGET_MODULE_PATH}'")

    module = importlib.util.module_from_spec(spec)
    sys.modules[_TARGET_MODULE_NAME] = module
    spec.loader.exec_module(module)
    return module


_target = _load_target()
_LOGGER.warning("solver_nova is deprecated; use puzzles.sudoku-9x9.solver.novus")

__all__ = [
    name for name in getattr(_target, "__all__", dir(_target)) if not name.startswith("_")
]

for _name in __all__:
    globals()[_name] = getattr(_target, _name)
