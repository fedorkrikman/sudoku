"""Facade for generator implementations across puzzles."""

from __future__ import annotations

from typing import Any, Dict, Mapping

from orchestrator.router import ResolvedModule, resolve

from ._loader import load_module
from ._utils import build_env


def generate_complete(
    puzzle_kind: str,
    spec: Dict[str, Any],
    *,
    seed: str,
    profile: str = "dev",
    env: Mapping[str, str] | None = None,
) -> tuple[Dict[str, Any], ResolvedModule]:
    """Generate a complete grid for the specified puzzle."""

    env_map = build_env(env)
    resolved = resolve(puzzle_kind, "generator", profile, env_map)
    module = load_module(resolved)

    try:
        handler = getattr(module, "port_generate_complete")
    except AttributeError as exc:  # pragma: no cover - defensive guard
        raise AttributeError(
            f"Generator implementation '{resolved.module_id}' does not expose 'port_generate_complete'"
        ) from exc

    payload = handler(spec, seed=seed)
    return payload, resolved


__all__ = ["generate_complete"]
