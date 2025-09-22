"""Validation severity profiles (dev/ci/prod)."""

from __future__ import annotations


from dataclasses import dataclass, field, replace
from typing import Dict, FrozenSet, Mapping

from .errors import SEVERITY_WARN, ValidationIssue


@dataclass(frozen=True)
class ProfileConfig:
    """Profile toggles that govern which checks are executed."""

    name: str
    check_schema: bool = True
    check_invariants: bool = True
    check_crossrefs: bool = True
    warn_as_error: bool = False
    invariant_rules: Mapping[str, FrozenSet[str]] = field(default_factory=dict)
    crossref_rules: Mapping[str, FrozenSet[str]] = field(default_factory=dict)
    severity_overrides: Mapping[str, Mapping[str, str]] = field(default_factory=dict)

    def is_invariant_enabled(self, artifact_type: str, rule_name: str) -> bool:
        rules = self.invariant_rules.get(artifact_type)
        return rules is None or rule_name in rules

    def is_crossref_enabled(self, artifact_type: str, rule_name: str) -> bool:
        rules = self.crossref_rules.get(artifact_type)
        return rules is None or rule_name in rules

    def apply_overrides(self, artifact_type: str, issue: ValidationIssue) -> ValidationIssue:
        overrides: Dict[str, str] = {}
        general = self.severity_overrides.get("*", {})
        if general:
            overrides.update(general)
        specific = self.severity_overrides.get(artifact_type, {})
        if specific:
            overrides.update(specific)
        desired = overrides.get(issue.code)
        if desired and desired != issue.severity:
            return replace(issue, severity=desired)
        return issue


_DEV_RULES = {
    "Spec": frozenset({"spec_size", "spec_alphabet_length", "spec_alphabet_unique", "spec_solver_timeout"}),
    "CompleteGrid": frozenset({"grid_encoding", "grid_length", "grid_symbols", "grid_canonical_hash"}),
    "Verdict": frozenset({"verdict_xor", "verdict_unique", "verdict_time", "verdict_cutoff"}),
    "ExportBundle": frozenset({"bundle_format"}),
}

_DEV_CROSSREFS = {
    "CompleteGrid": frozenset({"spec_ref_exists"}),
    "Verdict": frozenset({"spec_ref_exists", "verdict_refs_exist"}),
    "ExportBundle": frozenset({"bundle_inputs_exist", "bundle_types_match", "bundle_spec_consistency"}),
}

_PROD_INVARIANTS = {
    "Spec": frozenset({"spec_size", "spec_alphabet_length", "spec_alphabet_unique", "spec_solver_timeout"}),
    "CompleteGrid": frozenset({"grid_encoding", "grid_length", "grid_symbols"}),
    "Verdict": frozenset({"verdict_xor", "verdict_unique", "verdict_time", "verdict_cutoff"}),
    "ExportBundle": frozenset({"bundle_format"}),
}

_PROD_CROSSREFS = _DEV_CROSSREFS

_PROFILES: Dict[str, ProfileConfig] = {
    "dev": ProfileConfig(
        name="dev",
        check_schema=True,
        check_invariants=True,
        check_crossrefs=True,
        warn_as_error=False,
        invariant_rules=_DEV_RULES,
        crossref_rules=_DEV_CROSSREFS,
        severity_overrides={},
    ),
    "ci": ProfileConfig(
        name="ci",
        check_schema=True,
        check_invariants=True,
        check_crossrefs=True,
        warn_as_error=True,
        invariant_rules=_DEV_RULES,
        crossref_rules=_DEV_CROSSREFS,
        severity_overrides={},
    ),
    "prod": ProfileConfig(
        name="prod",
        check_schema=True,
        check_invariants=True,
        check_crossrefs=True,
        warn_as_error=False,
        invariant_rules=_PROD_INVARIANTS,
        crossref_rules=_PROD_CROSSREFS,
        severity_overrides={
            "Verdict": {"verdict.cutoff.invalid": SEVERITY_WARN},
        },
    ),
}


def get_profile(name: str | None) -> ProfileConfig:
    """Return the profile matching *name* (defaults to ``dev``)."""

    if not name:
        name = "dev"
    key = name.lower()
    if key not in _PROFILES:
        raise ValueError(f"Unknown validation profile: {name}")
    return _PROFILES[key]


__all__ = ["ProfileConfig", "get_profile"]
