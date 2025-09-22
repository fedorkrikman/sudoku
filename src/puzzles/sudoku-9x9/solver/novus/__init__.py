"""Compatibility alias for the Nova solver scaffold."""

from __future__ import annotations

import importlib
from types import ModuleType

_NOVUS_MODULE_NAME = "solver_nova"


def _load_novus() -> ModuleType:
    return importlib.import_module(_NOVUS_MODULE_NAME)


_novus = _load_novus()

__all__ = [
    name for name in getattr(_novus, "__all__", dir(_novus)) if not name.startswith("_")
]

for _name in __all__:
    globals()[_name] = getattr(_novus, _name)

NOVUS_MODULE = _novus
__all__.append("NOVUS_MODULE")
