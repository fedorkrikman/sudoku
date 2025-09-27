from __future__ import annotations

import importlib.util
import sys
import json
from pathlib import Path


def _load_overhead_module():
    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location("shadow_overhead_guard", root / "tools" / "ci" / "shadow_overhead_guard.py")
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise RuntimeError("unable to load shadow_overhead_guard module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


overhead = _load_overhead_module()


def test_overhead_guard_generates_report(tmp_path, monkeypatch) -> None:
    seeds_path = tmp_path / "seeds.txt"
    seeds_path.write_text("\n".join(str(i) for i in range(10)) + "\n", encoding="utf-8")

    durations = {
        False: [10.0, 11.0, 12.0, 13.0, 14.0],
        True: [10.5, 11.2, 12.1, 13.1, 14.2],
    }

    def fake_run(seed: str, profile: str, *, shadow_enabled: bool, sample_rate: float) -> float:
        bucket = durations[shadow_enabled]
        index = int(seed) % len(bucket)
        return bucket[index]

    monkeypatch.setattr(overhead, "_run_pipeline", fake_run)

    report_path = tmp_path / "report.json"
    monkeypatch.setattr(overhead, "_REPORT_DIR", tmp_path / "baselines")

    exit_code = overhead.main(
        [
            "--profile",
            "dev",
            "--seeds-file",
            str(seeds_path),
            "--warmup",
            "1",
            "--samples",
            "4",
            "--report",
            str(report_path),
        ]
    )
    assert exit_code == 0

    payload = json.loads(report_path.read_text("utf-8"))
    assert payload["passed"] is True
    assert payload["delta_ms"]["p95"] >= 0.1
    assert payload["base_ms"]["p95"] >= 13.0
    assert payload["shadow_ms"]["p95"] >= 13.0
    assert len(payload["top_deltas"]) <= 4

    commit = overhead._current_commit_sha()
    hw = overhead._hardware_fingerprint()
    baseline_path = (tmp_path / "baselines" / f"baseline_{commit}_{hw}_dev.json")
    assert baseline_path.exists()

    baseline_payload = json.loads(baseline_path.read_text("utf-8"))
    assert baseline_payload["runs"]
