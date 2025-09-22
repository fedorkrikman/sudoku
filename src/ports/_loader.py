"""Helpers for loading puzzle modules dynamically."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Dict

from orchestrator.router import ResolvedModule

_MODULE_CACHE: Dict[Path, ModuleType] = {}


def load_module(resolved: ResolvedModule) -> ModuleType:
    """Import the module described by ``resolved`` and cache the instance."""

    module_path = resolved.module_path.resolve()
    cached = _MODULE_CACHE.get(module_path)
    if cached is not None:
        return cached

    module_name = (
        f"puzzle_{resolved.puzzle_kind.replace('-', '_')}_"
        f"{resolved.role}_{resolved.impl_id}"
    )
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load module from {module_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    _MODULE_CACHE[module_path] = module
    return module


__all__ = ["load_module"]
