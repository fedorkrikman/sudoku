"""Placeholder difficulty port to exercise router integration."""

from __future__ import annotations

from typing import Mapping

from orchestrator.router import ResolvedModule, resolve

from ._utils import build_env


def resolve_difficulty(
    puzzle_kind: str,
    *,
    profile: str = "dev",
    env: Mapping[str, str] | None = None,
) -> ResolvedModule:
    """Resolve the difficulty role without invoking an implementation."""

    env_map = build_env(env)
    return resolve(puzzle_kind, "difficulty", profile, env_map)


__all__ = ["resolve_difficulty"]
