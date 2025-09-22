"""Facade for printer implementations across puzzles."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Mapping

from orchestrator.router import ResolvedModule, resolve

from ._loader import load_module
from ._utils import build_env


def export_bundle(
    puzzle_kind: str,
    bundle: Dict[str, Any],
    *,
    output_dir: str | Path,
    profile: str = "dev",
    env: Mapping[str, str] | None = None,
) -> tuple[Dict[str, Any], ResolvedModule]:
    """Invoke the configured printer implementation."""

    env_map = build_env(env)
    resolved = resolve(puzzle_kind, "printer", profile, env_map)
    module = load_module(resolved)

    try:
        handler = getattr(module, "port_export")
    except AttributeError as exc:  # pragma: no cover - defensive guard
        raise AttributeError(
            f"Printer implementation '{resolved.module_id}' does not expose 'port_export'"
        ) from exc

    payload = handler(bundle, output_dir=output_dir)
    return payload, resolved


__all__ = ["export_bundle"]
