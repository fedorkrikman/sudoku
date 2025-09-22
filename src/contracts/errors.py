"""Shared error types for the Validation Center."""

from __future__ import annotations


from dataclasses import dataclass
from typing import List

SEVERITY_ERROR = "ERROR"
SEVERITY_WARN = "WARN"


@dataclass(frozen=True)
class ValidationIssue:
    """Single validation finding produced by a rule or schema check."""

    code: str
    msg: str
    path: str
    severity: str


@dataclass(frozen=True)
class ValidationReport:
    """Aggregate result of running the Validation Center."""

    ok: bool
    errors: List[ValidationIssue]
    warnings: List[ValidationIssue]
    timings_ms: dict[str, int]


def make_error(code: str, msg: str, path: str) -> ValidationIssue:
    """Construct an error-level :class:`ValidationIssue`."""

    return ValidationIssue(code=code, msg=msg, path=path, severity=SEVERITY_ERROR)


def make_warning(code: str, msg: str, path: str) -> ValidationIssue:
    """Construct a warning-level :class:`ValidationIssue`."""

    return ValidationIssue(code=code, msg=msg, path=path, severity=SEVERITY_WARN)


__all__ = [
    "SEVERITY_ERROR",
    "SEVERITY_WARN",
    "ValidationIssue",
    "ValidationReport",
    "make_error",
    "make_warning",
]
