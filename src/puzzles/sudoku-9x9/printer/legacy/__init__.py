"""Compatibility alias for the legacy Sudoku printer."""

from __future__ import annotations

import importlib
from types import ModuleType

_LEGACY_PRINTER_MODULE = "make_sudoku_pdf"


def _load_legacy() -> ModuleType:
    return importlib.import_module(_LEGACY_PRINTER_MODULE)


_legacy = _load_legacy()

__all__ = [
    name for name in getattr(_legacy, "__all__", dir(_legacy)) if not name.startswith("_")
]

for _name in __all__:
    globals()[_name] = getattr(_legacy, _name)

LEGACY_PRINTER_MODULE = _legacy
__all__.append("LEGACY_PRINTER_MODULE")
