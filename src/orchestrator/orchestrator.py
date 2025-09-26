"""Primary Sudoku pipeline orchestrator (Spec → Grid → Verdict → Export)."""

from __future__ import annotations

import argparse
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Mapping, Optional

from artifacts import artifact_store
from contracts import loader, validator
from feature_flags import is_shadow_mode_enabled
from ports import generator_port, printer_port, solver_port
from project_config import get_section

from .shadow_compare import run_shadow_check

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


def build_spec_from_config(puzzle_kind: str) -> Dict[str, Any]:
    """Construct the Spec payload from the static project configuration."""

    puzzle = get_section("PUZZLE")
    block = puzzle.get("block", {})
    limits = get_section("LIMITS")

    spec_payload: Dict[str, Any] = {
        "name": puzzle_kind,
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


def _merge_env(overrides: Mapping[str, str] | None = None) -> Dict[str, str]:
    env: Dict[str, str] = {str(k): str(v) for k, v in os.environ.items()}
    if overrides:
        env.update({str(k): str(v) for k, v in overrides.items()})
    return env


def _extract_shadow_hash_salt(env: Mapping[str, str]) -> str | None:
    for key in ("PUZZLE_SHADOW_HASH_SALT", "SHADOW_HASH_SALT"):
        value = env.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _extract_shadow_rate_override(env: Mapping[str, str]) -> float | None:
    for key in (
        "PUZZLE_SHADOW_RATE",
        "PUZZLE_SHADOW_SAMPLE_RATE",
        "SHADOW_RATE",
        "SHADOW_SAMPLE_RATE",
    ):
        value = env.get(key)
        if value is None:
            continue
        try:
            rate = float(value)
        except (TypeError, ValueError):
            continue
        return max(0.0, min(1.0, rate))
    return None


def _select_puzzle_kind(
    cli_override: Optional[str], env: Mapping[str, str], profile: str
) -> str:
    if cli_override:
        return cli_override

    env_override = env.get("PUZZLE_KIND")
    if env_override:
        return env_override

    run_cfg = get_section("run", default={})
    if isinstance(run_cfg, dict):
        by_profile = run_cfg.get("by_profile")
        if isinstance(by_profile, dict):
            profile_cfg = by_profile.get(profile)
            if isinstance(profile_cfg, dict):
                value = profile_cfg.get("puzzle_kind")
                if isinstance(value, str) and value:
                    return value
        value = run_cfg.get("puzzle_kind")
        if isinstance(value, str) and value:
            return value

    raise RuntimeError(
        "Puzzle kind must be selected explicitly via --puzzle, PUZZLE_KIND or run.puzzle_kind"
    )


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


def run_pipeline(
    *,
    puzzle_kind: Optional[str] = None,
    output_dir: str = _DEFAULT_OUTPUT_DIR,
    env_overrides: Mapping[str, str] | None = None,
) -> Dict[str, Any]:
    """Execute the end-to-end pipeline and return resulting artifact identifiers."""

    env_map = _merge_env(env_overrides)

    root_seed = env_map.get("PUZZLE_ROOT_SEED", "default-root-seed")
    run_id = f"run-{uuid.uuid5(uuid.NAMESPACE_URL, root_seed).hex[:12]}"
    current_profile = env_map.get("PUZZLE_VALIDATION_PROFILE", "dev")

    selected_puzzle = _select_puzzle_kind(puzzle_kind, env_map, current_profile)

    results: Dict[str, Any] = {
        "run_id": run_id,
        "root_seed": root_seed,
        "puzzle_kind": selected_puzzle,
        "profile": current_profile,
        "modules": {},
    }

    module_journal: Dict[str, Dict[str, Any]] = {}

    # Stage 1: build and persist the Spec artifact.
    spec_stage = "stage.config.spec"
    spec_seed = derive_seed(root_seed, spec_stage, None)
    spec_payload = build_spec_from_config(selected_puzzle)
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
    complete_payload, generator_module = generator_port.generate_complete(
        selected_puzzle,
        spec_artifact,
        seed=complete_seed,
        profile=current_profile,
        env=env_map,
    )
    module_journal["generator"] = {
        "module_id": generator_module.module_id,
        "impl": generator_module.impl_id,
        "state": generator_module.state,
        "decision_source": generator_module.decision_source,
        "fallback_used": generator_module.fallback_used,
    }
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
    verdict_payload, solver_module = solver_port.check_uniqueness(
        selected_puzzle,
        spec_artifact,
        complete_artifact,
        options=None,
        profile=current_profile,
        env=env_map,
    )
    module_journal["solver"] = {
        "module_id": solver_module.module_id,
        "impl": solver_module.impl_id,
        "state": solver_module.state,
        "decision_source": solver_module.decision_source,
        "fallback_used": solver_module.fallback_used,
        "sample_rate": solver_module.sample_rate,
    }
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

    shadow_enabled = is_shadow_mode_enabled(env_map)
    shadow_rate = _extract_shadow_rate_override(env_map)
    effective_rate = shadow_rate if shadow_rate is not None else solver_module.sample_rate
    module_journal["solver"]["sample_rate"] = effective_rate

    if shadow_enabled:
        shadow_outcome = run_shadow_check(
            puzzle_kind=selected_puzzle,
            run_id=run_id,
            stage="solver:check_uniqueness",
            seed=verdict_seed,
            profile=current_profile,
            module=solver_module,
            sample_rate=effective_rate,
            hash_salt=_extract_shadow_hash_salt(env_map),
            spec_artifact=spec_artifact,
            complete_artifact=complete_artifact,
            primary_payload=verdict_payload,
            primary_time_ms=verdict_artifact["metrics"]["time_ms"],
            env=env_map,
            options=None,
        )
        module_journal["solver"]["shadow_sampled"] = shadow_outcome.event.payload.get("sampled", False)
        results["shadow"] = {
            "event": shadow_outcome.event.payload,
            "counters": shadow_outcome.counters,
        }
    else:
        module_journal["solver"]["shadow_sampled"] = False
        results["shadow"] = {
            "event": {
                "event": "shadow_compare.disabled",
                "sampled": False,
                "reason": "feature_disabled",
            },
            "counters": {},
        }

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

    # Stage 5: ensure cross-references are still consistent before export.
    crossref_report = validator.check_refs(bundle_id, store=artifact_store, profile=current_profile)
    if not crossref_report.ok:
        raise validator.ManagedValidationError(
            "Export bundle failed cross-reference check",
            crossref_report,
        )

    # Invoke export port and return metadata.
    export_result, printer_module = printer_port.export_bundle(
        selected_puzzle,
        bundle_artifact,
        output_dir=output_dir,
        profile=current_profile,
        env=env_map,
    )
    module_journal["printer"] = {
        "module_id": printer_module.module_id,
        "impl": printer_module.impl_id,
        "state": printer_module.state,
        "decision_source": printer_module.decision_source,
        "fallback_used": printer_module.fallback_used,
    }
    results["pdf_path"] = export_result["pdf_path"]
    results["export_time_ms"] = export_result["time_ms"]
    results["modules"] = module_journal

    return results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the Sudoku pipeline for a selected puzzle kind.",
    )
    parser.add_argument(
        "--puzzle",
        dest="puzzle_kind",
        help="Puzzle kind identifier (e.g. 'sudoku-9x9'). Overrides config and environment.",
    )
    parser.add_argument(
        "--output-dir",
        default=_DEFAULT_OUTPUT_DIR,
        help=(
            "Directory where exported bundles are written. "
            f"Defaults to '{_DEFAULT_OUTPUT_DIR}'."
        ),
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = run_pipeline(puzzle_kind=args.puzzle_kind, output_dir=args.output_dir)
    except RuntimeError as exc:
        parser.error(str(exc))
    print(
        f"Run {result['run_id']} completed for puzzle {result['puzzle_kind']} "
        f"using modules: {', '.join(sorted(result['modules'].keys()))}"
    )
    return 0


__all__ = ["derive_seed", "build_spec_from_config", "run_pipeline", "build_parser", "main"]


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
