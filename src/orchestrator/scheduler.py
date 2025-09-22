"""Scheduler skeleton for the future multi-executor orchestrator."""

from __future__ import annotations

from typing import List, Sequence

from .executor import Executor, SequentialExecutor
from .task import Result, WorkUnit


class Scheduler:
    """Deterministic task scheduler with sequential policy by default."""

    def __init__(self, executor: Executor | None = None) -> None:
        self.executor = executor or SequentialExecutor()

    def build_task_graph(self, spec_id: str, impl: str) -> List[WorkUnit]:
        """Construct the deterministic task list for the requested solver impl."""

        # The scaffold returns an empty list; concrete implementations will
        # populate propagation/heuristic/branch steps extracted from the legacy
        # solver.  The interface is provided now to unblock orchestrator wiring.
        return []

    def submit(self, work_units: Sequence[WorkUnit]) -> List[Result]:
        """Submit work units to the underlying executor."""

        return self.executor.submit(list(work_units))

    def barrier(self) -> None:
        self.executor.barrier()

    def shutdown(self) -> None:
        self.executor.shutdown()


__all__ = ["Scheduler"]
