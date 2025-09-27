"""Runtime feature flag helpers."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

try:  # Python 3.11+
    import tomllib  # type: ignore[attr-defined]
except ModuleNotFoundError:  # pragma: no cover - fallback for older Python
    import tomli as tomllib  # type: ignore[import-untyped]

__all__ = ["get_shadow_feature", "is_shadow_mode_enabled", "reload"]

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


def get_shadow_feature(profile: str | None = None) -> dict[str, Any]:
    """Return the merged shadow feature block for the given profile."""

    features = _load_features()
    entry = features.get("shadow")
    merged: dict[str, Any] = {}
    if isinstance(entry, dict):
        for key, value in entry.items():
            if key == "by_profile":
                continue
            merged[key] = value

        if profile:
            by_profile = entry.get("by_profile")
            if isinstance(by_profile, dict):
                profile_key = profile.lower()
                profile_block = by_profile.get(profile_key)
                if isinstance(profile_block, dict):
                    for key, value in profile_block.items():
                        merged[key] = value
    return merged


def is_shadow_mode_enabled(env: Mapping[str, str] | None = None, *, profile: str | None = None) -> bool:
    """Return ``True`` when the shadow mode feature flag is enabled."""

    feature_block = get_shadow_feature(profile)
    enabled = bool(feature_block.get("enabled", False))

    if env:
        override_keys = (
            "CLI_SHADOW_ENABLED",
            "PUZZLE_SHADOW_ENABLED",
            "SHADOW_ENABLED",
            "PUZZLE_SHADOW_MODE_ENABLED",
            "SHADOW_MODE_ENABLED",
        )
        for key in override_keys:
            override = _coerce_bool(env.get(key))
            if override is not None:
                enabled = override
                break

    return enabled
