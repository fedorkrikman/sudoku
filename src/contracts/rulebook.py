"""Central registry of invariants and cross-reference rules."""

from __future__ import annotations


import hashlib
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Optional, Protocol

from .errors import ValidationIssue, make_error, make_warning
from .profiles import ProfileConfig


class ArtifactResolver(Protocol):
    def __call__(self, artifact_id: str) -> dict:  # pragma: no cover - structural typing
        ...


@dataclass(frozen=True)
class InvariantRule:
    name: str
    check: Callable[[dict, Optional[dict], ProfileConfig], Iterable[ValidationIssue]]


@dataclass(frozen=True)
class CrossRefRule:
    name: str
    check: Callable[[dict, Optional[object], Optional[ArtifactResolver], ProfileConfig], Iterable[ValidationIssue]]


def _expect_int(value: object, path: str, code: str, desc: str) -> List[ValidationIssue]:
    if isinstance(value, int):
        return []
    return [make_error(code, f"{desc} must be an integer", path)]



def _spec_size(artifact: dict, _spec: Optional[dict], _profile: ProfileConfig) -> Iterable[ValidationIssue]:
    issues: List[ValidationIssue] = []
    size = artifact.get("size")
    block = artifact.get("block", {})
    rows = block.get("rows") if isinstance(block, dict) else None
    cols = block.get("cols") if isinstance(block, dict) else None

    if not isinstance(size, int):
        issues.extend(_expect_int(size, "$.size", "type.mismatch", "Spec.size"))
        return issues

    if not isinstance(rows, int) or not isinstance(cols, int):
        issues.append(make_error("envelope.missing_field", "block.rows and block.cols must be integers", "$.block"))
        return issues

    if size != rows * cols:
        issues.append(
            make_error(
                "invariant.spec.size_block_mismatch",
                f"size {size} does not match block dimensions {rows}x{cols}",
                "$.size",
            )
        )
    return issues


def _spec_alphabet_length(artifact: dict, _spec: Optional[dict], _profile: ProfileConfig) -> Iterable[ValidationIssue]:
    issues: List[ValidationIssue] = []
    alphabet = artifact.get("alphabet")
    size = artifact.get("size")
    if not isinstance(alphabet, list):
        issues.append(make_error("type.mismatch", "alphabet must be an array", "$.alphabet"))
        return issues
    if not isinstance(size, int):
        issues.extend(_expect_int(size, "$.size", "type.mismatch", "Spec.size"))
        return issues
    if len(alphabet) != size:
        issues.append(
            make_error(
                "invariant.spec.alphabet_length",
                f"alphabet length {len(alphabet)} does not equal size {size}",
                "$.alphabet",
            )
        )
    return issues


def _spec_alphabet_unique(artifact: dict, _spec: Optional[dict], _profile: ProfileConfig) -> Iterable[ValidationIssue]:
    issues: List[ValidationIssue] = []
    alphabet = artifact.get("alphabet")
    if not isinstance(alphabet, list):
        return issues
    seen = set()
    for index, symbol in enumerate(alphabet):
        if not isinstance(symbol, str):
            issues.append(make_error("type.mismatch", "alphabet entries must be strings", f"$.alphabet[{index}]"))
            continue
        if symbol in seen:
            issues.append(
                make_error(
                    "invariant.spec.alphabet_unique",
                    f"symbol {symbol!r} is duplicated in alphabet",
                    f"$.alphabet[{index}]",
                )
            )
        seen.add(symbol)
    return issues


def _spec_solver_timeout(artifact: dict, _spec: Optional[dict], _profile: ProfileConfig) -> Iterable[ValidationIssue]:
    limits = artifact.get("limits")
    if not isinstance(limits, dict):
        return [make_error("envelope.missing_field", "limits section is required", "$.limits")]
    timeout = limits.get("solver_timeout_ms")
    if not isinstance(timeout, int) or timeout < 0:
        return [
            make_error(
                "invariant.spec.limits_solver_timeout",
                "limits.solver_timeout_ms must be a non-negative integer",
                "$.limits.solver_timeout_ms",
            )
        ]
    return []


