"""Micro-benchmark smoke coverage for the I2 performance scenario."""

from __future__ import annotations

import json
from pathlib import Path

from orchestrator.shadow_compare import PerfCase, run_perf_benchmark, write_perf_reports


def _load_cases() -> list[PerfCase]:
    payload = json.loads(Path("tests/perf_i2_dev.json").read_text())
    return [PerfCase(**entry) for entry in payload["cases"]]


def test_perf_i2_microbenchmark(tmp_path):
    cases = _load_cases()
    assert len(cases) == 60

    metrics = run_perf_benchmark(cases, warmup_runs=1, measure_runs=3)
    assert len(metrics) == len(cases)
    assert all(len(metric.samples) == 3 for metric in metrics)

    json_path, md_path = write_perf_reports(
        metrics=metrics,
        output_dir=tmp_path,
        warmup_runs=1,
        measure_runs=3,
    )

    json_payload = json.loads(json_path.read_text())
    assert json_payload["meta"]["warmup_runs"] == 1
    assert json_payload["meta"]["measure_runs"] == 3
    assert len(json_payload["cases"]) == len(metrics)

    md_lines = md_path.read_text().strip().splitlines()
    assert md_lines[0].startswith("# I2 microbenchmark")
