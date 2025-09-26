from __future__ import annotations

import json
from pathlib import Path

from tools.reports import mismatch_report


def _write_events(path: Path, events: list[dict]) -> None:
    lines = [json.dumps(event, sort_keys=True) for event in events]
    path.write_text("\n".join(lines), encoding="utf-8")


def test_aggregate_returns_plain_dicts(tmp_path):
    events = [
        {"event": "shadow_compare.completed", "severity": "CRITICAL", "kind": "value"},
        {"event": "shadow_compare.completed", "severity": "MINOR", "kind": "trace"},
        {"event": "shadow_compare.skipped", "severity": "NONE", "kind": "none"},
    ]
    log_path = tmp_path / "log.jsonl"
    _write_events(log_path, events)

    summary = mismatch_report.aggregate([log_path], top=2)

    assert summary["total_events"] == 2
    assert summary["severity"] == {"CRITICAL": 1, "MINOR": 1}
    assert isinstance(summary["severity"], dict)
    assert summary["top_kinds"] == [("value", 1), ("trace", 1)]

    canonical = json.loads(summary["canonical"])
    expected_top = [[kind, count] for kind, count in summary["top_kinds"]]
    assert canonical == {
        "total_events": summary["total_events"],
        "severity": summary["severity"],
        "top_kinds": expected_top,
    }
