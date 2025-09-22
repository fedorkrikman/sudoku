"""Executor interfaces for orchestrator work distribution."""

from __future__ import annotations

from typing import List, Protocol, Sequence

from .task import Result, WorkUnit


class Executor(Protocol):
    """Abstract execution backend."""

    def submit(self, work_units: Sequence[WorkUnit]) -> List[Result]:
        """Schedule a batch of work units for execution."""

    def barrier(self) -> None:
        """Wait until all enqueued work is finished."""

    def shutdown(self) -> None:
        """Tear down resources allocated by the executor."""


class SequentialExecutor:
    """Deterministic executor processing work units serially."""

    def submit(self, work_units: Sequence[WorkUnit]) -> List[Result]:
        results: List[Result] = []
        for unit in work_units:
            result = Result(work_unit=unit, outputs={}, metrics={}, status="skipped")
            results.append(result)
        return results

    def barrier(self) -> None:
        return None

    def shutdown(self) -> None:
        return None


__all__ = ["Executor", "SequentialExecutor"]
