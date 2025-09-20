"""Utility helpers for loading project-wide configuration."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

try:  # Python 3.11+
    import tomllib  # type: ignore[attr-defined]
except ModuleNotFoundError:  # pragma: no cover - fallback for older Python
    import tomli as tomllib  # type: ignore[import-untyped]


_CONFIG_FILENAME = "config.toml"


def _config_path() -> Path:
    return Path(__file__).resolve().parents[1] / _CONFIG_FILENAME


@lru_cache(maxsize=1)
def get_config() -> Dict[str, Any]:
    """Load and cache the project configuration as a dictionary."""
    path = _config_path()
    try:
        with path.open("rb") as fh:
            return tomllib.load(fh)
    except FileNotFoundError as exc:  # pragma: no cover - defensive guard
        raise RuntimeError(
            f"Configuration file '{_CONFIG_FILENAME}' was not found next to the project root"
        ) from exc


def get_section(path: str, default: Any = None) -> Any:
    """Retrieve a nested configuration value using dotted notation."""

    data: Any = get_config()
    for part in path.split("."):
        if isinstance(data, dict) and part in data:
            data = data[part]
        else:
            if default is not None:
                return default
            raise KeyError(f"Configuration path '{path}' not found")
    return data


__all__ = ["get_config", "get_section"]
