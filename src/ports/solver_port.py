"""Facade for solver implementations across puzzles."""

from __future__ import annotations

from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

try:  # Python 3.11+
    import tomllib  # type: ignore[attr-defined]
except ModuleNotFoundError:  # pragma: no cover - fallback for older Python
    import tomli as tomllib  # type: ignore[import-untyped]

from orchestrator.router import ResolvedModule, resolve

from ._loader import load_module
from ._utils import build_env


@dataclass(frozen=True)
class ShadowSettings:
    """Finalised shadow policy after precedence resolution."""

    enabled: bool
    sample_rate: float
    primary: str
    secondary: str
    log_mismatch: bool
    budget_ms_p95: int


_PROFILE_SAMPLE_DEFAULTS = {
    "dev": 0.25,
    "test": 0.25,
    "pilot": 1.0,
    "prod": 0.0,
}


def _features_path() -> Path:
    return Path(__file__).resolve().parents[2] / "config" / "features.toml"


@lru_cache(maxsize=1)
def _load_features() -> Dict[str, Any]:
    path = _features_path()
    if not path.exists():
        return {}
    with path.open("rb") as handle:
        return tomllib.load(handle)


def _parse_bool(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalised = value.strip().lower()
        if normalised in {"1", "true", "yes", "on"}:
            return True
        if normalised in {"0", "false", "no", "off"}:
            return False
    return None


def _parse_float(value: Any) -> Optional[float]:
    try:
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str) and value.strip():
            return float(value)
    except (TypeError, ValueError):
        return None
    return None


def _parse_int(value: Any) -> Optional[int]:
    try:
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.strip():
            return int(value)
    except (TypeError, ValueError):
        return None
    return None


def _clamp_rate(value: float) -> float:
    return max(0.0, min(1.0, value))


def _shadow_defaults(profile: str, resolved: ResolvedModule | None) -> ShadowSettings:
    base_rate = _PROFILE_SAMPLE_DEFAULTS.get(profile.lower(), 0.0)
    if resolved is not None and isinstance(resolved.sample_rate, (int, float)):
        base_rate = float(resolved.sample_rate)
    primary = resolved.impl_id if resolved is not None else "legacy"
    return ShadowSettings(
        enabled=False,
        sample_rate=_clamp_rate(base_rate),
        primary=primary,
        secondary="novus",
        log_mismatch=True,
        budget_ms_p95=50,
    )


def _apply_shadow_overrides(settings: ShadowSettings, overrides: Mapping[str, Any]) -> ShadowSettings:
    enabled = settings.enabled
    sample_rate = settings.sample_rate
    primary = settings.primary
    secondary = settings.secondary
    log_mismatch = settings.log_mismatch
    budget = settings.budget_ms_p95

    if "enabled" in overrides:
        maybe = _parse_bool(overrides["enabled"])
        if maybe is not None:
            enabled = maybe
    if "sample_rate" in overrides:
        maybe_rate = _parse_float(overrides["sample_rate"])
        if maybe_rate is not None:
            sample_rate = _clamp_rate(maybe_rate)
    if "primary" in overrides:
        value = overrides["primary"]
        if isinstance(value, str) and value:
            primary = value
    if "secondary" in overrides:
        value = overrides["secondary"]
        if isinstance(value, str) and value:
            secondary = value
    if "log_mismatch" in overrides:
        maybe = _parse_bool(overrides["log_mismatch"])
        if maybe is not None:
            log_mismatch = maybe
    if "budget_ms_p95" in overrides:
        maybe_budget = _parse_int(overrides["budget_ms_p95"])
        if maybe_budget is not None and maybe_budget >= 0:
            budget = maybe_budget

    return ShadowSettings(
        enabled=enabled,
        sample_rate=sample_rate,
        primary=primary,
        secondary=secondary,
        log_mismatch=log_mismatch,
        budget_ms_p95=budget,
    )