def _grid_encoding(artifact: dict, _spec: Optional[dict], _profile: ProfileConfig) -> Iterable[ValidationIssue]:
    encoding = artifact.get("encoding")
    if not isinstance(encoding, dict):
        return [make_error("type.mismatch", "encoding must be an object", "$.encoding")]
    kind = encoding.get("kind")
    if kind != "row-major-string":
        return [
            make_error(
                "invariant.grid.encoding_kind",
                f"encoding.kind must be 'row-major-string', got {kind!r}",
                "$.encoding.kind",
            )
        ]
    return []


def _grid_length(artifact: dict, spec: Optional[dict], _profile: ProfileConfig) -> Iterable[ValidationIssue]:
    grid = artifact.get("grid")
    if not isinstance(grid, str):
        return [make_error("type.mismatch", "grid must be a string", "$.grid")]
    if not spec or not isinstance(spec.get("size"), int):
        return []
    size = spec["size"]
    expected = size * size
    if len(grid) != expected:
        return [
            make_error(
                "invariant.grid.length",
                f"grid length {len(grid)} does not equal size^2 ({expected})",
                "$.grid",
            )
        ]
    return []


def _grid_symbols(artifact: dict, spec: Optional[dict], _profile: ProfileConfig) -> Iterable[ValidationIssue]:
    grid = artifact.get("grid")
    if not isinstance(grid, str) or not spec:
        return []
    alphabet = spec.get("alphabet")
    if not isinstance(alphabet, list):
        return []
    allowed = set(symbol for symbol in alphabet if isinstance(symbol, str))
    issues: List[ValidationIssue] = []
    for index, symbol in enumerate(grid):
        if symbol not in allowed:
            issues.append(
                make_error(
                    "invariant.grid.symbol_out_of_alphabet",
                    f"symbol {symbol!r} not present in Spec alphabet",
                    f"$.grid[{index}]",
                )
            )
    return issues


def _grid_canonical_hash(artifact: dict, _spec: Optional[dict], _profile: ProfileConfig) -> Iterable[ValidationIssue]:
    canonical = artifact.get("canonical_hash")
    grid = artifact.get("grid")
    if canonical is None or not isinstance(grid, str):
        return []
    if not isinstance(canonical, str):
        return [make_warning("invariant.grid.canonical_hash", "canonical_hash must be a string", "$.canonical_hash")]
    digest = hashlib.sha256(grid.encode("utf-8")).hexdigest()
    expected = f"sha256-{digest}"
    if canonical != expected:
        return [
            make_warning(
                "invariant.grid.canonical_hash",
                f"canonical_hash {canonical!r} does not match computed {expected!r}",
                "$.canonical_hash",
            )
        ]
    return []


def _verdict_xor(artifact: dict, _spec: Optional[dict], _profile: ProfileConfig) -> Iterable[ValidationIssue]:
    candidate_ref = artifact.get("candidate_ref")
    solved_ref = artifact.get("solved_ref")
    present = [ref for ref in (candidate_ref, solved_ref) if isinstance(ref, str) and ref]
    if len(present) != 1:
        return [
            make_error(
                "verdict.input_ref.xor_violation",
                "Exactly one of candidate_ref or solved_ref must be provided",
                "$.candidate_ref",
            )
        ]
    return []


def _verdict_unique(artifact: dict, _spec: Optional[dict], _profile: ProfileConfig) -> Iterable[ValidationIssue]:
    unique = artifact.get("unique")
    if isinstance(unique, bool):
        return []
    return [make_error("type.mismatch", "unique must be a boolean", "$.unique")]


def _verdict_time(artifact: dict, _spec: Optional[dict], _profile: ProfileConfig) -> Iterable[ValidationIssue]:
    time_ms = artifact.get("time_ms")
    if not isinstance(time_ms, int) or time_ms < 0:
        return [make_error("verdict.time.invalid", "time_ms must be non-negative integer", "$.time_ms")]
    return []


def _verdict_cutoff(artifact: dict, _spec: Optional[dict], _profile: ProfileConfig) -> Iterable[ValidationIssue]:
    cutoff = artifact.get("cutoff")
    allowed = {None, "TIMEOUT", "SECOND_SOLUTION_FOUND"}
    if cutoff not in allowed:
        return [
            make_error(
                "verdict.cutoff.invalid",
                "cutoff must be null, 'TIMEOUT' or 'SECOND_SOLUTION_FOUND'",
                "$.cutoff",
            )
        ]
    return []


