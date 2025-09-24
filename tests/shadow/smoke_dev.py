"""Smoke coverage for the shadow comparison orchestration layer."""

from __future__ import annotations

import dataclasses

import pytest

from orchestrator import shadow_compare
from orchestrator.shadow_compare import run_shadow_check
from orchestrator.router import ResolvedModule, resolve


@pytest.fixture()
def solved_grid() -> str:
    return (
        "123456789"
        "456789123"
        "789123456"
        "214365897"
        "365897214"
        "897214365"
        "531642978"
        "642978531"
        "978531642"
    )


@pytest.fixture()
def spec_payload() -> dict:
    return {
        "name": "sudoku-9x9",
        "size": 9,
        "block": {"rows": 3, "cols": 3},
        "alphabet": list("123456789"),
        "limits": {"solver_timeout_ms": 1000},
    }


@pytest.fixture()
def complete_artifact(solved_grid: str) -> dict:
    return {"grid": solved_grid, "artifact_id": "sha256-complete-grid"}


@pytest.fixture()
def primary_payload(spec_payload: dict, complete_artifact: dict) -> dict:
    from sudoku_solver import port_check_uniqueness

    return port_check_uniqueness(spec_payload, complete_artifact)


@pytest.fixture()
def resolved_module() -> ResolvedModule:
    resolved = resolve(
        "sudoku-9x9",
        "solver",
        "dev",
        {"PUZZLE_SOLVER_IMPL": "novus", "PUZZLE_SOLVER_STATE": "shadow"},
    )
    return dataclasses.replace(resolved, sample_rate=1.0)


def _run_shadow(
    *,
    resolved_module: ResolvedModule,
    spec_payload: dict,
    complete_artifact: dict,
    primary_payload: dict,
    sample_rate: float,
) -> shadow_compare.ShadowOutcome:
    shadow_compare.reset_state()
    return run_shadow_check(
        puzzle_kind="sudoku-9x9",
        run_id="run-test-01",
        stage="solver:check_uniqueness",
        seed="feedface1234",
        profile="dev",
        module=dataclasses.replace(resolved_module, sample_rate=sample_rate),
        sample_rate=sample_rate,
        hash_salt=None,
        spec_artifact=spec_payload,
        complete_artifact=complete_artifact,
        primary_payload=primary_payload,
        primary_time_ms=42,
        env={},
        options=None,
    )


def test_shadow_sample_miss(resolved_module, spec_payload, complete_artifact, primary_payload):
    outcome = _run_shadow(
        resolved_module=resolved_module,
        spec_payload=spec_payload,
        complete_artifact=complete_artifact,
        primary_payload=primary_payload,
        sample_rate=0.0,
    )
    event = outcome.event.payload
    assert event["sampled"] is False
    assert "shadow_info" in outcome.counters
    state = shadow_compare.get_state()
    assert state.counters["shadow_info"] == 1


def test_shadow_happy_path_sample_hit(resolved_module, spec_payload, complete_artifact, primary_payload):
    outcome = _run_shadow(
        resolved_module=resolved_module,
        spec_payload=spec_payload,
        complete_artifact=complete_artifact,
        primary_payload=primary_payload,
        sample_rate=1.0,
    )
    event = outcome.event.payload
    assert event["sampled"] is True
    assert event["category"] == "OK"
    assert outcome.counters["shadow_ok"] == 1
    assert len(event["event_id"]) == 8
    assert event["ts"].startswith("2024-")


@pytest.mark.parametrize(
    "code,expected_counter",
    [
        ("C1", "shadow_mismatch_C1"),
        ("C2", "shadow_mismatch_C2"),
        ("M1", "shadow_mismatch_M1"),
        ("M2", "shadow_mismatch_M2"),
        ("E2", "shadow_error_E2"),
    ],
)
def test_shadow_injections(monkeypatch, resolved_module, spec_payload, complete_artifact, primary_payload, code, expected_counter):
    def fake_compare(*args, **kwargs):
        return code, {"injected": code}

    monkeypatch.setattr(shadow_compare, "_compare_payloads", fake_compare)
    outcome = _run_shadow(
        resolved_module=resolved_module,
        spec_payload=spec_payload,
        complete_artifact=complete_artifact,
        primary_payload=primary_payload,
        sample_rate=1.0,
    )
    assert outcome.event.payload["category"] == code
    assert expected_counter in outcome.counters


def test_shadow_exception_injected(monkeypatch, resolved_module, spec_payload, complete_artifact, primary_payload):
    def boom(*args, **kwargs):  # pragma: no cover - error path instrumentation
        raise RuntimeError("boom")

    monkeypatch.setattr(shadow_compare, "_invoke_solver", boom)
    outcome = _run_shadow(
        resolved_module=resolved_module,
        spec_payload=spec_payload,
        complete_artifact=complete_artifact,
        primary_payload=primary_payload,
        sample_rate=1.0,
    )
    assert outcome.event.payload["category"] == "E1"
    assert "shadow_error_E1" in outcome.counters


def test_event_id_determinism(resolved_module, spec_payload, complete_artifact, primary_payload):
    outcome_first = _run_shadow(
        resolved_module=resolved_module,
        spec_payload=spec_payload,
        complete_artifact=complete_artifact,
        primary_payload=primary_payload,
        sample_rate=1.0,
    )
    first_id = outcome_first.event.payload["event_id"]
    outcome_second = _run_shadow(
        resolved_module=resolved_module,
        spec_payload=spec_payload,
        complete_artifact=complete_artifact,
        primary_payload=primary_payload,
        sample_rate=1.0,
    )
    assert outcome_second.event.payload["event_id"] == first_id
