"""Aggregation helpers for shadow mismatch logs."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Iterable, Mapping

from contracts.jsoncanon import jcs_dump

__all__ = ["aggregate"]


def _load_events(paths: Iterable[Path]) -> Iterable[Mapping[str, object]]:
    for path in paths:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            yield json.loads(line)


def aggregate(paths: Iterable[Path], *, top: int = 5) -> Mapping[str, object]:
    severities = Counter()
    kinds = Counter()
    samples = 0
    for event in _load_events(paths):
        if event.get("event") != "shadow_compare.completed":
            continue
        samples += 1
        severity = str(event.get("severity", "UNKNOWN"))
        severities[severity] += 1
        kind = str(event.get("kind", "unknown"))
        kinds[kind] += 1

    summary = {
        "total_events": samples,
        "severity": severities,
        "top_kinds": kinds.most_common(top),
    }
    # Canonicalise summary for deterministic snapshots
    summary["canonical"] = jcs_dump(summary).decode("utf-8")
    return summary
