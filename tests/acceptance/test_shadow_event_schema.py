from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import importlib.util
import json
import sys

from contracts.envelope import make_envelope

from orchestrator.shadow_compare import ShadowRun, ShadowTask, run_with_shadow


def _load_schema_check():
    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location("schema_check", root / "tools" / "ci" / "schema_check.py")
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise RuntimeError("unable to load schema_check module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


schema_check = _load_schema_check()


def _build_task(candidate_payload: dict, baseline_payload: dict) -> ShadowTask:
    envelope = make_envelope(
        profile="dev",
        solver_id="sudoku-9x9:/legacy@",
        commit_sha="0123456789abcdef0123456789abcdef01234567",
        baseline_sha=None,
        run_id="run-shadow-schema",
    )
    return ShadowTask(
        envelope=envelope,
        run_id="run-shadow-schema",
        stage="solver:check_uniqueness",
        seed="seed-0001",
        module_id="sudoku-9x9:/legacy@",
        profile="dev",
        sample_rate=Decimal("1"),
        sample_rate_str="1",
        hash_salt=None,
        sticky=False,
        baseline_runner=lambda: ShadowRun(verdict="ok", result_artifact=baseline_payload),
        candidate_runner=lambda: ShadowRun(verdict="ok", result_artifact=candidate_payload),
        metadata={
            "puzzle_digest": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "commit_sha": "0123456789abcdef0123456789abcdef01234567",
            "baseline_sha": "89abcdef0123456789abcdef0123456789abcdef",
        },
        allow_fallback=False,
        primary_impl="legacy",
        secondary_impl="novus",
        log_mismatch=False,
        complete_artifact={"grid": "123456789" * 9},
    )


def test_mismatch_event_conforms_to_schema(tmp_path: Path) -> None:
    candidate_payload = {"unique": True, "grid": "1" * 81}
    baseline_payload = {"unique": True, "grid": "2" * 81}

    task = _build_task(candidate_payload, baseline_payload)
    result = run_with_shadow(task)
    event = result.event

    events_path = tmp_path / "events.jsonl"
    events_path.write_text(json.dumps(event, sort_keys=True) + "\n", encoding="utf-8")

    schema_path = Path("docs/icd/schemas/sudoku.shadow_mismatch.v1.schema.json")
    exit_code = schema_check.main([
        "--schema",
        str(schema_path),
        "--events",
        str(events_path),
    ])
    assert exit_code == 0

    assert event["type"] == "sudoku.shadow_mismatch.v1"
    assert event["verdict_status"] == "mismatch"
    assert event["taxonomy"]["code"] == "C2"
    assert isinstance(event["time_ms_primary"], int)
    assert isinstance(event["time_ms_shadow"], int)
