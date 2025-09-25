"""Legacy printer implementation for Sudoku PDF export."""

from __future__ import annotations

from . import _impl as _legacy_module
from ._impl import *  # noqa: F401,F403 - re-export legacy surface

LEGACY_PRINTER_MODULE = _legacy_module

__all__ = [name for name in globals() if not name.startswith("_")]
