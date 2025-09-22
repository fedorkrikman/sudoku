"""Facade for solver implementations across puzzles."""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

from orchestrator.router import ResolvedModule, resolve

from ._loader import load_module
from ._utils import build_env


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
    module = load_module(resolved)

    try:
        handler = getattr(module, "port_check_uniqueness")
    except AttributeError as exc:  # pragma: no cover - defensive guard
        raise AttributeError(
            f"Solver implementation '{resolved.module_id}' does not expose 'port_check_uniqueness'"
        ) from exc

    payload = handler(spec, grid_or_candidate, options=options)
    return payload, resolved


__all__ = ["check_uniqueness"]
