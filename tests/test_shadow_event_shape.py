from __future__ import annotations

from orchestrator import orchestrator


def test_shadow_event_payload_contains_required_fields() -> None:
    overrides = {
        "PUZZLE_ROOT_SEED": "shadow-event-seed",
        "CLI_SHADOW_ENABLED": "1",
        "CLI_SHADOW_SAMPLE_RATE": "1.0",
    }
    result = orchestrator.run_pipeline(env_overrides=overrides)

    event = result["shadow"]["event"]
    assert event["type"] == "sudoku.shadow_sample.v1"

    required = {
        "run_id",
        "ts_iso8601",
        "commit_sha",
        "baseline_sha",
        "hw_fingerprint",
        "profile",
        "puzzle_digest",
        "solver_primary",
        "solver_shadow",
        "verdict_status",
        "time_ms_primary",
        "time_ms_shadow",
        "diff_summary",
        "solved_ref_digest",
    }
    assert required.issubset(event.keys())

    assert event["run_id"] == result["run_id"]
    assert event["solver_primary"] == "legacy"
    assert event["solver_shadow"] == "novus"
    assert event["verdict_status"] == "match"
    assert isinstance(event["time_ms_primary"], float)
    assert isinstance(event["time_ms_shadow"], float)
    assert isinstance(event["solved_ref_digest"], str)
    assert event["ts_iso8601"].endswith("Z")
