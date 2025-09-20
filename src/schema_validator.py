"""Offline JSON Schema validator tailored for the puzzle artifacts."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

try:  # Optional dependency
    import jsonschema  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - fallback to manual validation
    jsonschema = None  # type: ignore[assignment]

import artifact_store

_REPO_ROOT = Path(__file__).resolve().parents[1]
_CONTRACT_ROOT = _REPO_ROOT / "PuzzleContracts"
_CATALOG_PATH = _CONTRACT_ROOT / "catalog.json"


@dataclass(frozen=True)
class SchemaDescriptor:
    """Descriptor that binds an artifact type to its active schema."""

    type: str
    version: str
    schema_id: str
    schema_path: str


_catalog: Dict[str, SchemaDescriptor] = {}
_schema_cache: Dict[str, Dict[str, Any]] = {}


def _load_catalog() -> Dict[str, SchemaDescriptor]:
    if _catalog:
        return _catalog
    raw = json.loads(_CATALOG_PATH.read_text("utf-8"))
    for artifact_type, data in raw.items():
        descriptor = SchemaDescriptor(
            type=artifact_type,
            version=data["version"],
            schema_id=data["schema_id"],
            schema_path=data["schema_path"],
        )
        _catalog[artifact_type] = descriptor
    return _catalog


def get_schema_descriptor(artifact_type: str) -> SchemaDescriptor:
    """Return the schema descriptor for *artifact_type*."""

    catalog = _load_catalog()
    if artifact_type not in catalog:
        raise KeyError(f"Unknown artifact type: {artifact_type}")
    return catalog[artifact_type]


def load_schema(schema_path: str) -> Dict[str, Any]:
    """Load a schema relative to the contracts root directory."""

    resolved = (_CONTRACT_ROOT / schema_path).resolve()
    cache_key = str(resolved)
    if cache_key in _schema_cache:
        return _schema_cache[cache_key]
    schema = json.loads(resolved.read_text("utf-8"))
    schema_id = schema.get("$id")
    if isinstance(schema_id, str):
        _schema_cache[schema_id] = schema
    _schema_cache[cache_key] = schema
    _schema_cache[resolved.as_uri()] = schema
    return schema


def _iso_to_datetime(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:  # pragma: no cover - defensive path
        raise ValueError("created_at must be a valid ISO8601 timestamp") from exc


def validate_envelope(obj: Dict[str, Any]) -> None:
    """Perform minimal validation of the shared envelope fields."""

    if not isinstance(obj, dict):
        raise TypeError("Artifact must be a mapping")

    artifact_type = obj.get("type")
    if not isinstance(artifact_type, str):
        raise ValueError("Envelope requires a 'type' string")
    descriptor = get_schema_descriptor(artifact_type)

    schema_version = obj.get("schema_version")
    if schema_version != descriptor.version:
        raise ValueError(f"Unexpected schema_version for {artifact_type}: {schema_version}")

    if obj.get("schema_id") != descriptor.schema_id:
        raise ValueError("schema_id does not match catalog entry")

    if obj.get("schema_path") != descriptor.schema_path:
        raise ValueError("schema_path does not match catalog entry")

    if artifact_type != "Spec":
        spec_ref = obj.get("spec_ref")
        if not (isinstance(spec_ref, str) and spec_ref.startswith("sha256:")):
            raise ValueError("spec_ref must reference a Spec artifact")
    else:
        if "spec_ref" in obj and obj.get("spec_ref") not in (None, ""):
            raise ValueError("Spec artifacts must not reference another spec")

    artifact_id = obj.get("artifact_id")
    if not (isinstance(artifact_id, str) and artifact_id.startswith("sha256:")):
        raise ValueError("artifact_id is required before validation")

    created_at = obj.get("created_at")
    if not isinstance(created_at, str):
        raise ValueError("created_at must be an ISO formatted string")
    _iso_to_datetime(created_at)

    puzzle_type = obj.get("puzzle_type")
    if puzzle_type != "sudoku":
        raise ValueError("puzzle_type must be 'sudoku'")

    run_id = obj.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        raise ValueError("run_id must be a non-empty string")

    seed = obj.get("seed")
    if not isinstance(seed, (str, int)):
        raise ValueError("seed must be a string or integer")

    stage = obj.get("stage")
    if not isinstance(stage, str) or not stage:
        raise ValueError("stage must be a non-empty string")

    parents = obj.get("parents")
    if not isinstance(parents, list):
        raise ValueError("parents must be a list")
    for parent in parents:
        if not (isinstance(parent, str) and parent.startswith("sha256:")):
            raise ValueError("parents must contain only sha256 references")

    metrics = obj.get("metrics")
    if not isinstance(metrics, dict):
        raise ValueError("metrics must be an object")
    time_ms = metrics.get("time_ms")
    if not isinstance(time_ms, int) or time_ms < 0:
        raise ValueError("metrics.time_ms must be a non-negative integer")

    warnings = obj.get("warnings")
    errors = obj.get("errors")
    if not isinstance(warnings, list) or not all(isinstance(x, str) for x in warnings):
        raise ValueError("warnings must be an array of strings")
    if not isinstance(errors, list) or not all(isinstance(x, str) for x in errors):
        raise ValueError("errors must be an array of strings")

    ext = obj.get("ext")
    if not isinstance(ext, dict):
        raise ValueError("ext must be an object")


def _load_spec_for(obj: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    spec_ref = obj.get("spec_ref")
    if isinstance(spec_ref, str) and spec_ref.startswith("sha256:"):
        try:
            return artifact_store.load_artifact(spec_ref)
        except FileNotFoundError:
            return None
    return None


def _validate_spec(obj: Dict[str, Any]) -> None:
    size = obj.get("size")
    block = obj.get("block")
    alphabet = obj.get("alphabet")
    limits = obj.get("limits")

    if not isinstance(size, int) or size <= 0:
        raise ValueError("Spec.size must be a positive integer")
    if not (isinstance(block, dict) and "rows" in block and "cols" in block):
        raise ValueError("Spec.block must define rows and cols")
    rows = block.get("rows")
    cols = block.get("cols")
    if not (isinstance(rows, int) and isinstance(cols, int)):
        raise ValueError("Spec.block rows/cols must be integers")
    if rows <= 0 or cols <= 0 or rows * cols != size:
        raise ValueError("Spec.block dimensions must multiply to size")

    if not (isinstance(alphabet, list) and len(alphabet) == size):
        raise ValueError("Spec.alphabet must contain exactly 'size' symbols")
    seen = set()
    for symbol in alphabet:
        if not isinstance(symbol, str) or not symbol:
            raise ValueError("Spec.alphabet symbols must be non-empty strings")
        if symbol in seen:
            raise ValueError("Spec.alphabet symbols must be unique")
        seen.add(symbol)

    if not isinstance(limits, dict):
        raise ValueError("Spec.limits must be an object")
    timeout = limits.get("solver_timeout_ms")
    if not isinstance(timeout, int) or timeout < 0:
        raise ValueError("Spec.limits.solver_timeout_ms must be a non-negative integer")


def _validate_complete_grid(obj: Dict[str, Any]) -> None:
    spec = _load_spec_for(obj)
    size = spec.get("size") if spec else None
    alphabet = spec.get("alphabet") if spec else None

    encoding = obj.get("encoding")
    if not (isinstance(encoding, dict) and encoding.get("kind") == "row-major-string"):
        raise ValueError("encoding.kind must be 'row-major-string'")
    if encoding.get("alphabet") != "as-in-spec":
        raise ValueError("encoding.alphabet must be 'as-in-spec'")

    grid = obj.get("grid")
    if not isinstance(grid, str) or not grid:
        raise ValueError("grid must be a non-empty string")

    if isinstance(size, int):
        expected_length = size * size
        if len(grid) != expected_length:
            raise ValueError("grid length must match size*size from the spec")
    if isinstance(alphabet, list):
        alphabet_set = set(alphabet)
        if any(ch not in alphabet_set for ch in grid):
            raise ValueError("grid may only contain symbols from the spec alphabet")

    canonical_hash = obj.get("canonical_hash")
    if not (isinstance(canonical_hash, str) and canonical_hash.startswith("sha256:")):
        raise ValueError("canonical_hash must be a sha256 reference")
    expected_hash = hashlib.sha256(grid.encode("utf-8")).hexdigest()
    if canonical_hash != f"sha256:{expected_hash}":
        raise ValueError("canonical_hash does not match grid contents")


def _validate_verdict(obj: Dict[str, Any]) -> None:
    unique = obj.get("unique")
    if not isinstance(unique, bool):
        raise ValueError("unique must be a boolean")

    time_ms = obj.get("time_ms")
    if not isinstance(time_ms, int) or time_ms < 0:
        raise ValueError("time_ms must be a non-negative integer")

    nodes = obj.get("nodes")
    if nodes is not None and (not isinstance(nodes, int) or nodes < 0):
        raise ValueError("nodes must be a non-negative integer or null")

    cutoff = obj.get("cutoff")
    if cutoff is not None and not isinstance(cutoff, str):
        raise ValueError("cutoff must be a string or null")

    candidate_ref = obj.get("candidate_ref")
    solved_ref = obj.get("solved_ref")
    if candidate_ref is None and solved_ref is None:
        raise ValueError("Either candidate_ref or solved_ref must be provided")
    if unique and not (isinstance(solved_ref, str) and solved_ref.startswith("sha256:")):
        raise ValueError("unique verdicts must provide a solved_ref")


def _validate_export_bundle(obj: Dict[str, Any]) -> None:
    inputs = obj.get("inputs")
    if not isinstance(inputs, dict):
        raise ValueError("inputs must be an object")
    for key in ("complete_ref", "verdict_ref"):
        ref = inputs.get(key)
        if not (isinstance(ref, str) and ref.startswith("sha256:")):
            raise ValueError(f"inputs.{key} must be a sha256 reference")

    target = obj.get("target")
    if not isinstance(target, dict):
        raise ValueError("target must be an object")
    if target.get("format") != "pdf":
        raise ValueError("target.format must be 'pdf'")
    template = target.get("template")
    if not isinstance(template, str) or not template:
        raise ValueError("target.template must be a non-empty string")

    render_meta = obj.get("render_meta")
    if not isinstance(render_meta, dict):
        raise ValueError("render_meta must be an object")
    dpi = render_meta.get("dpi")
    if not isinstance(dpi, int) or dpi <= 0:
        raise ValueError("render_meta.dpi must be a positive integer")
    page = render_meta.get("page")
    if not isinstance(page, str) or not page:
        raise ValueError("render_meta.page must be a non-empty string")


def _manual_validate(obj: Dict[str, Any]) -> None:
    artifact_type = obj["type"]
    if artifact_type == "Spec":
        _validate_spec(obj)
    elif artifact_type == "CompleteGrid":
        _validate_complete_grid(obj)
    elif artifact_type == "Verdict":
        _validate_verdict(obj)
    elif artifact_type == "ExportBundle":
        _validate_export_bundle(obj)


def validate_artifact(obj: Dict[str, Any]) -> None:
    """Validate an artifact using JSON Schema when available."""

    validate_envelope(obj)

    descriptor = get_schema_descriptor(obj["type"])
    schema = load_schema(descriptor.schema_path)

    if jsonschema is not None:
        Validator = jsonschema.validators.validator_for(schema)
        Validator.check_schema(schema)
        resolver = jsonschema.RefResolver(
            base_uri=( _CONTRACT_ROOT / descriptor.schema_path).resolve().as_uri(),
            referrer=schema,
            store=_schema_cache,
        )
        validator = Validator(schema, resolver=resolver)
        validator.validate(obj)
    else:  # pragma: no cover - exercised when jsonschema is absent
        _manual_validate(obj)

    # Manual invariants complement JSON Schema even when jsonschema is present.
    _manual_validate(obj)


__all__ = [
    "SchemaDescriptor",
    "get_schema_descriptor",
    "load_schema",
    "validate_envelope",
    "validate_artifact",
]
