"""Utilities for canonical storage of pipeline artifacts."""

from __future__ import annotations

import copy
import hashlib
import json
import math
import unicodedata
from pathlib import Path
from typing import Any, Dict

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ARTIFACT_ROOT = _REPO_ROOT / "artifacts"


def _normalize(obj: Any) -> Any:
    """Return a deep-normalised structure suitable for canonical JSON."""

    if isinstance(obj, dict):
        return {str(k): _normalize(v) for k, v in sorted(obj.items(), key=lambda item: str(item[0]))}
    if isinstance(obj, list):
        return [_normalize(item) for item in obj]
    if isinstance(obj, str):
        return unicodedata.normalize("NFC", obj)
    if isinstance(obj, float):
        if not math.isfinite(obj):
            raise ValueError("Non-finite numbers are not allowed in artifacts")
        return obj
    return obj


def canonicalize(obj: Dict[str, Any]) -> bytes:
    """Serialise *obj* into canonical JSON bytes.

    Dictionaries are sorted lexicographically by key, strings are normalised to
    NFC, and the output does not contain insignificant whitespace.
    """

    normalised = _normalize(obj)
    return json.dumps(normalised, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def compute_artifact_id(obj: Dict[str, Any]) -> str:
    """Compute the canonical artifact identifier for *obj*.

    The hash is calculated over the canonical JSON representation of the object
    with the ``artifact_id`` field removed.
    """

    base = copy.deepcopy(obj)
    if isinstance(base, dict) and "artifact_id" in base:
        base = dict(base)
        base.pop("artifact_id", None)
    canonical = canonicalize(base)
    digest = hashlib.sha256(canonical).hexdigest()
    return f"sha256-{digest}"


def save_artifact(obj: Dict[str, Any]) -> str:
    """Persist an artifact and return its identifier.

    The artifact is written into ``artifacts/<Type>/<artifact_id>.json`` using
    canonical JSON serialisation. ``artifact_id`` is generated deterministically
    from the canonical JSON representation of the payload without the
    ``artifact_id`` field itself.
    """

    if not isinstance(obj, dict):
        raise TypeError("Artifact must be a mapping")

    artifact_copy: Dict[str, Any] = copy.deepcopy(obj)
    artifact_id = compute_artifact_id(artifact_copy)
    existing_id = artifact_copy.get("artifact_id")
    if existing_id is not None and existing_id != artifact_id:
        raise ValueError("Provided artifact_id does not match canonical hash")
    artifact_copy["artifact_id"] = artifact_id

    artifact_type = artifact_copy.get("type")
    if not isinstance(artifact_type, str) or not artifact_type:
        raise ValueError("Artifact type must be a non-empty string")

    target_dir = _ARTIFACT_ROOT / artifact_type
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / f"{artifact_id}.json"
    target_path.write_bytes(canonicalize(artifact_copy))

    # Update the original object in-place to reflect the canonical identifier.
    obj["artifact_id"] = artifact_id
    return artifact_id


def load_artifact(artifact_id: str) -> Dict[str, Any]:
    """Load and return an artifact by its identifier."""

    if not artifact_id.startswith("sha256-"):
        raise ValueError("Artifact identifier must start with 'sha256-'")
    for type_dir in _ARTIFACT_ROOT.glob("*"):
        if not type_dir.is_dir():
            continue
        candidate = type_dir / f"{artifact_id}.json"
        if candidate.exists():
            return json.loads(candidate.read_text("utf-8"))
    raise FileNotFoundError(f"Artifact '{artifact_id}' was not found in the store")


def ref(path_or_id: str) -> Dict[str, Any]:
    """Resolve *path_or_id* either from the store or from a JSON file."""

    if path_or_id.startswith("sha256-"):
        return load_artifact(path_or_id)
    path = Path(path_or_id)
    if not path.is_absolute():
        path = _REPO_ROOT / path
    return json.loads(path.read_text("utf-8"))


__all__ = [
    "canonicalize",
    "compute_artifact_id",
    "save_artifact",
    "load_artifact",
    "ref",
]
