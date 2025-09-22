"""Public facade for the Validation Center."""

from __future__ import annotations

import os
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

from . import loader, profiles, rulebook
from .errors import (
    SEVERITY_WARN,
    ManagedValidationError,
    ValidationIssue,
    ValidationReport,
    make_error,
)
from .profiles import ProfileConfig

try:  # Optional dependency for schema validation
    import jsonschema  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - optional dependency
    jsonschema = None  # type: ignore[assignment]


class _StoreResolver:
    """Adapter providing caching ``load_artifact`` access for cross-ref rules."""

    def __init__(self, loader: Callable[[str], dict]) -> None:
        self._loader = loader
        self._cache: Dict[str, dict] = {}

    def load_artifact(self, artifact_id: str) -> dict:
        if artifact_id in self._cache:
            return self._cache[artifact_id]
        resolved = self._loader(artifact_id)
        self._cache[artifact_id] = resolved
        return resolved

    def try_load(self, artifact_id: str) -> Optional[dict]:
        try:
            return self.load_artifact(artifact_id)
        except Exception:  # pragma: no cover - defensive
            return None


def _choose_profile(profile: str | ProfileConfig | None) -> ProfileConfig:
    if isinstance(profile, ProfileConfig):
        return profile
    if profile in (None, "", "auto"):
        env = os.environ.get("PUZZLE_VALIDATION_PROFILE")
        return profiles.get_profile(env)
    return profiles.get_profile(str(profile))


def _coerce_resolver(store: Any) -> Tuple[Any, Optional[_StoreResolver]]:
    if store is None:
        return None, None
    if isinstance(store, _StoreResolver):
        return store, store
    if callable(store):  # direct resolver
        adapter = _StoreResolver(store)
        return adapter, adapter
    loader = getattr(store, "load_artifact", None)
    if callable(loader):  # type: ignore[arg-type]
        adapter = _StoreResolver(loader)  # type: ignore[arg-type]
        return store, adapter
    raise TypeError("store must expose a callable or load_artifact()")


def _jsonschema_path(exc: Exception) -> str:
    if jsonschema is None:
        return "$.schema"
    path = getattr(exc, "absolute_path", [])
    if not path:
        return "$.schema"
    components: List[str] = ["$"]
    for part in path:
        if isinstance(part, int):
            components.append(f"[{part}]")
        else:
            components.append(f".{part}")
    return "".join(components)


