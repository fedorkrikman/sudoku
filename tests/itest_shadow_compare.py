from __future__ import annotations

import json

import pytest

from contracts.envelope import make_envelope
from orchestrator import log as shadow_log
from orchestrator.shadow_compare import (
    GuardrailContext,
    ShadowRun,
    ShadowTask,
    run_with_shadow,
)


@pytest.fixture(autouse=True)
def configure_log(tmp_path):
    shadow_log.configure(tmp_path)
    return tmp_path


def _make_task(*, sample_rate: float, guardrail=None) -> ShadowTask:
    envelope = make_envelope(profile="dev", solver_id="solver", commit_sha="abc123")

    def baseline_runner() -> ShadowRun:
        return ShadowRun(verdict="ok", result_artifact={"grid": "123", "candidates": [1, 2]})

    def candidate_runner() -> ShadowRun:
        return ShadowRun(verdict="ok", result_artifact={"grid": "123", "candidates": [1, 2]})

    return ShadowTask(
        envelope=envelope,
        run_id="run-1",
        stage="solver",
        seed="feed",
        module_id="solver:novus",
        profile="dev",
        sample_rate=sample_rate,
        hash_salt="salt",
        baseline_runner=baseline_runner,
        candidate_runner=candidate_runner,
        guardrail=guardrail,
    )


def test_run_with_shadow_logs_event(tmp_path):
    task = _make_task(sample_rate=1.0)
    result = run_with_shadow(task)

    assert result.sampled is True
    assert result.event_path is not None
    content = result.event_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(content) == 1
    payload = json.loads(content[0])
    assert payload["event"] == "shadow_compare.completed"
    assert payload["severity"] == "NONE"
    assert payload["digests"]["baseline"] == payload["digests"]["candidate"]


def test_guardrail_triggers_fallback(tmp_path):
    def guardrail(ctx: GuardrailContext) -> bool:
        return True

    task = _make_task(sample_rate=1.0, guardrail=guardrail)
    result = run_with_shadow(task)
    assert result.fallback_used is True
    assert result.returned == result.baseline


def test_no_sample_skips_logging(tmp_path):
    task = _make_task(sample_rate=0.0)
    result = run_with_shadow(task)
    assert result.sampled is False
    assert result.event_path is None
