"""Primary Sudoku pipeline orchestrator (Spec → Grid → Verdict → Export)."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from artifacts import artifact_store
from contracts import loader, validator
import make_sudoku_pdf
import sudoku_generator
import sudoku_solver
from project_config import get_section

_DEFAULT_OUTPUT_DIR = "exports"


def _deterministic_created_at(seed: str, stage: str) -> str:
    anchor = datetime(2023, 1, 1, tzinfo=timezone.utc)
    digest = uuid.uuid5(uuid.NAMESPACE_OID, f"{seed}|{stage}").int
    offset_ms = digest % (24 * 60 * 60 * 1000)
    moment = anchor + timedelta(milliseconds=offset_ms)
    return moment.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _deterministic_duration(seed: str, stage: str) -> int:
    digest = uuid.uuid5(uuid.NAMESPACE_X500, f"duration|{seed}|{stage}").int
    return digest % 2000


def derive_seed(root_seed: str, stage: str, parent_id: Optional[str]) -> str:
    """Derive a deterministic child seed from the root seed and stage context."""

    material = "|".join([root_seed, stage, parent_id or ""])
    return uuid.uuid5(uuid.NAMESPACE_URL, material).hex


def build_spec_from_config() -> Dict[str, Any]:
    """Construct the Spec payload from the static project configuration."""

    puzzle = get_section("PUZZLE")
    block = puzzle.get("block", {})
    limits = get_section("LIMITS")

    spec_payload: Dict[str, Any] = {
        "name": puzzle["name"],
        "size": puzzle["size"],
        "block": {
            "rows": block["rows"],
            "cols": block["cols"],
        },
        "alphabet": list(puzzle["alphabet"]),
        "limits": {
            "solver_timeout_ms": limits["solver_timeout_ms"],
        },
    }
    return spec_payload


def _base_envelope(
    artifact_type: str,
    *,
    run_id: str,
    seed: str,
    stage: str,
    parents: List[str],
    spec_ref: Optional[str],
) -> Dict[str, Any]:
    descriptor = loader.get_descriptor(artifact_type)
    envelope: Dict[str, Any] = {
        "type": artifact_type,
        "schema_version": descriptor.version,
        "schema_id": descriptor.schema_id,
        "schema_path": descriptor.schema_path,
        "created_at": _deterministic_created_at(seed, stage),
        "puzzle_type": "sudoku",
        "spec_ref": spec_ref if spec_ref is not None else None,
        "run_id": run_id,
        "seed": seed,
        "stage": stage,
        "parents": list(parents),
        "metrics": {"time_ms": 0},
        "warnings": [],
        "errors": [],
        "ext": {},
    }
    return envelope


def _finalise_and_store(artifact: Dict[str, Any], expect_type: str, profile: str | None) -> str:
    artifact["artifact_id"] = artifact_store.compute_artifact_id(artifact)
    validator.assert_valid(artifact, expect_type=expect_type, profile=profile, store=artifact_store)
    return artifact_store.save_artifact(artifact)


def run_pipeline(output_dir: str = _DEFAULT_OUTPUT_DIR) -> Dict[str, Any]:
    """Execute the end-to-end pipeline and return resulting artifact identifiers."""

    root_seed = os.environ.get("PUZZLE_ROOT_SEED", "default-root-seed")
    run_id = f"run-{uuid.uuid5(uuid.NAMESPACE_URL, root_seed).hex[:12]}"
    results: Dict[str, Any] = {"run_id": run_id, "root_seed": root_seed}

    current_profile = os.environ.get("PUZZLE_VALIDATION_PROFILE", "dev")

    # Stage 1: build and persist the Spec artifact.
    spec_stage = "stage.config.spec"
    spec_seed = derive_seed(root_seed, spec_stage, None)
    spec_payload = build_spec_from_config()
    spec_artifact = _base_envelope(
        "Spec",
        run_id=run_id,
        seed=spec_seed,
        stage=spec_stage,
        parents=[],
        spec_ref=None,
    )
    spec_artifact.update(spec_payload)
    spec_artifact["metrics"]["time_ms"] = _deterministic_duration(spec_seed, spec_stage)
    spec_id = _finalise_and_store(spec_artifact, "Spec", current_profile)
    results["spec_id"] = spec_id

    # Stage 2: generate a complete grid.
    complete_stage = "stage.generate.complete"
    complete_seed = derive_seed(root_seed, complete_stage, spec_id)
    complete_payload = sudoku_generator.port_generate_complete(spec_artifact, seed=complete_seed)
    complete_artifact = _base_envelope(
        "CompleteGrid",
        run_id=run_id,
        seed=complete_seed,
        stage=complete_stage,
        parents=[spec_id],
        spec_ref=spec_id,
    )
    complete_artifact.update(complete_payload)
    complete_artifact["metrics"]["time_ms"] = _deterministic_duration(complete_seed, complete_stage)
    complete_id = _finalise_and_store(complete_artifact, "CompleteGrid", current_profile)
    results["complete_id"] = complete_id

    # Stage 3: verify uniqueness / solved state.
    verdict_stage = "stage.solve.verify"
    verdict_seed = derive_seed(root_seed, verdict_stage, complete_id)
    verdict_payload = sudoku_solver.port_check_uniqueness(
        spec_artifact,
        complete_artifact,
        options=None,
    )
    verdict_artifact = _base_envelope(
        "Verdict",
        run_id=run_id,
        seed=verdict_seed,
        stage=verdict_stage,
        parents=[spec_id, complete_id],
        spec_ref=spec_id,
    )
    verdict_artifact.update(verdict_payload)
    verdict_artifact["metrics"]["time_ms"] = _deterministic_duration(verdict_seed, verdict_stage)
    verdict_id = _finalise_and_store(verdict_artifact, "Verdict", current_profile)
    results["verdict_id"] = verdict_id

    # Stage 4: build export bundle.
    bundle_stage = "stage.export.bundle"
    bundle_seed = derive_seed(root_seed, bundle_stage, verdict_id)
    render = get_section("RENDER")
    bundle_payload = {
        "inputs": {"complete_ref": complete_id, "verdict_ref": verdict_id},
        "target": {"format": render["format"], "template": render["template"]},
        "render_meta": {"page": render["page"], "dpi": render["dpi"]},
    }
    bundle_artifact = _base_envelope(
        "ExportBundle",
        run_id=run_id,
        seed=bundle_seed,
        stage=bundle_stage,
        parents=[complete_id, verdict_id],
        spec_ref=spec_id,
    )
    bundle_artifact.update(bundle_payload)
    bundle_artifact["metrics"]["time_ms"] = _deterministic_duration(bundle_seed, bundle_stage)
    bundle_id = _finalise_and_store(bundle_artifact, "ExportBundle", current_profile)
    results["exportbundle_id"] = bundle_id

    # Stage 5: invoke export port and return metadata.
    export_result = make_sudoku_pdf.port_export(bundle_artifact, output_dir=output_dir)
    results["pdf_path"] = export_result["pdf_path"]
    results["export_time_ms"] = export_result["time_ms"]

    return results


__all__ = ["derive_seed", "build_spec_from_config", "run_pipeline"]