def _bundle_format(artifact: dict, _spec: Optional[dict], _profile: ProfileConfig) -> Iterable[ValidationIssue]:
    target = artifact.get("target")
    if not isinstance(target, dict):
        return [make_error("envelope.missing_field", "target section is required", "$.target")]
    fmt = target.get("format")
    if fmt != "pdf":
        return [make_error("invariant.export.format", "target.format must be 'pdf'", "$.target.format")]
    return []


def _resolve(artifact_id: str, resolver: Optional[ArtifactResolver], path: str) -> tuple[Optional[dict], List[ValidationIssue]]:
    if resolver is None:
        return None, [make_warning("crossref.artifact_missing", "store resolver not configured", path)]
    try:
        resolved = resolver(artifact_id)
    except FileNotFoundError:
        return None, [make_error("crossref.artifact_missing", f"artifact {artifact_id} not found", path)]
    except Exception as exc:  # pragma: no cover - defensive
        return None, [make_error("crossref.artifact_missing", f"failed to resolve {artifact_id}: {exc}", path)]
    return resolved, []


def _grid_spec_ref(artifact: dict, _store: Optional[object], resolver: Optional[ArtifactResolver], _profile: ProfileConfig) -> Iterable[ValidationIssue]:
    spec_ref = artifact.get("spec_ref")
    if not isinstance(spec_ref, str) or not spec_ref:
        return [make_error("crossref.artifact_missing", "spec_ref must reference a Spec", "$.spec_ref")]
    resolved, issues = _resolve(spec_ref, resolver, "$.spec_ref")
    if issues:
        return issues
    if resolved.get("type") != "Spec":
        return [make_error("crossref.type_mismatch", "spec_ref must point to Spec", "$.spec_ref")]
    return []


def _verdict_refs_exist(artifact: dict, _store: Optional[object], resolver: Optional[ArtifactResolver], _profile: ProfileConfig) -> Iterable[ValidationIssue]:
    issues: List[ValidationIssue] = []
    for field in ("candidate_ref", "solved_ref"):
        ref = artifact.get(field)
        if ref is None:
            continue
        if not isinstance(ref, str) or not ref:
            issues.append(make_error("crossref.type_mismatch", f"{field} must be a reference id", f"$.{field}"))
            continue
        resolved, new_issues = _resolve(ref, resolver, f"$.{field}")
        issues.extend(new_issues)
        if resolved and resolved.get("type") != "CompleteGrid":
            issues.append(make_error("crossref.type_mismatch", f"{field} must point to CompleteGrid", f"$.{field}"))
    return issues


def _bundle_inputs_exist(artifact: dict, _store: Optional[object], resolver: Optional[ArtifactResolver], _profile: ProfileConfig) -> Iterable[ValidationIssue]:
    inputs = artifact.get("inputs")
    if not isinstance(inputs, dict):
        return [make_error("envelope.missing_field", "inputs section is required", "$.inputs")]
    issues: List[ValidationIssue] = []
    for field in ("complete_ref", "verdict_ref"):
        ref = inputs.get(field)
        if not isinstance(ref, str) or not ref:
            issues.append(make_error("crossref.artifact_missing", f"{field} must be a reference id", f"$.inputs.{field}"))
            continue
        resolved, new_issues = _resolve(ref, resolver, f"$.inputs.{field}")
        issues.extend(new_issues)
    return issues


def _bundle_types_match(artifact: dict, _store: Optional[object], resolver: Optional[ArtifactResolver], _profile: ProfileConfig) -> Iterable[ValidationIssue]:
    inputs = artifact.get("inputs")
    if not isinstance(inputs, dict):
        return []
    issues: List[ValidationIssue] = []
    refs = {
        "complete_ref": "CompleteGrid",
        "verdict_ref": "Verdict",
    }
    for field, expected_type in refs.items():
        ref = inputs.get(field)
        if not isinstance(ref, str) or not ref:
            continue
        resolved, new_issues = _resolve(ref, resolver, f"$.inputs.{field}")
        issues.extend(new_issues)
        if resolved and resolved.get("type") != expected_type:
            issues.append(
                make_error(
                    "crossref.type_mismatch",
                    f"{field} must point to {expected_type}",
                    f"$.inputs.{field}",
                )
            )
    return issues


