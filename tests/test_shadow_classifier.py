from __future__ import annotations

from orchestrator.shadow_compare import ShadowRun, classify_mismatch


def test_classifies_identical_results_as_none():
    base = ShadowRun(verdict="ok", result_artifact={"grid": "123"})
    cand = ShadowRun(verdict="ok", result_artifact={"grid": "123"})
    kind, severity = classify_mismatch(base, cand)
    assert (kind, severity) == ("none", "NONE")


def test_detects_nondeterminism():
    base = ShadowRun(verdict="ok", result_artifact={"grid": "123"})
    cand = ShadowRun(verdict="unsolved", result_artifact={"grid": "123"})
    kind, severity = classify_mismatch(base, cand)
    assert severity == "CRITICAL"
    assert kind == "nondeterminism"


def test_detects_value_change():
    base = ShadowRun(verdict="ok", result_artifact={"grid": "123", "candidates": [1, 2]})
    cand = ShadowRun(verdict="ok", result_artifact={"grid": "456", "candidates": [1, 2]})
    kind, severity = classify_mismatch(base, cand)
    assert kind == "value"
    assert severity == "CRITICAL"


def test_detects_candidate_difference():
    base = ShadowRun(verdict="ok", result_artifact={"grid": "123", "candidates": [1, 2]})
    cand = ShadowRun(verdict="ok", result_artifact={"grid": "123", "candidates": [2, 3]})
    kind, severity = classify_mismatch(base, cand)
    assert kind == "candidates"
    assert severity == "MAJOR"
