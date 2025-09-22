#!/usr/bin/env python3
"""Validate contract fixtures and stored artifacts offline."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from contracts import schema_validator
from contracts.schema_validator import SchemaValidationError


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text("utf-8"))


def _validate(path: Path) -> None:
    payload = _load_json(path)
    schema_validator.validate_artifact(payload)


def main() -> int:
    fixtures_root = ROOT / "PuzzleContracts" / "fixtures"
    valid_dir = fixtures_root / "valid"
    invalid_dir = fixtures_root / "invalid"

    failures: list[str] = []

    for path in sorted(valid_dir.glob("*.json")):
        try:
            _validate(path)
        except Exception as exc:  # pragma: no cover - CLI reporting
            failures.append(f"valid fixture failed: {path.name}: {exc}")

    for path in sorted(invalid_dir.glob("*.json")):
        try:
            _validate(path)
        except SchemaValidationError:
            continue
        except Exception as exc:  # pragma: no cover - CLI reporting
            failures.append(f"invalid fixture raised unexpected error: {path.name}: {exc}")
        else:
            failures.append(f"invalid fixture unexpectedly passed: {path.name}")

    artifacts_root = ROOT / "artifacts"
    if artifacts_root.exists():
        for artifact_path in sorted(artifacts_root.glob("*/*.json")):
            try:
                _validate(artifact_path)
            except Exception as exc:  # pragma: no cover - CLI reporting
                failures.append(f"stored artifact invalid: {artifact_path.name}: {exc}")

    if failures:
        for line in failures:
            print(line)
        return 1

    print("All contract fixtures and artifacts are valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
