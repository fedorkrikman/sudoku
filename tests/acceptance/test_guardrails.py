from __future__ import annotations

from decimal import Decimal

from contracts.envelope import make_envelope

from orchestrator.shadow_compare import ShadowRun, ShadowTask, run_with_shadow


def test_guardrail_breach_marks_budget_exhausted() -> None:
    envelope = make_envelope(
        profile="dev",
        solver_id="sudoku-9x9:/legacy@",
        commit_sha="0123456789abcdef0123456789abcdef01234567",
        baseline_sha=None,
        run_id="run-guardrail",
    )

    candidate_payload = {"unique": True, "grid": "1" * 81, "time_ms": 10}
    baseline_payload = {
        "unique": True,
        "grid": "1" * 81,
        "time_ms": 2500,
        "nodes": 300_000,
        "bt_depth": 70,
    }

    task = ShadowTask(
        envelope=envelope,
        run_id="run-guardrail",
        stage="solver:check_uniqueness",
        seed="seed-guardrail",
        module_id="sudoku-9x9:/legacy@",
        profile="dev",
        sample_rate=Decimal("1"),
        sample_rate_str="1",
        hash_salt=None,
        sticky=False,
        baseline_runner=lambda: ShadowRun(verdict="ok", result_artifact=baseline_payload),
        candidate_runner=lambda: ShadowRun(verdict="ok", result_artifact=candidate_payload),
        metadata={
            "puzzle_digest": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
            "commit_sha": "0123456789abcdef0123456789abcdef01234567",
            "baseline_sha": "89abcdef0123456789abcdef0123456789abcdef",
        },
        allow_fallback=False,
        primary_impl="legacy",
        secondary_impl="novus",
        log_mismatch=False,
        complete_artifact={"grid": "123456789" * 9},
    )

    result = run_with_shadow(task)
    event = result.event

    assert event["verdict_status"] == "budget_exhausted"
    assert event["taxonomy"]["code"] == "C4"
    assert event["taxonomy"]["severity"] == "MAJOR"
    assert event["nodes"] == 300_000
    assert event["bt_depth"] == 70
    assert event["time_ms"] >= 2500
    assert "nodes" in event["limit_hit"]
    assert result.taxonomy == event["taxonomy"]