def _check_iso8601(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _envelope_checks(artifact: Dict[str, Any], expect_type: str, descriptor: loader.SchemaDescriptor | None) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    artifact_type = artifact.get("type")
    if artifact_type != expect_type:
        issues.append(make_error("type.mismatch", f"Expected type {expect_type!r}, got {artifact_type!r}", "$.type"))
    if descriptor is None:
        return issues

    if artifact.get("schema_version") != descriptor.version:
        issues.append(make_error("schema.mismatch_version", "schema_version does not match catalog", "$.schema_version"))
    if artifact.get("schema_id") != descriptor.schema_id:
        issues.append(make_error("schema.mismatch_id", "schema_id does not match catalog", "$.schema_id"))
    if artifact.get("schema_path") != descriptor.schema_path:
        issues.append(make_error("schema.mismatch_path", "schema_path does not match catalog", "$.schema_path"))

    spec_ref = artifact.get("spec_ref")
    if expect_type == "Spec":
        if spec_ref not in (None, ""):
            issues.append(make_error("envelope.bad_type", "Spec must not define spec_ref", "$.spec_ref"))
    else:
        if not isinstance(spec_ref, str) or not spec_ref:
            issues.append(make_error("envelope.missing_field", "spec_ref must reference a Spec", "$.spec_ref"))

    artifact_id = artifact.get("artifact_id")
    if not isinstance(artifact_id, str) or not artifact_id.startswith("sha256-"):
        issues.append(make_error("envelope.missing_field", "artifact_id must start with 'sha256-'", "$.artifact_id"))

    created_at = artifact.get("created_at")
    if not _check_iso8601(created_at):
        issues.append(make_error("envelope.bad_type", "created_at must be ISO8601 string", "$.created_at"))

    if artifact.get("puzzle_type") != "sudoku":
        issues.append(make_error("envelope.bad_type", "puzzle_type must be 'sudoku'", "$.puzzle_type"))

    run_id = artifact.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        issues.append(make_error("envelope.bad_type", "run_id must be a non-empty string", "$.run_id"))

    seed = artifact.get("seed")
    if not isinstance(seed, (str, int)):
        issues.append(make_error("envelope.bad_type", "seed must be string or integer", "$.seed"))

    stage = artifact.get("stage")
    if not isinstance(stage, str) or not stage:
        issues.append(make_error("envelope.bad_type", "stage must be a non-empty string", "$.stage"))

    parents = artifact.get("parents")
    if not isinstance(parents, list):
        issues.append(make_error("envelope.bad_type", "parents must be a list", "$.parents"))
    else:
        for index, parent in enumerate(parents):
            if not isinstance(parent, str) or not parent.startswith("sha256-"):
                issues.append(make_error("envelope.bad_type", "parents must contain artifact ids", f"$.parents[{index}]"))
        if len(parents) != len(set(parents)):
            issues.append(make_error("envelope.bad_type", "parents must be unique", "$.parents"))

    metrics = artifact.get("metrics")
    if not isinstance(metrics, dict):
        issues.append(make_error("envelope.bad_type", "metrics must be an object", "$.metrics"))
    else:
        time_ms = metrics.get("time_ms")
        if not isinstance(time_ms, int) or time_ms < 0:
            issues.append(make_error("envelope.bad_type", "metrics.time_ms must be non-negative integer", "$.metrics.time_ms"))

    return issues


def _schema_stage(artifact: Any, expect_type: str, profile: ProfileConfig) -> List[ValidationIssue]:
    errors: List[ValidationIssue] = []
    if not isinstance(artifact, dict):
        errors.append(make_error("type.mismatch", "Artifact must be a JSON object", "$"))
        return errors

    descriptor: loader.SchemaDescriptor | None = None
    try:
        descriptor = loader.get_descriptor(expect_type)
    except KeyError:
        errors.append(make_error("schema.not_found", f"Unknown artifact type {expect_type}", "$.type"))

    envelope_issues = _envelope_checks(artifact, expect_type, descriptor)
    errors.extend(envelope_issues)

    if descriptor and profile.check_schema:
        try:
            schema_dict = loader.load_schema(descriptor.schema_id, descriptor.schema_path)
        except (OSError, ValueError) as exc:
            errors.append(make_error("schema.not_found", str(exc), "$.schema"))
        else:
            validator = loader.maybe_compile(schema_dict)
            if hasattr(validator, "validate"):
                try:
                    validator.validate(artifact)
                except Exception as exc:  # pragma: no cover - jsonschema errors
                    message = getattr(exc, "message", str(exc))
                    errors.append(make_error("type.mismatch", message, _jsonschema_path(exc)))
    return errors


def _apply_overrides(profile: ProfileConfig, artifact_type: str, issues: List[ValidationIssue]) -> Tuple[List[ValidationIssue], List[ValidationIssue]]:
    errors: List[ValidationIssue] = []
    warnings: List[ValidationIssue] = []
    for issue in issues:
        adjusted = profile.apply_overrides(artifact_type, issue)
        if adjusted.severity == SEVERITY_WARN:
            warnings.append(adjusted)
        else:
            errors.append(adjusted)
    return errors, warnings


def validate(
    artifact: Dict[str, Any],
    expect_type: str,
    profile: str | ProfileConfig | None = None,
    *,
    store: Any = None,
) -> ValidationReport:
    profile_cfg = _choose_profile(profile)
    timings = {"schema": 0, "invariants": 0, "crossrefs": 0}
    all_errors: List[ValidationIssue] = []
    all_warnings: List[ValidationIssue] = []

    schema_start = time.perf_counter()
    schema_issues = _schema_stage(artifact, expect_type, profile_cfg)
    schema_errors_adj, schema_warnings_adj = _apply_overrides(profile_cfg, expect_type, schema_issues)
    all_errors.extend(schema_errors_adj)
    all_warnings.extend(schema_warnings_adj)
    timings["schema"] = int((time.perf_counter() - schema_start) * 1000)

    base_store, resolver = _coerce_resolver(store)
    spec_context: Optional[dict] = artifact if expect_type == "Spec" else None
    if spec_context is None and isinstance(artifact, dict):
        spec_ref = artifact.get("spec_ref")
        if isinstance(spec_ref, str) and resolver is not None:
            candidate = resolver.try_load(spec_ref)
            if candidate and candidate.get("type") == "Spec":
                spec_context = candidate

    if profile_cfg.check_invariants and isinstance(artifact, dict):
        invariants_start = time.perf_counter()
        invariant_issues = rulebook.run_invariants(artifact, spec_context, profile_cfg)
        inv_errors, inv_warnings = _apply_overrides(profile_cfg, expect_type, invariant_issues)
        all_errors.extend(inv_errors)
        all_warnings.extend(inv_warnings)
        timings["invariants"] = int((time.perf_counter() - invariants_start) * 1000)

    if profile_cfg.check_crossrefs and isinstance(artifact, dict):
        crossref_start = time.perf_counter()
        store_for_rules = resolver if resolver is not None else base_store
        crossref_issues = rulebook.run_crossrefs(artifact, store_for_rules, profile_cfg)
        cr_errors, cr_warnings = _apply_overrides(profile_cfg, expect_type, crossref_issues)
        all_errors.extend(cr_errors)
        all_warnings.extend(cr_warnings)
        timings["crossrefs"] = int((time.perf_counter() - crossref_start) * 1000)

    ok = not all_errors
    return ValidationReport(ok=ok, errors=all_errors, warnings=all_warnings, timings_ms=timings)


def assert_valid(
    artifact: Dict[str, Any],
    expect_type: str,
    profile: str | ProfileConfig | None = None,
    *,
    store: Any = None,
) -> None:
    profile_cfg = _choose_profile(profile)
    report = validate(artifact, expect_type, profile=profile_cfg, store=store)
    if report.ok and not (profile_cfg.warn_as_error and report.warnings):
        return
    issues = report.errors[:]
    if profile_cfg.warn_as_error:
        issues.extend(report.warnings)
    codes = ", ".join(issue.code for issue in issues[:5])
    if len(issues) > 5:
        codes += ", …"
    raise ManagedValidationError(f"Validation failed for {expect_type}: {codes}", report)


def check_refs(
    bundle_or_id: Dict[str, Any] | str,
    store: Any,
    profile: str | ProfileConfig | None = None,
) -> ValidationReport:
    if store is None:
        raise ValueError("store is required for check_refs")
    base, resolver = _coerce_resolver(store)
    if resolver is None:
        raise ValueError("store must provide a resolver for check_refs")
    if isinstance(bundle_or_id, str):
        artifact = resolver.load_artifact(bundle_or_id)
    else:
        artifact = bundle_or_id
    store_arg = resolver if resolver is not None else base
    return validate(artifact, expect_type="ExportBundle", profile=profile, store=store_arg)


__all__ = [
    "ManagedValidationError",
    "assert_valid",
    "check_refs",
    "validate",
]
