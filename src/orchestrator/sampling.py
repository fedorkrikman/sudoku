"""Deterministic sampling helpers for shadow execution."""

from __future__ import annotations

import hashlib
from decimal import Decimal, ROUND_DOWN

__all__ = ["hit"]


def _materialise(hash_salt: str | None, run_id: str, puzzle_digest: str | None, sticky: bool) -> bytes:
    parts = [hash_salt or ""]
    if not sticky:
        parts.append(run_id)
    parts.extend(["sudoku", "shadow", puzzle_digest or ""])
    return "".join(parts).encode("utf-8")


def hit(
    hash_salt: str | None,
    run_id: str,
    puzzle_digest: str | None,
    rate: Decimal | float | int,
    *,
    sticky: bool,
) -> bool:
    """Return ``True`` if the deterministic sampler selects the run.

    ``rate`` is clamped to ``[0.0, 1.0]`` to make the helper robust to
    configuration mistakes.  The sampling decision uses the first eight bytes of
    the SHA256 digest as an unsigned integer to avoid float precision drift.
    """

    if not isinstance(rate, Decimal):
        rate = Decimal(str(rate))

    if rate <= Decimal("0"):
        return False
    if rate >= Decimal("1"):
        return True

    material = _materialise(hash_salt, run_id, puzzle_digest, sticky)
    digest = hashlib.sha256(material).digest()
    u64 = int.from_bytes(digest[:8], "big", signed=False)
    scale = Decimal(1 << 64)
    threshold = int((rate * scale).to_integral_value(rounding=ROUND_DOWN))
    return u64 < threshold
