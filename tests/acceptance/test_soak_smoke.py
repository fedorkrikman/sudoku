from __future__ import annotations

import importlib.util
import sys
import json
from pathlib import Path


def _load_soak_module():
    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location("soak_run", root / "tools" / "ci" / "soak_run.py")
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise RuntimeError("unable to load soak_run module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


soak = _load_soak_module()


def test_soak_runner_produces_summary(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(soak, "_SOAK_BASE", tmp_path / "soak")

    def fake_run_pipeline(*, env_overrides: dict[str, str], **_: object) -> dict[str, object]:
        seed_value = env_overrides.get("PUZZLE_ROOT_SEED", "soak-0000")
        seed_index = int(seed_value.split("-")[-1])
        base_event = {
            "type": "sudoku.shadow_sample.v1",
            "run_id": f"run-{seed_index:04d}",
            "ts_iso8601": "2023-01-01T00:00:00.000Z",
            "commit_sha": "0123456789abcdef0123456789abcdef01234567",
            "baseline_sha": "0123456789abcdef0123456789abcdef01234567",
            "hw_fingerprint": "0011223344556677",
            "profile": env_overrides.get("PUZZLE_VALIDATION_PROFILE", "dev"),
            "puzzle_digest": "f" * 64,
            "solver_primary": "legacy",
            "solver_shadow": "novus",
            "verdict_status": "match",
            "time_ms_primary": 5,
            "time_ms_shadow": 6,
            "diff_summary": "none",
            "solved_ref_digest": "f" * 64,
            "sample_rate": "1",
            "solve_trace_sha256": "1" * 64,
            "state_hash_sha256": "2" * 64,
            "envelope_jcs_sha256": "3" * 64,
        }
        if seed_index % 5 == 0:
            base_event.update(
                {
                    "type": "sudoku.shadow_mismatch.v1",
                    "verdict_status": "mismatch",
                    "diff_summary": "C1:unique_flag_mismatch",
                    "taxonomy": {"code": "C1", "severity": "CRITICAL", "reason": "unique_flag_mismatch"},
                }
            )
        elif seed_index % 7 == 0:
            base_event.update(
                {
                    "type": "sudoku.shadow_mismatch.v1",
                    "verdict_status": "budget_exhausted",
                    "diff_summary": "C4:time_ms",
                    "taxonomy": {"code": "C4", "severity": "MAJOR", "reason": "guardrail_exceeded_time_ms"},
                    "nodes": 210000,
                    "bt_depth": 70,
                    "time_ms": 2400,
                    "limit_hit": "time_ms",
                }
            )
        return {"shadow": {"event": base_event, "counters": {}}}

    monkeypatch.setattr(soak.orchestrator, "run_pipeline", fake_run_pipeline)

    out_path = tmp_path / "summary.json"
    exit_code = soak.main(
        [
            "--n",
            "20",
            "--out",
            str(out_path),
            "--profile",
            "dev",
            "--seed",
            "20250927",
        ]
    )
    assert exit_code == 0

    summary = json.loads(out_path.read_text("utf-8"))
    assert summary["processed"] == min(20, soak._SEED_UPPER)
    assert summary["failures"]
    assert summary["taxonomy"]["C1"] >= 1
    assert summary["status"] in {"PASS", "WARN"}

    dated_dir = (tmp_path / "soak" / summary["timestamp"][:10].replace("-", "") )
    assert (dated_dir / "summary.json").exists()
