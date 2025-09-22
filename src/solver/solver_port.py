"""SolverPort facade orchestrating legacy and Nova implementations."""

from __future__ import annotations

from typing import Literal, Optional, Tuple


def run(
    spec_artifact_id: str,
    impl: Literal["legacy", "nova", "shadow"],
    *,
    shadow_sample_rate: float = 0.0,
) -> Tuple[str, Optional[str]]:
    """Execute the configured solver implementation.

    Parameters
    ----------
    spec_artifact_id:
        Identifier of the validated Spec artifact residing in the artifact
        store.
    impl:
        Selector for the active solver implementation.  ``"legacy"`` represents
        the current solver, ``"nova"`` activates the re-architecture and
        ``"shadow"`` allows dual execution for verification scenarios.
    shadow_sample_rate:
        Fraction of runs that should execute the shadow solver path.  Only
        meaningful when ``impl == "shadow"``.

    Returns
    -------
    Tuple[str, Optional[str]]
        Identifiers of the produced CompleteGrid artifact and optional
        SolveTrace artifact.

    Notes
    -----
    The facade is intentionally left unimplemented for the scaffold.  Concrete
    logic will be introduced once Nova steps are available and the Validation
    Center wiring is finalised.
    """

    raise NotImplementedError("SolverPort.run is pending integration with solver implementations.")


__all__ = ["run"]
