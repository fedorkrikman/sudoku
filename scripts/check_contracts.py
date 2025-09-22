#!/usr/bin/env python3
"""Validate contract fixtures and stored artifacts offline."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from artifacts import artifact_store
from contracts import validator


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text("utf-8"))


class FixtureStore:
    def __init__(self) -> None:
        self._fixtures: dict[str, dict] = {}

    def preload(self, payload: dict) -> None:
        artifact_id = payload.get("artifact_id")
        if isinstance(artifact_id, str):
            self._fixtures[artifact_id] = payload

    def load_artifact(self, artifact_id: str) -> dict:
        if artifact_id in self._fixtures:
            return self._fixtures[artifact_id]
        return artifact_store.load_artifact(artifact_id)


def _guess_type(path: Path, payload: dict) -> str:
    value = payload.get("type")
    if isinstance(value, str) and value:
        return value
    prefix = path.stem.split("-", 1)[0].lower()
    mapping = {
        "spec": "Spec",
        "completegrid": "CompleteGrid",
        "verdict": "Verdict",
        "exportbundle": "ExportBundle",
    }
    if prefix in mapping:
        return mapping[prefix]
    raise ValueError(f"Cannot infer artifact type for {path.name}")


def _validate(path: Path, *, profile: str, store: FixtureStore) -> validator.ValidationReport:
    payload = _load_json(path)
    expect_type = _guess_type(path, payload)
    store.preload(payload)
    return validator.validate(payload, expect_type=expect_type, profile=profile, store=store)


def main() -> int:
    fixtures_root = ROOT / "PuzzleContracts" / "fixtures"
    valid_dir = fixtures_root / "valid"
    invalid_dir = fixtures_root / "invalid"

    profile = os.environ.get("PUZZLE_VALIDATION_PROFILE", "dev")
    store = FixtureStore()
    failures: list[str] = []

    for path in sorted(valid_dir.glob("*.json")):
        report = _validate(path, profile=profile, store=store)
        if not report.ok:
            codes = ", ".join(issue.code for issue in report.errors)
            failures.append(f"valid fixture failed: {path.name}: {codes}")

    for path in sorted(invalid_dir.glob("*.json")):
        payload = _load_json(path)
        expect_type = _guess_type(path, payload)
        report = validator.validate(payload, expect_type=expect_type, profile=profile, store=store)
        if report.ok:
            failures.append(f"invalid fixture unexpectedly passed: {path.name}")
        else:
            codes = [issue.code for issue in report.errors]
            codes.extend(f"warn:{issue.code}" for issue in report.warnings)
            print(f"{path.name}: {', '.join(codes)}")

    artifacts_root = ROOT / "artifacts"
    if artifacts_root.exists():
        for artifact_path in sorted(artifacts_root.glob("*/*.json")):
            payload = _load_json(artifact_path)
            expect_type = _guess_type(artifact_path, payload)
            report = validator.validate(payload, expect_type=expect_type, profile=profile, store=store)
            if not report.ok:
                codes = [issue.code for issue in report.errors]
                codes.extend(f"warn:{issue.code}" for issue in report.warnings)
                failures.append(f"stored artifact invalid: {artifact_path.name}: {', '.join(codes)}")

    if failures:
        for line in failures:
            print(line)
        return 1

    print("All contract fixtures and artifacts are valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
