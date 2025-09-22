"""State capsule definition for the Nova solver pipeline."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Iterable, Mapping, Sequence


@dataclass(frozen=True)
class StateCapsule:
    """Immutable snapshot of the solver state.

    The capsule is intentionally minimal for the initial scaffold.  Real
    implementations are expected to populate ``grid`` and ``candidates`` with
    dedicated value objects.  ``history`` keeps an ordered collection of
    previously applied deltas and metadata, while ``rng_seed`` allows deriving
    deterministic pseudo-random choices without relying on global RNG state.
    """

    grid: Any
    candidates: Any
    history: Sequence[Mapping[str, Any]]
    rng_seed: int

    def evolve(
        self,
        *,
        grid: Any | None = None,
        candidates: Any | None = None,
        history: Iterable[Mapping[str, Any]] | None = None,
        rng_seed: int | None = None,
    ) -> "StateCapsule":
        """Create a new capsule with updated components.

        The method keeps the dataclass frozen while still allowing callers to
        describe state transitions in a controlled fashion.  ``history`` is
        normalised to a tuple to preserve immutability guarantees.
        """

        return replace(
            self,
            grid=self.grid if grid is None else grid,
            candidates=self.candidates if candidates is None else candidates,
            history=tuple(self.history if history is None else history),
            rng_seed=self.rng_seed if rng_seed is None else rng_seed,
        )


__all__ = ["StateCapsule"]
