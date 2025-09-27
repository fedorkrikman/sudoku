"""Run lightweight documentation consistency checks."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Iterable, List, Mapping

ROOT = Path(__file__).resolve().parents[2]

_DIGEST_KEYS = {
    "puzzle_digest",
    "solved_ref_digest",
    "solve_trace_sha256",
    "state_hash_sha256",
    "envelope_jcs_sha256",
}

_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _require_date_stamp(path: Path, expected: str) -> None:
    content = path.read_text("utf-8")
    marker = f"Verified on {expected}"
    if marker not in content:
        raise ValueError(f"{path} is missing 'Verified on {expected}' stamp")


def _require_compatibility_notes(path: Path) -> None:
    content = path.read_text("utf-8")
    if re.search(r"compatibility", content, re.IGNORECASE) is None:
        raise ValueError(f"{path} is missing compatibility notes")


def _iter_log_events(base: Path) -> Iterable[Mapping[str, object]]:
    if not base.exists():
        return []
    for jsonl_path in base.rglob("*.jsonl"):
        for line in jsonl_path.read_text("utf-8").splitlines():
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, Mapping):
                yield payload


def _check_no_fractional_numbers(value: object, *, path: str = "event") -> None:
    if isinstance(value, float):
        raise ValueError(f"{path} contains fractional float {value!r}")
    if isinstance(value, Mapping):
        for key, item in value.items():
            _check_no_fractional_numbers(item, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _check_no_fractional_numbers(item, path=f"{path}[{index}]")


def _check_log_integrity(base: Path) -> None:
    hex_pattern = re.compile(r"^[0-9a-f]{64}$")

    def _walk(value: object, path: str) -> None:
        if isinstance(value, Mapping):
            for key, item in value.items():
                _walk(item, f"{path}.{key}" if path else str(key))
        elif isinstance(value, list):
            for index, item in enumerate(value):
                _walk(item, f"{path}[{index}]")
        elif isinstance(value, float):
            raise ValueError(f"log field {path} must not be a float (got {value!r})")

    for event in _iter_log_events(base):
        _walk(event, "event")
        for key in ("time_ms_primary", "time_ms_shadow", "time_ms", "nodes", "bt_depth"):
            if key in event:
                value = event[key]
                if not isinstance(value, int):
                    raise ValueError(f"log field {key} must be integer, got {value!r}")
        for key in _DIGEST_KEYS:
            if key in event:
                value = event[key]
                if not isinstance(value, str) or hex_pattern.fullmatch(value) is None:
                    raise ValueError(f"log field {key} must be 64 hex characters")


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expect-date", required=True, help="Expected verification date string")
    parser.add_argument("--files", nargs="+", type=Path, required=True, help="Documentation files to inspect")
    parser.add_argument("--logs", type=Path, default=ROOT / "logs" / "shadow", help="Shadow log directory")
    args = parser.parse_args(list(argv) if argv is not None else None)

    failures: List[str] = []

    for doc_path in args.files:
        path = (ROOT / doc_path) if not doc_path.is_absolute() else doc_path
        if not path.exists():
            failures.append(f"missing documentation file: {path}")
            continue
        try:
            _require_date_stamp(path, args.expect_date)
        except ValueError as exc:
            failures.append(str(exc))
        try:
            _require_compatibility_notes(path)
        except ValueError as exc:
            failures.append(str(exc))

    try:
        _check_log_integrity(args.logs)
    except ValueError as exc:
        failures.append(str(exc))

    if failures:
        for message in failures:
            print(message)
        return 1

    print(f"Documentation checks passed for {len(args.files)} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
