"""Shadow sampling guardrail helpers."""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["ShadowTelemetry", "recommend_action"]


@dataclass(frozen=True)
class ShadowTelemetry:
    shadow_fraction: float
    avg_delta_ms: float
    cpu_budget_ms: float
    mismatch_rate: float
    sample_count: int
    window_days: int


def recommend_action(telemetry: ShadowTelemetry) -> str:
    """Return the policy adjustment recommended for the provided telemetry."""

    overhead = telemetry.shadow_fraction * telemetry.avg_delta_ms
    budget_threshold = 0.05 * telemetry.cpu_budget_ms

    if telemetry.window_days >= 3 and overhead > budget_threshold:
        return "halve"
    if telemetry.mismatch_rate > 0.002:
        return "raise_to_0.05@24h"
    if telemetry.sample_count >= 10_000 and telemetry.mismatch_rate < 0.0002:
        return "lower_to_0.005"
    return "keep"
