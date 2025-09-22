"""Work unit definitions for the orchestrator scaffold."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, MutableMapping, Sequence


@dataclass(frozen=True)
class WorkUnit:
    """Atomic unit of work for the orchestrator.

    Parameters mirror the high-level design document.  All collections are kept
    mapping-based to highlight that the orchestrator will interact with
    Validation Center via artifact identifiers rather than mutable payloads.
    """

    name: str
    inputs: Mapping[str, str]
    params: Mapping[str, Any]
    expected_outputs: Sequence[str]
    capabilities: Mapping[str, bool]
    policy: Mapping[str, Any]


@dataclass
class Result:
    """Container for executor results."""

    work_unit: WorkUnit
    outputs: MutableMapping[str, str]
    metrics: MutableMapping[str, Any]
    status: str = "pending"


__all__ = ["Result", "WorkUnit"]
