"""Delta v1 primitives shared across Nova solver components.

The production implementation will eventually operate directly on immutable
grid/candidate structures.  For the purposes of the current scaffolding we
focus on validating and ordering delta descriptors so downstream components
(trace writer, difficulty calculator) can rely on deterministic behaviour.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Iterator, Mapping, Sequence, Tuple


class DeltaValidationError(ValueError):
    """Raised when delta payload does not conform to the Delta v1 contract."""


class DeltaOp(str, Enum):
    """Supported delta kinds for Sudoku 9×9 Nova solver."""

    ELIM = "ELIM"
    PLACE = "PLACE"

    @classmethod
    def from_value(cls, value: str) -> "DeltaOp":
        try:
            return cls(value)
        except ValueError as exc:  # pragma: no cover - defensive guard
            raise DeltaValidationError(f"Unsupported delta op: {value!r}") from exc


@dataclass(frozen=True, slots=True)
class Delta:
    """Canonical representation of a single state mutation."""

    op: DeltaOp
    cell: int
    digit: int

    def __post_init__(self) -> None:
        if not isinstance(self.op, DeltaOp):
            object.__setattr__(self, "op", DeltaOp.from_value(str(self.op)))
        if not 0 <= int(self.cell) <= 80:
            raise DeltaValidationError(f"cell must be in [0, 80], got {self.cell!r}")
        if not 1 <= int(self.digit) <= 9:
            raise DeltaValidationError(f"digit must be in [1, 9], got {self.digit!r}")

    def sort_key(self) -> Tuple[int, int, int]:
        """Return canonical sorting key (op → cell → digit)."""

        return (0 if self.op is DeltaOp.ELIM else 1, int(self.cell), int(self.digit))

    def to_payload(self) -> dict:
        """Convert the delta into a serialisable mapping."""

        return {"op": self.op.value, "cell": int(self.cell), "digit": int(self.digit)}


DeltaLike = Delta | Mapping[str, object]


def ensure_delta(candidate: DeltaLike) -> Delta:
    """Normalise arbitrary delta descriptor to :class:`Delta`."""

    if isinstance(candidate, Delta):
        return candidate
    if isinstance(candidate, Mapping):
        try:
            op = candidate["op"]
            cell = candidate["cell"]
            digit = candidate["digit"]
        except KeyError as exc:  # pragma: no cover - defensive guard
            raise DeltaValidationError("delta mapping is missing required keys") from exc
        return Delta(DeltaOp.from_value(str(op)), int(cell), int(digit))
    raise TypeError(f"Unsupported delta descriptor: {type(candidate)!r}")


def _iter_canonical(deltas: Iterable[DeltaLike]) -> Iterator[Delta]:
    for item in deltas:
        yield ensure_delta(item)


def canonicalise_deltas(deltas: Iterable[DeltaLike]) -> Tuple[Delta, ...]:
    """Return deltas sorted according to the Delta v1 order."""

    canonical = sorted(_iter_canonical(deltas), key=Delta.sort_key)
    return tuple(canonical)


def validate_deltas(deltas: Sequence[DeltaLike]) -> Tuple[Delta, ...]:
    """Validate and canonicalise deltas in one step."""

    return canonicalise_deltas(deltas)


__all__ = [
    "Delta",
    "DeltaLike",
    "DeltaOp",
    "DeltaValidationError",
    "canonicalise_deltas",
    "ensure_delta",
    "validate_deltas",
]
