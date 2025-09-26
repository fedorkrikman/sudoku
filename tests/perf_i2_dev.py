"""Smoke tests for shadow mismatch report aggregation."""

from __future__ import annotations

from pathlib import Path

from tools.reports.mismatch_report import aggregate


def test_aggregate_counts(tmp_path: Path):
    payload = {
        "event": "shadow_compare.completed",
        "severity": "CRITICAL",
        "kind": "value",
    }
    log_path = tmp_path / "shadow.jsonl"
    log_path.write_text("\n".join([str(payload).replace("'", '"') for _ in range(3)]))

    summary = aggregate([log_path], top=2)
    assert summary["total_events"] == 3
    assert summary["severity"]["CRITICAL"] == 3
    assert summary["top_kinds"][0][0] == "value"
