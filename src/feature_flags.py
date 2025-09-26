"""Runtime feature flag helpers."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

try:  # Python 3.11+
    import tomllib  # type: ignore[attr-defined]
except ModuleNotFoundError:  # pragma: no cover - fallback for older Python
    import tomli as tomllib  # type: ignore[import-untyped]

__all__ = ["is_shadow_mode_enabled", "reload"]

_FEATURES_FILENAME = "config/features.toml"


def _features_path() -> Path:
    return Path(__file__).resolve().parents[1] / _FEATURES_FILENAME


@lru_cache(maxsize=1)
def _load_features() -> dict[str, Any]:
    path = _features_path()
    if not path.exists():
        return {}
    with path.open("rb") as handle:
        return tomllib.load(handle)


def reload() -> None:
    """Clear the cached feature configuration."""

    _load_features.cache_clear()


def _coerce_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalised = value.strip().lower()
        if normalised in {"1", "true", "yes", "on"}:
            return True
        if normalised in {"0", "false", "no", "off"}:
            return False
    return None


def is_shadow_mode_enabled(env: Mapping[str, str] | None = None) -> bool:
    """Return ``True`` when the shadow mode feature flag is enabled."""

    features = _load_features()
    enabled = False

    entry = features.get("shadow_mode")
    if isinstance(entry, dict):
        value = entry.get("enabled")
        if isinstance(value, bool):
            enabled = value
    elif isinstance(entry, bool):
        enabled = entry

    if env:
        for key in ("PUZZLE_SHADOW_MODE_ENABLED", "SHADOW_MODE_ENABLED"):
            override = _coerce_bool(env.get(key))
            if override is not None:
                enabled = override
                break

    return enabled
