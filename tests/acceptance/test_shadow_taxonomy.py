from __future__ import annotations

from decimal import Decimal

import orchestrator.shadow_compare as shadow_compare
from orchestrator.shadow_compare import ShadowOutcome, ShadowRun, classify_mismatch, run_shadow_check


def _run(verdict: str, payload: dict) -> ShadowRun:
    return ShadowRun(verdict=verdict, result_artifact=payload)


def test_classify_unique_flag_mismatch() -> None:
    base = _run("ok", {"unique": True})
    candidate = _run("unsolved", {"unique": False})
    code, reason = classify_mismatch(base, candidate)
    assert code == "C1"
    assert reason == "unique_flag_mismatch"


def test_classify_grid_difference() -> None:
    base = _run("ok", {"unique": True, "grid": "1" * 81})
    candidate = _run("ok", {"unique": True, "grid": "2" * 81})
    code, reason = classify_mismatch(base, candidate)
    assert code == "C2"
    assert reason == "grid_value_diff"


def test_classify_trace_divergence() -> None:
    base = _run("ok", {"unique": True, "grid": "1" * 81, "trace": [{"step": 1}]})
    candidate = _run("ok", {"unique": True, "grid": "1" * 81, "trace": []})
    code, reason = classify_mismatch(base, candidate)
    assert code == "C3"
    assert reason == "solve_trace_divergence"


def test_classify_format_mismatch() -> None:
    base = _run("ok", {"unique": True, "grid": "1" * 81, "candidates": {"0": [1, 2]}})
    candidate = _run("ok", {"unique": True, "grid": "1" * 81, "candidates": {"0": [1, 3]}})
    code, reason = classify_mismatch(base, candidate)
    assert code == "C5"
    assert reason == "format_canon_mismatch"


def test_classify_other_difference() -> None:
    base = _run("ok", {"unique": True, "grid": "1" * 81, "meta": "a"})
    candidate = _run("ok", {"unique": True, "grid": "1" * 81, "meta": "b"})
    code, reason = classify_mismatch(base, candidate)
    assert code == "C6"
    assert reason == "other_diff"


def test_run_shadow_check_counts_taxonomy(monkeypatch) -> None:
    baseline_payload = {"unique": True, "grid": "2" * 81}
    candidate_payload = {"unique": True, "grid": "1" * 81}

    counterpart = type(
        "Resolved",
        (),
        {"module_id": "sudoku-9x9:/novus@", "impl_id": "novus", "allow_fallback": False},
    )()
    monkeypatch.setattr(shadow_compare, "_resolve_counterpart", lambda **_: counterpart)
    monkeypatch.setattr(shadow_compare, "_invoke_solver", lambda *_, **__: baseline_payload)

    module = type(
        "Module",
        (),
        {"module_id": "sudoku-9x9:/legacy@", "impl_id": "legacy", "allow_fallback": False},
    )()

    outcome = run_shadow_check(
        puzzle_kind="sudoku-9x9",
        run_id="run-taxonomy",
        stage="solver",
        seed="seed-0002",
        profile="dev",
        module=module,
        sample_rate=Decimal("1"),
        sample_rate_str="1",
        hash_salt=None,
        sticky=False,
        spec_artifact={},
        complete_artifact={},
        primary_payload=candidate_payload,
        primary_time_ms=0,
        env={},
        options=None,
        shadow_config={"secondary": "novus"},
    )

    assert isinstance(outcome, ShadowOutcome)
    assert outcome.counters == {"shadow_mismatch_C2": 1}