def _shadow_env_overrides(env: Mapping[str, str]) -> Dict[str, Any]:
    keys = {
        "enabled": (
            "PUZZLE_SHADOW_ENABLED",
            "SHADOW_ENABLED",
        ),
        "sample_rate": (
            "PUZZLE_SHADOW_SAMPLE_RATE",
            "SHADOW_SAMPLE_RATE",
        ),
        "primary": (
            "PUZZLE_SHADOW_PRIMARY",
            "SHADOW_PRIMARY",
        ),
        "secondary": (
            "PUZZLE_SHADOW_SECONDARY",
            "SHADOW_SECONDARY",
        ),
        "log_mismatch": (
            "PUZZLE_SHADOW_LOG_MISMATCH",
            "SHADOW_LOG_MISMATCH",
        ),
        "budget_ms_p95": (
            "PUZZLE_SHADOW_BUDGET_MS_P95",
            "SHADOW_BUDGET_MS_P95",
        ),
    }
    payload: Dict[str, Any] = {}
    for field, aliases in keys.items():
        for alias in aliases:
            if alias in env:
                payload[field] = env[alias]
                break
    return payload


def _shadow_cli_overrides(env: Mapping[str, str]) -> Dict[str, Any]:
    keys = {
        "enabled": "CLI_SHADOW_ENABLED",
        "sample_rate": "CLI_SHADOW_SAMPLE_RATE",
        "primary": "CLI_SHADOW_PRIMARY",
        "secondary": "CLI_SHADOW_SECONDARY",
        "log_mismatch": "CLI_SHADOW_LOG_MISMATCH",
        "budget_ms_p95": "CLI_SHADOW_BUDGET_MS_P95",
    }
    payload: Dict[str, Any] = {}
    for field, alias in keys.items():
        if alias in env:
            payload[field] = env[alias]
    return payload


def _shadow_feature_overrides() -> Dict[str, Any]:
    shadow_entry = _load_features().get("shadow")
    if isinstance(shadow_entry, dict):
        return dict(shadow_entry)
    return {}


def _compute_shadow_settings(
    profile: str,
    env: Mapping[str, str],
    resolved: ResolvedModule,
) -> ShadowSettings:
    settings = _shadow_defaults(profile, resolved)

    settings = _apply_shadow_overrides(settings, {"sample_rate": resolved.sample_rate})
    settings = _apply_shadow_overrides(settings, _shadow_feature_overrides())
    settings = _apply_shadow_overrides(settings, _shadow_env_overrides(env))
    settings = _apply_shadow_overrides(settings, _shadow_cli_overrides(env))

    if settings.primary != resolved.impl_id:
        settings = replace(settings, primary=resolved.impl_id)

    if not settings.enabled:
        settings = replace(settings, sample_rate=0.0)

    return settings


def check_uniqueness(
    puzzle_kind: str,
    spec: Dict[str, Any],
    grid_or_candidate: Dict[str, Any],
    *,
    options: Optional[Dict[str, Any]] = None,
    profile: str = "dev",
    env: Mapping[str, str] | None = None,
) -> tuple[Dict[str, Any], ResolvedModule]:
    """Dispatch the uniqueness check to the configured solver implementation."""

    env_map = build_env(env)
    resolved = resolve(puzzle_kind, "solver", profile, env_map)
    shadow_settings = _compute_shadow_settings(profile, env_map, resolved)

    module = load_module(resolved)

    try:
        handler = getattr(module, "port_check_uniqueness")
    except AttributeError as exc:  # pragma: no cover - defensive guard
        raise AttributeError(
            f"Solver implementation '{resolved.module_id}' does not expose 'port_check_uniqueness'"
        ) from exc

    payload = handler(spec, grid_or_candidate, options=options)

    enriched = replace(
        resolved,
        sample_rate=shadow_settings.sample_rate,
        config={
            **resolved.config,
            "shadow": {
                "enabled": shadow_settings.enabled,
                "primary": shadow_settings.primary,
                "secondary": shadow_settings.secondary,
                "sample_rate": shadow_settings.sample_rate,
                "log_mismatch": shadow_settings.log_mismatch,
                "budget_ms_p95": shadow_settings.budget_ms_p95,
            },
        },
    )

    return payload, enriched


__all__ = ["check_uniqueness"]
