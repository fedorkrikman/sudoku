"""Validate shadow events against the published JSON schema."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping

try:  # optional dependency
    import jsonschema
except Exception:  # pragma: no cover - handled via fallback
    jsonschema = None  # type: ignore[assignment]

ROOT = Path(__file__).resolve().parents[2]


def _load_events(path: Path) -> List[Mapping[str, Any]]:
    events: List[Mapping[str, Any]] = []
    for line_no, line in enumerate(path.read_text("utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:  # pragma: no cover - defensive
            raise SystemExit(f"invalid JSON on line {line_no}: {exc}")
        if not isinstance(payload, Mapping):
            raise SystemExit(f"event on line {line_no} must be an object")
        events.append(payload)
    return events


def _load_schema(path: Path) -> Mapping[str, Any]:
    try:
        return json.loads(path.read_text("utf-8"))
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise SystemExit(f"invalid schema JSON: {exc}")


def _expect_type(value: Any, schema: Mapping[str, Any], label: str) -> None:
    expected = schema.get("type")
    if expected == "object":
        if not isinstance(value, Mapping):
            raise ValueError(f"{label} must be an object")
    elif expected == "string":
        if not isinstance(value, str):
            raise ValueError(f"{label} must be a string")
    elif expected == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{label} must be an integer")
    elif expected is not None:
        raise ValueError(f"unsupported schema type '{expected}' for {label}")


def _check_string(value: str, schema: Mapping[str, Any], label: str) -> None:
    enum = schema.get("enum")
    if enum is not None and value not in enum:
        raise ValueError(f"{label} must be one of {enum}")
    pattern = schema.get("pattern")
    if pattern and re.fullmatch(pattern, value) is None:
        raise ValueError(f"{label} does not match pattern {pattern!r}")
    if "minLength" in schema and len(value) < int(schema["minLength"]):
        raise ValueError(f"{label} shorter than minimum length {schema['minLength']}")
    const = schema.get("const")
    if const is not None and value != const:
        raise ValueError(f"{label} must equal {const!r}")


def _check_integer(value: int, schema: Mapping[str, Any], label: str) -> None:
    if "minimum" in schema and value < int(schema["minimum"]):
        raise ValueError(f"{label} must be >= {schema['minimum']}")
    const = schema.get("const")
    if const is not None and value != const:
        raise ValueError(f"{label} must equal {const}")


def _apply_if_then(event: Mapping[str, Any], clause: Mapping[str, Any]) -> None:
    condition = clause.get("if")
    if not isinstance(condition, Mapping):
        return

    def matches(payload: Mapping[str, Any], predicate: Mapping[str, Any]) -> bool:
        props = predicate.get("properties")
        if not isinstance(props, Mapping):
            return False
        for key, subschema in props.items():
            if key not in payload:
                return False
            expected = subschema.get("const")
            if expected is None:
                return False
            if payload[key] != expected:
                return False
        return True

    if matches(event, condition):
        then_clause = clause.get("then")
        if isinstance(then_clause, Mapping):
            _validate_object(event, then_clause, "event")


def _validate_object(event: Mapping[str, Any], schema: Mapping[str, Any], label: str) -> None:
    _expect_type(event, schema, label)
    required = schema.get("required", [])
    for key in required:
        if key not in event:
            raise ValueError(f"missing required field {label}.{key}")

    properties = schema.get("properties", {})
    for key, subschema in properties.items():
        if key not in event:
            continue
        value = event[key]
        sublabel = f"{label}.{key}" if label else key
        _expect_type(value, subschema, sublabel)
        expected_type = subschema.get("type")
        if expected_type == "object":
            _validate_object(value, subschema, sublabel)
        elif expected_type == "string":
            _check_string(value, subschema, sublabel)
        elif expected_type == "integer":
            _check_integer(value, subschema, sublabel)
        else:
            if "const" in subschema and value != subschema["const"]:
                raise ValueError(f"{sublabel} must equal {subschema['const']!r}")

    additional = schema.get("additionalProperties", True)
    if additional is False:
        allowed = set(properties.keys())
        extras = [key for key in event.keys() if key not in allowed]
        if extras:
            raise ValueError(f"unexpected fields on {label}: {sorted(extras)}")

    for clause in schema.get("allOf", []):
        if isinstance(clause, Mapping):
            _apply_if_then(event, clause)


def _fallback_validate(event: Mapping[str, Any], schema: Mapping[str, Any]) -> None:
    _validate_object(event, schema, "event")


def _validate_with_jsonschema(events: Iterable[Mapping[str, Any]], schema: Mapping[str, Any]) -> List[str]:
    validator = jsonschema.Draft7Validator(schema)  # type: ignore[attr-defined]
    errors: List[str] = []
    for index, event in enumerate(events):
        for error in validator.iter_errors(event):  # pragma: no cover - exercised via acceptance
            pointer = "/".join(str(part) for part in error.path)
            errors.append(f"event[{index}] {pointer}: {error.message}")
    return errors


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", type=Path, required=True, help="Path to JSON schema")
    parser.add_argument("--events", type=Path, required=True, help="Path to shadow events JSONL")
    args = parser.parse_args(list(argv) if argv is not None else None)

    schema = _load_schema(args.schema)
    events = _load_events(args.events)

    if jsonschema is not None:
        errors = _validate_with_jsonschema(events, schema)
    else:
        errors = []
        for index, event in enumerate(events):
            try:
                _fallback_validate(event, schema)
            except ValueError as exc:
                errors.append(f"event[{index}]: {exc}")

    if errors:
        for message in errors:
            print(message, file=sys.stderr)
        return 1

    print(f"Validated {len(events)} events against {args.schema.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
