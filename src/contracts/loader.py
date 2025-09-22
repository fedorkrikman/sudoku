"""Schema loading utilities for the Validation Center."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Tuple

try:  # Optional dependency; jsonschema is not required at runtime
    import jsonschema  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - optional dependency
    jsonschema = None  # type: ignore[assignment]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CONTRACT_ROOT = _REPO_ROOT / "PuzzleContracts"
_CATALOG_PATH = _CONTRACT_ROOT / "catalog.json"


@dataclass(frozen=True)
class SchemaDescriptor:
    """Descriptor describing a schema entry from the catalog."""

    artifact_type: str
    version: str
    schema_id: str
    schema_path: str


_catalog_cache: Dict[str, SchemaDescriptor] | None = None
_schema_cache: Dict[Tuple[str, str], Dict[str, Any]] = {}
_compiled_cache: Dict[Tuple[str, str], Any] = {}


def load_catalog() -> Dict[str, SchemaDescriptor]:
    """Load and cache the schema catalog."""

    global _catalog_cache
    if _catalog_cache is not None:
        return _catalog_cache

    raw_catalog = json.loads(_CATALOG_PATH.read_text("utf-8"))
    catalog: Dict[str, SchemaDescriptor] = {}
    for artifact_type, payload in raw_catalog.items():
        catalog[artifact_type] = SchemaDescriptor(
            artifact_type=artifact_type,
            version=payload["version"],
            schema_id=payload["schema_id"],
            schema_path=payload["schema_path"],
        )
    _catalog_cache = catalog
    return catalog


def get_descriptor(artifact_type: str) -> SchemaDescriptor:
    """Return the :class:`SchemaDescriptor` for *artifact_type*."""

    catalog = load_catalog()
    if artifact_type not in catalog:
        raise KeyError(f"Unknown artifact type: {artifact_type}")
    return catalog[artifact_type]


def load_schema(schema_id: str, schema_path: str) -> Dict[str, Any]:
    """Load a JSON schema defined in the local PuzzleContracts catalog."""

    if "://" in schema_path:
        raise ValueError("Remote schema paths are not permitted")

    resolved = (_CONTRACT_ROOT / schema_path).resolve()
    if not str(resolved).startswith(str(_CONTRACT_ROOT)):
        raise ValueError("Schema path escapes the contracts directory")

    cache_key = (schema_id, schema_path)
    if cache_key in _schema_cache:
        return copy.deepcopy(_schema_cache[cache_key])

    schema = json.loads(resolved.read_text("utf-8"))
    if "$id" in schema and schema["$id"] != schema_id:
        raise ValueError(
            f"Schema id mismatch: catalog has {schema_id!r}, schema has {schema['$id']!r}"
        )

    _schema_cache[cache_key] = schema
    return copy.deepcopy(schema)


def maybe_compile(schema_dict: Dict[str, Any]) -> Any:
    """Compile *schema_dict* if ``jsonschema`` is available."""

    cache_key = (schema_dict.get("$id", ""), schema_dict.get("$schema", ""))
    if cache_key in _compiled_cache:
        return _compiled_cache[cache_key]

    if jsonschema is None:
        return schema_dict

    validator_cls = getattr(jsonschema, 'Draft202012Validator', getattr(jsonschema, 'Draft7Validator'))
    validator = validator_cls(schema_dict)
    _compiled_cache[cache_key] = validator
    return validator


__all__ = [
    "SchemaDescriptor",
    "get_descriptor",
    "load_catalog",
    "load_schema",
    "maybe_compile",
]
