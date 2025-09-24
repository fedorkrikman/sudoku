"""SolveTrace v1 helpers for the Nova solver."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Iterable, List, Mapping, MutableSequence, Sequence

from .delta import Delta, canonicalise_deltas


class TraceValidationError(ValueError):
    """Raised when trace entry violates SolveTrace v1 contract."""


@dataclass(frozen=True, slots=True)
class SolveTraceEntry:
    """Immutable container with SolveTrace v1 payload."""

    step: int
    technique_id: str
    deltas: Sequence[Delta]
    placements: int
    candidates_removed: int
    state_hash_before: str
    state_hash_after: str
    time_us: int | None = None
    note: str | None = None

    def __post_init__(self) -> None:
        if self.step < 1:
            raise TraceValidationError("step must be >= 1")
        if not self.technique_id:
            raise TraceValidationError("technique_id must be a non-empty string")
        if self.placements < 0:
            raise TraceValidationError("placements must be >= 0")
        if self.candidates_removed < 0:
            raise TraceValidationError("candidates_removed must be >= 0")
        if self.time_us is not None and self.time_us < 0:
            raise TraceValidationError("time_us must be >= 0 when provided")

    def to_payload(self) -> dict:
        payload = {
            "step": int(self.step),
            "technique_id": str(self.technique_id),
            "deltas": [delta.to_payload() for delta in canonicalise_deltas(self.deltas)],
            "placements": int(self.placements),
            "candidates_removed": int(self.candidates_removed),
            "state_hash_before": str(self.state_hash_before),
            "state_hash_after": str(self.state_hash_after),
            "time_us": None if self.time_us is None else int(self.time_us),
        }
        if self.note is not None:
            payload["note"] = str(self.note)
        return payload


@dataclass
class SolveTrace:
    """Mutable trace accumulator producing SolveTrace v1 JSON payloads."""

    entries: MutableSequence[SolveTraceEntry] = field(default_factory=list)

    def append(self, entry: SolveTraceEntry | Mapping[str, object]) -> None:
        if isinstance(entry, Mapping):
            entry = SolveTraceEntry(**entry)
        if self.entries and entry.step <= self.entries[-1].step:
            raise TraceValidationError("trace steps must be strictly increasing")
        self.entries.append(entry)

    def extend(self, entries: Iterable[SolveTraceEntry | Mapping[str, object]]) -> None:
        for entry in entries:
            self.append(entry)

    def snapshot(self) -> List[SolveTraceEntry]:
        return list(self.entries)

    def to_json(self, *, indent: int | None = None) -> str:
        payload = [entry.to_payload() for entry in self.entries]
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), indent=indent)


__all__ = ["SolveTrace", "SolveTraceEntry", "TraceValidationError"]
