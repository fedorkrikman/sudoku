"""Envelope utilities shared by shadow orchestration components."""

from __future__ import annotations

import platform
import socket
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict

__all__ = ["Envelope", "make_envelope", "envelope_to_dict"]


@dataclass(frozen=True)
class Envelope:
    ts: str
    run_id: str
    profile: str
    solver_id: str
    commit_sha: str
    baseline_sha: str | None
    hw_fingerprint: str
    seq: int


def _default_hw_fingerprint() -> str:
    cpu = platform.processor() or platform.machine()
    node = socket.gethostname()
    kernel = platform.release()
    payload = f"{cpu}|{node}|{kernel}"
    import hashlib

    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def make_envelope(
    profile: str,
    solver_id: str,
    commit_sha: str,
    baseline_sha: str | None = None,
    *,
    run_id: str | None = None,
    seq: int = 0,
    ts: str | None = None,
    hw_fingerprint: str | None = None,
) -> Envelope:
    """Construct an :class:`Envelope` with deterministic defaults."""

    timestamp = ts or datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    resolved_run_id = run_id or f"run-{uuid.uuid4().hex[:12]}"
    fingerprint = hw_fingerprint or _default_hw_fingerprint()
    return Envelope(
        ts=timestamp,
        run_id=resolved_run_id,
        profile=profile,
        solver_id=solver_id,
        commit_sha=commit_sha,
        baseline_sha=baseline_sha,
        hw_fingerprint=fingerprint,
        seq=seq,
    )


def envelope_to_dict(envelope: Envelope) -> Dict[str, Any]:
    return asdict(envelope)
