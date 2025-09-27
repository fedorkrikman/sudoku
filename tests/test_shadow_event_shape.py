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
    assert event["type"] in {"sudoku.shadow_sample.v1", "sudoku.shadow_mismatch.v1"}

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
        "sample_rate",
        "solve_trace_sha256",
        "state_hash_sha256",
        "envelope_jcs_sha256",
    }
    assert required.issubset(event.keys())

    assert event["run_id"] == result["run_id"]
    assert event["solver_primary"] == "legacy"
    assert event["solver_shadow"] == "novus"
    if event["type"] == "sudoku.shadow_sample.v1":
        assert event["verdict_status"] == "match"
        assert "taxonomy" not in event
    else:
        assert event["verdict_status"] in {"mismatch", "budget_exhausted"}
        assert "taxonomy" in event
    assert isinstance(event["sample_rate"], str)
    assert len(event["puzzle_digest"]) == 64
    assert len(event["solve_trace_sha256"]) == 64
    assert len(event["state_hash_sha256"]) == 64
    assert len(event["envelope_jcs_sha256"]) == 64
    assert isinstance(event["time_ms_primary"], int)
    assert isinstance(event["time_ms_shadow"], int)
    assert isinstance(event.get("solved_ref_digest"), str)
    assert event["ts_iso8601"].endswith("Z")
