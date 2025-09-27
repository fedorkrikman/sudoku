"""Facade for solver implementations across puzzles."""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation, ROUND_DOWN
from typing import Any, Dict, Mapping, Optional
import re
import warnings

from feature_flags import get_shadow_feature
from orchestrator.router import ResolvedModule, resolve

from ._loader import load_module
from ._utils import build_env


_DECIMAL_PATTERN = re.compile(r"^-?[0-9]+(?:\.[0-9]{1,6})?$")


@dataclass(frozen=True)
class ShadowSettings:
    """Finalised shadow policy after precedence resolution."""

    enabled: bool
    sample_rate: Decimal
    sample_rate_str: str
    primary: str
    secondary: str
    log_mismatch: bool
    budget_ms_p95: int
    hash_salt: str
    sticky: bool


_PROFILE_SAMPLE_DEFAULTS = {
    "dev": Decimal("0.25"),
    "test": Decimal("0.25"),
    "pilot": Decimal("1.0"),
    "prod": Decimal("0.0"),
}


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


def _parse_decimal(value: Any) -> Optional[Decimal]:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, str):
        candidate = value.strip()
        if not candidate:
            return None
        if not _DECIMAL_PATTERN.match(candidate):
            return None
        try:
            return Decimal(candidate)
        except InvalidOperation:
            return None
    if isinstance(value, (int, float)):
        warnings.warn(
            "Shadow sample_rate numeric overrides are deprecated; use decimal strings instead",
            RuntimeWarning,
            stacklevel=2,
        )
        try:
            return Decimal(str(value))
        except InvalidOperation:
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


def _format_decimal(value: Decimal) -> str:
    quantised = (
        value.quantize(Decimal("0.000001"), rounding=ROUND_DOWN)
        if value.as_tuple().exponent < -6
        else value
    )
    # Use normalised fixed-point representation without scientific notation.
    text = format(quantised.normalize(), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".") or "0"
    return text


def _clamp_decimal(value: Decimal) -> Decimal:
    if value < Decimal("0"):
        return Decimal("0")
    if value > Decimal("1"):
        return Decimal("1")
    return value


def _shadow_defaults(profile: str, resolved: ResolvedModule | None) -> ShadowSettings:
    base_rate = _PROFILE_SAMPLE_DEFAULTS.get(profile.lower(), Decimal("0"))
    if resolved is not None and isinstance(resolved.sample_rate, (int, float, Decimal)):
        try:
            base_rate = Decimal(str(resolved.sample_rate))
        except (InvalidOperation, ValueError):
            base_rate = _PROFILE_SAMPLE_DEFAULTS.get(profile.lower(), Decimal("0"))
    clamped = _clamp_decimal(base_rate)
    primary = resolved.impl_id if resolved is not None else "legacy"
    return ShadowSettings(
        enabled=False,
        sample_rate=clamped,
        sample_rate_str=_format_decimal(clamped),
        primary=primary,
        secondary="novus",
        log_mismatch=True,
        budget_ms_p95=50,
        hash_salt="",
        sticky=False,
    )


def _apply_shadow_overrides(settings: ShadowSettings, overrides: Mapping[str, Any]) -> ShadowSettings:
    enabled = settings.enabled
    sample_rate = settings.sample_rate
    sample_rate_str = settings.sample_rate_str
    primary = settings.primary
    secondary = settings.secondary
    log_mismatch = settings.log_mismatch
    budget = settings.budget_ms_p95
    hash_salt = settings.hash_salt
    sticky = settings.sticky

    if "enabled" in overrides:
        maybe = _parse_bool(overrides["enabled"])
        if maybe is not None:
            enabled = maybe
    if "sample_rate" in overrides:
        maybe_rate = _parse_decimal(overrides["sample_rate"])
        if maybe_rate is not None:
            sample_rate = _clamp_decimal(maybe_rate)
            sample_rate_str = _format_decimal(sample_rate)
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
    if "hash_salt" in overrides:
        value = overrides["hash_salt"]
        if isinstance(value, str):
            hash_salt = value
    if "sticky" in overrides:
        maybe = _parse_bool(overrides["sticky"])
        if maybe is not None:
            sticky = maybe

    return ShadowSettings(
        enabled=enabled,
        sample_rate=sample_rate,
        sample_rate_str=sample_rate_str,
        primary=primary,
        secondary=secondary,
        log_mismatch=log_mismatch,
        budget_ms_p95=budget,
        hash_salt=hash_salt,
        sticky=sticky,
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
        "hash_salt": (
            "PUZZLE_SHADOW_HASH_SALT",
            "SHADOW_HASH_SALT",
        ),
        "sticky": (
            "PUZZLE_SHADOW_STICKY",
            "SHADOW_STICKY",
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
        "hash_salt": "CLI_SHADOW_HASH_SALT",
        "sticky": "CLI_SHADOW_STICKY",
    }
    payload: Dict[str, Any] = {}
    for field, alias in keys.items():
        if alias in env:
            payload[field] = env[alias]
    return payload


def _shadow_feature_overrides(profile: str) -> Dict[str, Any]:
    return dict(get_shadow_feature(profile))


def _compute_shadow_settings(
    profile: str,
    env: Mapping[str, str],
    resolved: ResolvedModule,
) -> ShadowSettings:
    settings = _shadow_defaults(profile, resolved)

    module_override: Dict[str, Any] = {}
    if isinstance(resolved.sample_rate, (int, float, Decimal)):
        module_override["sample_rate"] = Decimal(str(resolved.sample_rate))

    settings = _apply_shadow_overrides(settings, module_override)
    settings = _apply_shadow_overrides(settings, _shadow_feature_overrides(profile))
    settings = _apply_shadow_overrides(settings, _shadow_env_overrides(env))
    settings = _apply_shadow_overrides(settings, _shadow_cli_overrides(env))

    if settings.primary != resolved.impl_id:
        settings = replace(settings, primary=resolved.impl_id)

    if not settings.enabled:
        zero = Decimal("0")
        settings = replace(settings, sample_rate=zero, sample_rate_str=_format_decimal(zero))

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

    shadow_policy = {
        "enabled": shadow_settings.enabled,
        "primary": shadow_settings.primary,
        "secondary": shadow_settings.secondary,
        "sample_rate": shadow_settings.sample_rate_str,
        "log_mismatch": shadow_settings.log_mismatch,
        "budget_ms_p95": shadow_settings.budget_ms_p95,
        "hash_salt": shadow_settings.hash_salt,
        "sticky": shadow_settings.sticky,
    }

    enriched = replace(
        resolved,
        sample_rate=float(shadow_settings.sample_rate),
        config={
            **resolved.config,
            "shadow": shadow_policy,
        },
    )

    return payload, enriched


__all__ = ["check_uniqueness"]
