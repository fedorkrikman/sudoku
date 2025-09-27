"""Module resolution router for puzzle-first architecture."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping

from project_config import get_config

PUZZLES_ROOT = Path(__file__).resolve().parents[1] / "puzzles"
SUPPORTED_ROLES = {"solver", "generator", "printer", "difficulty"}


class RouterError(RuntimeError):
    """Raised when a module resolution request cannot be satisfied."""


@dataclass(frozen=True)
class ResolvedModule:
    """Description of the module chosen for a puzzle role."""

    puzzle_kind: str
    role: str
    impl_id: str
    module_id: str
    module_path: Path
    state: str
    decision_source: str
    sample_rate: float
    sample_hit: bool
    allow_fallback: bool
    fallback_used: bool
    contracts: str | None
    config: Dict[str, Any]


_DEF_STATE = "default"
_DEF_IMPL = "legacy"


def _normalise_env(env: Mapping[str, str]) -> Dict[str, str]:
    return {str(k).upper(): str(v) for k, v in env.items()}


def _extract_role_policy(puzzle_kind: str, role: str, profile: str) -> Dict[str, Any]:
    config = get_config()
    modules = config.get("modules", {})
    puzzle_cfg = modules.get(puzzle_kind, {}) if isinstance(modules, dict) else {}
    role_cfg = puzzle_cfg.get(role, {}) if isinstance(puzzle_cfg, dict) else {}

    policy: Dict[str, Any] = {}
    if isinstance(role_cfg, dict):
        for key, value in role_cfg.items():
            if key == "by_profile":
                continue
            policy[key] = value

        by_profile = role_cfg.get("by_profile")
        if isinstance(by_profile, dict):
            profile_block = by_profile.get(profile)
            if isinstance(profile_block, dict):
                policy.update(profile_block)
    return policy


def _resolve_impl(policy: Dict[str, Any], env: Dict[str, str], role: str) -> tuple[str, str, str]:
    role_upper = role.upper()
    cli_impl_key = f"CLI_PUZZLE_{role_upper}_IMPL"
    cli_state_key = f"CLI_PUZZLE_{role_upper}_STATE"
    env_impl_key = f"PUZZLE_{role_upper}_IMPL"
    env_state_key = f"PUZZLE_{role_upper}_STATE"

    decision_source = "config"
    impl = str(policy.get("impl", _DEF_IMPL))
    state = str(policy.get("state", _DEF_STATE))

    if env_impl_key in env and env[env_impl_key]:
        impl = env[env_impl_key]
        decision_source = "env"
    if env_state_key in env and env[env_state_key]:
        state = env[env_state_key]
        decision_source = "env"

    if env.get(cli_impl_key):
        impl = env[cli_impl_key]
        decision_source = "cli"
    if env.get(cli_state_key):
        state = env[cli_state_key]
        decision_source = "cli"

    return impl, state, decision_source


def _resolve_sample_rate(policy: Mapping[str, Any], env: Mapping[str, str], role: str) -> float:
    role_upper = role.upper()
    cli_key = f"CLI_PUZZLE_{role_upper}_SAMPLE_RATE"
    env_key = f"PUZZLE_{role_upper}_SAMPLE_RATE"

    for key in (cli_key, env_key):
        raw = env.get(key)
        if raw is None:
            continue
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        return max(0.0, min(1.0, value))

    raw_policy = policy.get("sample_rate", 0.0)
    try:
        value = float(raw_policy)
    except (TypeError, ValueError):
        value = 0.0
    return max(0.0, min(1.0, value))


def _apply_policy_defaults(policy: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(policy)
    merged.setdefault("impl", _DEF_IMPL)
    merged.setdefault("state", _DEF_STATE)
    merged.setdefault("sample_rate", 0.0)
    merged.setdefault("allow_fallback", True)
    return merged


def resolve(puzzle_kind: str, role: str, profile: str, env: Mapping[str, str]) -> ResolvedModule:
    if role not in SUPPORTED_ROLES:
        raise RouterError(f"Unsupported role '{role}'")

    puzzle_root = PUZZLES_ROOT / puzzle_kind
    if not puzzle_root.exists():
        raise RouterError(f"Puzzle '{puzzle_kind}' is not registered under 'src/puzzles'")

    env_map = _normalise_env(env)
    policy = _apply_policy_defaults(_extract_role_policy(puzzle_kind, role, profile))

    impl, state, decision_source = _resolve_impl(policy, env_map, role)

    if profile.lower() == "ci" and state in {"shadow", "canary"}:
        raise RouterError(
            f"State '{state}' is not permitted for role '{role}' under CI profile"
        )

    allow_fallback = bool(policy.get("allow_fallback", True))
    sample_rate = _resolve_sample_rate(policy, env_map, role)
    contracts = policy.get("contracts")

    module_root = puzzle_root / role / impl
    fallback_used = False
    if not module_root.exists():
        if allow_fallback and impl != _DEF_IMPL:
            fallback_root = puzzle_root / role / _DEF_IMPL
            if fallback_root.exists():
                module_root = fallback_root
                impl = _DEF_IMPL
                fallback_used = True
                decision_source = "fallback"
            else:
                raise RouterError(
                    f"Requested implementation '{impl}' for role '{role}' is missing and no fallback is available"
                )
        else:
            raise RouterError(
                f"Implementation '{impl}' for role '{role}' is not available for puzzle '{puzzle_kind}'"
            )

    module_path = module_root / "__init__.py"
    if not module_path.exists():
        raise RouterError(
            f"Implementation package '{module_root}' does not contain an __init__.py file"
        )

    module_id = f"{puzzle_kind}:/{impl}@"

    return ResolvedModule(
        puzzle_kind=puzzle_kind,
        role=role,
        impl_id=impl,
        module_id=module_id,
        module_path=module_path,
        state=state,
        decision_source=decision_source,
        sample_rate=sample_rate,
        sample_hit=False,
        allow_fallback=allow_fallback,
        fallback_used=fallback_used,
        contracts=contracts if isinstance(contracts, str) else None,
        config=dict(policy),
    )


__all__ = ["ResolvedModule", "RouterError", "resolve", "SUPPORTED_ROLES"]