def _bundle_spec_consistency(artifact: dict, _store: Optional[object], resolver: Optional[ArtifactResolver], _profile: ProfileConfig) -> Iterable[ValidationIssue]:
    bundle_spec = artifact.get("spec_ref")
    if not isinstance(bundle_spec, str) or not bundle_spec:
        return []
    issues: List[ValidationIssue] = []
    inputs = artifact.get("inputs") if isinstance(artifact.get("inputs"), dict) else None
    if not isinstance(inputs, dict):
        return []
    for field in ("complete_ref", "verdict_ref"):
        ref = inputs.get(field)
        if not isinstance(ref, str) or not ref:
            continue
        resolved, new_issues = _resolve(ref, resolver, f"$.inputs.{field}")
        issues.extend(new_issues)
        if resolved and resolved.get("spec_ref") != bundle_spec:
            issues.append(
                make_error(
                    "crossref.spec_mismatch",
                    f"{field} spec_ref {resolved.get('spec_ref')!r} does not match bundle spec_ref {bundle_spec!r}",
                    f"$.inputs.{field}",
                )
            )
    return issues


_RULES: Dict[str, Dict[str, List[object]]] = {
    "Spec": {
        "invariants": [
            InvariantRule("spec_size", _spec_size),
            InvariantRule("spec_alphabet_length", _spec_alphabet_length),
            InvariantRule("spec_alphabet_unique", _spec_alphabet_unique),
            InvariantRule("spec_solver_timeout", _spec_solver_timeout),
        ],
        "crossrefs": [],
    },
    "CompleteGrid": {
        "invariants": [
            InvariantRule("grid_encoding", _grid_encoding),
            InvariantRule("grid_length", _grid_length),
            InvariantRule("grid_symbols", _grid_symbols),
            InvariantRule("grid_canonical_hash", _grid_canonical_hash),
        ],
        "crossrefs": [
            CrossRefRule("spec_ref_exists", _grid_spec_ref),
        ],
    },
    "Verdict": {
        "invariants": [
            InvariantRule("verdict_xor", _verdict_xor),
            InvariantRule("verdict_unique", _verdict_unique),
            InvariantRule("verdict_time", _verdict_time),
            InvariantRule("verdict_cutoff", _verdict_cutoff),
        ],
        "crossrefs": [
            CrossRefRule("spec_ref_exists", _grid_spec_ref),
            CrossRefRule("verdict_refs_exist", _verdict_refs_exist),
        ],
    },
    "ExportBundle": {
        "invariants": [
            InvariantRule("bundle_format", _bundle_format),
        ],
        "crossrefs": [
            CrossRefRule("bundle_inputs_exist", _bundle_inputs_exist),
            CrossRefRule("bundle_types_match", _bundle_types_match),
            CrossRefRule("bundle_spec_consistency", _bundle_spec_consistency),
        ],
    },
}


def run_invariants(artifact: dict, spec_for_context: Optional[dict], profile: ProfileConfig) -> List[ValidationIssue]:
    rules = _RULES.get(artifact.get("type"), {}).get("invariants", [])
    issues: List[ValidationIssue] = []
    for rule in rules:
        if isinstance(rule, InvariantRule) and profile.is_invariant_enabled(artifact.get("type", ""), rule.name):
            issues.extend(rule.check(artifact, spec_for_context, profile))
    return issues


def run_crossrefs(artifact: dict, store: Optional[object], resolver: Optional[ArtifactResolver], profile: ProfileConfig) -> List[ValidationIssue]:
    rules = _RULES.get(artifact.get("type"), {}).get("crossrefs", [])
    issues: List[ValidationIssue] = []
    for rule in rules:
        if isinstance(rule, CrossRefRule) and profile.is_crossref_enabled(artifact.get("type", ""), rule.name):
            issues.extend(rule.check(artifact, store, resolver, profile))
    return issues


RULES = _RULES

__all__ = [
    "ArtifactResolver",
    "CrossRefRule",
    "InvariantRule",
    "RULES",
    "run_crossrefs",
    "run_invariants",
]
