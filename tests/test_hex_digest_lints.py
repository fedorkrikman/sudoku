from __future__ import annotations

import re

from orchestrator import orchestrator


_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def test_shadow_event_hex_digests() -> None:
    overrides = {
        "PUZZLE_ROOT_SEED": "hex-digest-seed",
        "CLI_SHADOW_ENABLED": "1",
        "CLI_SHADOW_SAMPLE_RATE": "1.0",
    }
    result = orchestrator.run_pipeline(env_overrides=overrides)
    event = result["shadow"]["event"]

    for field in ("puzzle_digest", "solve_trace_sha256", "state_hash_sha256", "envelope_jcs_sha256"):
        value = event[field]
        assert isinstance(value, str)
        assert _HEX64.fullmatch(value), f"Field {field} is not a lowercase sha256 hex digest"
