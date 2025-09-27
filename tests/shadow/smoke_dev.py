from __future__ import annotations

import json
from decimal import Decimal

from contracts.envelope import make_envelope
from orchestrator import log as shadow_log
from orchestrator.shadow_compare import ShadowRun, ShadowTask, run_with_shadow


def test_shadow_sample_skip(tmp_path):
    shadow_log.configure(tmp_path)
    task = ShadowTask(
        envelope=make_envelope(profile="dev", solver_id="solver", commit_sha="abc"),
        run_id="run-123",
        stage="solver",
        seed="seed",
        module_id="solver:novus",
        profile="dev",
        sample_rate=Decimal("0"),
        sample_rate_str="0",
        hash_salt="salt",
        sticky=False,
        baseline_runner=lambda: ShadowRun(verdict="ok", result_artifact={"grid": "123"}),
        candidate_runner=lambda: ShadowRun(verdict="ok", result_artifact={"grid": "123"}),
    )
    result = run_with_shadow(task)
    assert result.sampled is False
    assert result.event_path is None


def test_shadow_logs_event(tmp_path):
    shadow_log.configure(tmp_path)

    baseline = ShadowRun(verdict="ok", result_artifact={"grid": "123", "candidates": [1, 2]})
    candidate = ShadowRun(verdict="ok", result_artifact={"grid": "124", "candidates": [1, 2]})

    task = ShadowTask(
        envelope=make_envelope(profile="dev", solver_id="solver", commit_sha="abc"),
        run_id="run-123",
        stage="solver",
        seed="seed",
        module_id="solver:novus",
        profile="dev",
        sample_rate=Decimal("1"),
        sample_rate_str="1",
        hash_salt="salt",
        sticky=False,
        baseline_runner=lambda: baseline,
        candidate_runner=lambda: candidate,
    )

    result = run_with_shadow(task)
    assert result.sampled is True
    assert result.event_path is not None
    payload = json.loads(result.event_path.read_text().splitlines()[0])
    assert payload["kind"] == "value"
    assert payload["severity"] == "CRITICAL"
