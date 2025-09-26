"""Deterministic sampling helpers for shadow execution."""

from __future__ import annotations

import hashlib
from typing import Any

__all__ = ["hit"]


def _materialise(hash_salt: str | None, run_id: str, stage: str, seed: str, module_id: str) -> bytes:
    parts = [hash_salt or "", run_id, stage, seed, module_id]
    return "|".join(parts).encode("utf-8")


def hit(
    hash_salt: str | None,
    run_id: str,
    stage: str,
    seed: str,
    module_id: str,
    rate: float,
) -> bool:
    """Return ``True`` if the deterministic sampler selects the run.

    ``rate`` is clamped to ``[0.0, 1.0]`` to make the helper robust to
    configuration mistakes.  The sampling decision uses the first eight bytes of
    the SHA256 digest as an unsigned integer to avoid float precision drift.
    """

    if rate <= 0:
        return False
    if rate >= 1:
        return True

    material = _materialise(hash_salt, run_id, stage, seed, module_id)
    digest = hashlib.sha256(material).digest()
    u64 = int.from_bytes(digest[:8], "big", signed=False)
    threshold = rate * (1 << 64)
    return u64 < threshold
