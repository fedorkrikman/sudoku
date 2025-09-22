"""Offline JSON Schema validator tailored for local puzzle artifacts."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

try:  # Optional dependency for full JSON Schema validation
    import jsonschema  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - fallback to manual checks
    jsonschema = None  # type: ignore[assignment]

from artifacts import artifact_store


class SchemaValidationError(RuntimeError):
    """Exception raised when an artifact fails validation."""

    def __init__(self, code: str, detail: Optional[str] = None) -> None:
        self.code = code
        self.detail = detail
        message = code if detail is None else f"{code}:{detail}"
        super().__init__(message)


_REPO_ROOT = Path(__file__).resolve().parents[2]
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
        raise SchemaValidationError("schema-not-found", artifact_type)
    return catalog[artifact_type]


def load_schema(schema_path: str) -> Dict[str, Any]:
    """Load a schema relative to the contracts root directory."""

    resolved = (_CONTRACT_ROOT / schema_path).resolve()
    cache_key = str(resolved)
    if cache_key in _schema_cache:
        return _schema_cache[cache_key]

    try:
        schema = json.loads(resolved.read_text("utf-8"))
    except FileNotFoundError as exc:  # pragma: no cover - defensive
        raise SchemaValidationError("schema-not-found", schema_path) from exc

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
        raise SchemaValidationError("invalid-envelope", "created_at must be ISO8601") from exc


def _require(condition: bool, detail: str) -> None:
    if not condition:
        raise SchemaValidationError("invalid-envelope", detail)


def validate_envelope(obj: Dict[str, Any]) -> None:
    """Perform minimal validation of the shared envelope fields."""

    if not isinstance(obj, dict):
        raise SchemaValidationError("invalid-envelope", "artifact must be an object")

    artifact_type = obj.get("type")
    _require(isinstance(artifact_type, str) and artifact_type, "missing type")

    descriptor = get_schema_descriptor(artifact_type)

    schema_version = obj.get("schema_version")
    _require(schema_version == descriptor.version, "unexpected schema_version")

    _require(obj.get("schema_id") == descriptor.schema_id, "schema_id mismatch")
    _require(obj.get("schema_path") == descriptor.schema_path, "schema_path mismatch")

    spec_ref = obj.get("spec_ref")
    if artifact_type == "Spec":
        if spec_ref not in (None, ""):
            raise SchemaValidationError("invalid-envelope", "spec must not have spec_ref")
    else:
        _require(isinstance(spec_ref, str) and spec_ref.startswith("sha256-"), "spec_ref must reference a spec")

    artifact_id = obj.get("artifact_id")
    _require(isinstance(artifact_id, str) and artifact_id.startswith("sha256-"), "artifact_id must be present")

    created_at = obj.get("created_at")
    _require(isinstance(created_at, str), "created_at must be a string")
    _iso_to_datetime(created_at)

    _require(obj.get("puzzle_type") == "sudoku", "puzzle_type must be 'sudoku'")

    run_id = obj.get("run_id")
    _require(isinstance(run_id, str) and run_id, "run_id must be non-empty string")

    seed = obj.get("seed")
    _require(isinstance(seed, (str, int)), "seed must be string or integer")

    stage = obj.get("stage")
    _require(isinstance(stage, str) and stage, "stage must be non-empty string")

    parents = obj.get("parents")
    _require(isinstance(parents, list), "parents must be an array")
    for parent in parents:
        _require(isinstance(parent, str) and parent.startswith("sha256-"), "parents must contain artifact ids")
    if len(parents) != len(set(parents)):
        raise SchemaValidationError("invalid-envelope", "parents must be unique")

    metrics = obj.get("metrics")
    _require(isinstance(metrics, dict), "metrics must be an object")
    time_ms = metrics.get("time_ms")
    _require(isinstance(time_ms, int) and time_ms >= 0, "metrics.time_ms must be non-negative integer")

    warnings = obj.get("warnings")
    errors = obj.get("errors")
    _require(isinstance(warnings, list) and all(isinstance(x, str) for x in warnings), "warnings must be string array")
    _require(isinstance(errors, list) and all(isinstance(x, str) for x in errors), "errors must be string array")

    ext = obj.get("ext")
    _require(isinstance(ext, dict), "ext must be an object")


def _invariant(detail: str) -> None:
    raise SchemaValidationError("invariant-violation", detail)


def _load_spec_for(obj: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    spec_ref = obj.get("spec_ref")
    if isinstance(spec_ref, str) and spec_ref.startswith("sha256-"):
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
        _invariant("Spec.size must be a positive integer")
    if not isinstance(block, dict):
        _invariant("Spec.block must be an object")
    rows = block.get("rows") if isinstance(block, dict) else None
    cols = block.get("cols") if isinstance(block, dict) else None
    if not (isinstance(rows, int) and isinstance(cols, int)):
        _invariant("Spec.block rows and cols must be integers")
    if rows <= 0 or cols <= 0 or rows * cols != size:
        _invariant("Spec.block rows*cols must equal size")

    if not (isinstance(alphabet, list) and len(alphabet) == size):
        _invariant("Spec.alphabet must contain exactly size symbols")
    seen = set()
    for symbol in alphabet:
        if not isinstance(symbol, str) or not symbol:
            _invariant("Spec.alphabet symbols must be non-empty strings")
        if symbol in seen:
            _invariant("Spec.alphabet symbols must be unique")
        seen.add(symbol)

    if not isinstance(limits, dict):
        _invariant("Spec.limits must be an object")
    timeout = limits.get("solver_timeout_ms") if isinstance(limits, dict) else None
    if not isinstance(timeout, int) or timeout < 0:
        _invariant("Spec.limits.solver_timeout_ms must be a non-negative integer")


def _validate_complete_grid(obj: Dict[str, Any]) -> None:
    spec = _load_spec_for(obj)
    size = spec.get("size") if spec else None
    alphabet = spec.get("alphabet") if spec else None

    encoding = obj.get("encoding")
    if not (isinstance(encoding, dict) and encoding.get("kind") == "row-major-string"):
        _invariant("encoding.kind must be 'row-major-string'")
    if encoding.get("alphabet") != "as-in-spec":
        _invariant("encoding.alphabet must be 'as-in-spec'")

    grid = obj.get("grid")
    if not isinstance(grid, str) or not grid:
        _invariant("grid must be a non-empty string")

    if isinstance(size, int):
        expected_length = size * size
        if len(grid) != expected_length:
            _invariant("grid length must match size*size from the spec")
    if isinstance(alphabet, list):
        alphabet_set = set(alphabet)
        if any(ch not in alphabet_set for ch in grid):
            _invariant("grid may only contain symbols from the spec alphabet")

    canonical_hash = obj.get("canonical_hash")
    if not (isinstance(canonical_hash, str) and canonical_hash.startswith("sha256-")):
        _invariant("canonical_hash must be a sha256 reference")
    expected_hash = hashlib.sha256(grid.encode("utf-8")).hexdigest()
    if canonical_hash != f"sha256-{expected_hash}":
        _invariant("canonical_hash does not match grid contents")


def _validate_verdict(obj: Dict[str, Any]) -> None:
    unique = obj.get("unique")
    if not isinstance(unique, bool):
        _invariant("unique must be a boolean")

    time_ms = obj.get("time_ms")
    if not isinstance(time_ms, int) or time_ms < 0:
        _invariant("time_ms must be a non-negative integer")

    nodes = obj.get("nodes")
    if nodes is not None and (not isinstance(nodes, int) or nodes < 0):
        _invariant("nodes must be a non-negative integer or null")

    cutoff = obj.get("cutoff")
    allowed_cutoffs = {None, "TIMEOUT", "SECOND_SOLUTION_FOUND"}
    if cutoff not in allowed_cutoffs:
        _invariant("cutoff must be null, 'TIMEOUT' or 'SECOND_SOLUTION_FOUND'")

    candidate_ref = obj.get("candidate_ref")
    solved_ref = obj.get("solved_ref")
    if not candidate_ref and not solved_ref:
        _invariant("Either candidate_ref or solved_ref must be provided")
    if candidate_ref and not (isinstance(candidate_ref, str) and candidate_ref.startswith("sha256-")):
        _invariant("candidate_ref must be an artifact reference")
    if solved_ref and not (isinstance(solved_ref, str) and solved_ref.startswith("sha256-")):
        _invariant("solved_ref must be an artifact reference")
    if unique and not solved_ref:
        _invariant("unique verdicts must provide solved_ref")


def _validate_export_bundle(obj: Dict[str, Any]) -> None:
    inputs = obj.get("inputs")
    if not isinstance(inputs, dict):
        _invariant("inputs must be an object")
    for key in ("complete_ref", "verdict_ref"):
        ref = inputs.get(key)
        if not (isinstance(ref, str) and ref.startswith("sha256-")):
            _invariant(f"inputs.{key} must be a sha256 reference")

    target = obj.get("target")
    if not isinstance(target, dict):
        _invariant("target must be an object")
    if target.get("format") != "pdf":
        _invariant("target.format must be 'pdf'")

    render_meta = obj.get("render_meta")
    if not isinstance(render_meta, dict):
        _invariant("render_meta must be an object")
    dpi = render_meta.get("dpi")
    if not isinstance(dpi, int) or dpi < 72:
        _invariant("render_meta.dpi must be an integer >= 72")
    page = render_meta.get("page")
    if not isinstance(page, str) or not page:
        _invariant("render_meta.page must be a non-empty string")


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
            base_uri=(_CONTRACT_ROOT / descriptor.schema_path).resolve().as_uri(),
            referrer=schema,
            store=_schema_cache,
        )
        validator = Validator(schema, resolver=resolver)
        try:
            validator.validate(obj)
        except jsonschema.ValidationError as exc:
            raise SchemaValidationError("invariant-violation", exc.message) from exc
    else:  # pragma: no cover - exercised when jsonschema is absent
        _manual_validate(obj)

    # Manual invariants complement JSON Schema even when jsonschema is present.
    _manual_validate(obj)


__all__ = [
    "SchemaDescriptor",
    "SchemaValidationError",
    "get_schema_descriptor",
    "load_schema",
    "validate_envelope",
    "validate_artifact",
]
