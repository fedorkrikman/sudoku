"""Artifact reference helpers used by the orchestrator runtime."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, MutableMapping

__all__ = ["ArtifactRef", "make_artifact"]


@dataclass(frozen=True)
class ArtifactRef:
    """Description of an immutable artifact stored in persistent storage."""

    kind: str
    digest: str
    uri: str
    size: int | None = None
    media_type: str | None = None
    created_at: str | None = None
    compression: str | None = None
    schema_hint: str | None = None
    metadata: Mapping[str, Any] | None = None


def _compute_digest(payload: bytes) -> str:
    return f"sha256-{hashlib.sha256(payload).hexdigest()}"


def _coerce_bytes(data: Any) -> tuple[bytes, MutableMapping[str, Any]]:
    if isinstance(data, (bytes, bytearray, memoryview)):
        raw = bytes(data)
        return raw, {}
    if isinstance(data, Path):
        raw = data.read_bytes()
        return raw, {"uri": data.resolve().as_uri(), "size": len(raw)}
    if isinstance(data, str):
        path = Path(data)
        if path.exists():
            raw = path.read_bytes()
            return raw, {"uri": path.resolve().as_uri(), "size": len(raw)}
        return data.encode("utf-8"), {}
    raise TypeError("artifact payload must be bytes or filesystem path")


def make_artifact(
    kind: str,
    payload: Any,
    media_type: str | None = None,
    schema_hint: str | None = None,
    *,
    compression: str | None = None,
    created_at: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> ArtifactRef:
    """Return an :class:`ArtifactRef` computed from ``payload``.

    ``payload`` can either be bytes-like data or a filesystem path.  The
    resulting reference contains a stable ``sha256`` digest and optionally the
    media type, schema hint and compression metadata requested by the caller.
    """

    raw, extra = _coerce_bytes(payload)
    digest = _compute_digest(raw)

    if "uri" not in extra:
        extra["uri"] = f"memory://{digest}"
    if "size" not in extra:
        extra["size"] = len(raw)

    resolved_created_at = created_at or datetime.now(timezone.utc).isoformat()

    ref_metadata: MutableMapping[str, Any] = {}
    if metadata:
        ref_metadata.update(metadata)
    if media_type:
        ref_metadata.setdefault("media_type", media_type)
    if schema_hint:
        ref_metadata.setdefault("schema_hint", schema_hint)

    return ArtifactRef(
        kind=str(kind),
        digest=digest,
        uri=extra["uri"],
        size=extra.get("size"),
        media_type=media_type,
        created_at=resolved_created_at,
        compression=compression,
        schema_hint=schema_hint,
        metadata=dict(ref_metadata) if ref_metadata else None,
    )
