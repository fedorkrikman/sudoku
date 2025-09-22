"""Utility helpers for port facades."""

from __future__ import annotations

import os
from typing import Dict, Mapping


def build_env(overrides: Mapping[str, str] | None = None) -> Dict[str, str]:
    """Merge process environment with optional overrides."""

    env: Dict[str, str] = {str(k): str(v) for k, v in os.environ.items()}
    if overrides:
        env.update({str(k): str(v) for k, v in overrides.items()})
    return env


__all__ = ["build_env"]
