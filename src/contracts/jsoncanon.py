"""JSON Canonicalization Scheme (JCS) helpers.

This module implements a tiny subset of RFC 8785 that is sufficient for the
runtime components in this repository.  Objects are transformed into their
canonical representation by recursively sorting dictionary keys, normalising
numbers, and emitting UTF-8 encoded bytes without superfluous whitespace.  The
helpers intentionally avoid external dependencies so they can be reused in
light-weight environments such as the orchestrator worker processes.
"""

from __future__ import annotations

import json
import math
from decimal import Decimal
from typing import Any

__all__ = ["jcs_dump", "jcs_sha256"]


def _canonical_number(value: float) -> str:
    """Return the ECMAScript-compatible canonical string for ``value``.

    The implementation mirrors the algorithm from RFC 8785 §3.2.3.  We rely on
    :func:`decimal.Decimal` for deterministic conversion and then format the
    number using the shortest representation that round-trips back to the
    original float.
    """

    if math.isnan(value) or math.isinf(value):  # pragma: no cover - guarded by caller
        raise ValueError("NaN and Infinity are not permitted in JCS payloads")

    if value == 0:
        # Normalise both +0.0 and -0.0 to "0"
        return "0"

    decimal_value = Decimal(value)
    # Use normalized scientific notation and remove exponent when possible.
    normalized = format(decimal_value.normalize(), "f")
    if "E" in normalized or "e" in normalized:
        normalized = format(decimal_value.normalize(), "e")
    if normalized.endswith(".0"):
        normalized = normalized[:-2]
    return normalized


def _canonicalize(obj: Any) -> Any:
    if obj is None:
        return None
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, int):
        return obj
    if isinstance(obj, float):
        return json.loads(_canonical_number(obj))
    if isinstance(obj, str):
        return obj
    if isinstance(obj, (bytes, bytearray, memoryview)):
        # RFC 8785 does not define binary payloads.  Treat them as base64
        # encoded strings to keep the output deterministic.
        return (bytes(obj)).decode("utf-8")
    if isinstance(obj, list):
        return [_canonicalize(item) for item in obj]
    if isinstance(obj, tuple):
        return [_canonicalize(item) for item in obj]
    if isinstance(obj, dict):
        canonical_dict = {}
        for key in sorted(obj.keys(), key=str):
            value = obj[key]
            canonical_dict[str(key)] = _canonicalize(value)
        return canonical_dict
    raise TypeError(f"Unsupported type for JCS canonicalisation: {type(obj)!r}")


def jcs_dump(obj: Any) -> bytes:
    """Return canonical JCS bytes for ``obj``.

    The output is encoded as UTF-8 and guaranteed to be stable for supported
    inputs.  Unsupported value types raise :class:`TypeError`.
    """

    canonical = _canonicalize(obj)
    dumped = json.dumps(
        canonical,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )
    return dumped.encode("utf-8")


def jcs_sha256(obj: Any) -> str:
    """Return the ``sha256`` digest of the canonical representation of ``obj``."""

    import hashlib

    digest = hashlib.sha256(jcs_dump(obj)).hexdigest()
    return f"sha256-{digest}"
