import re

from orchestrator import orchestrator


HEX64 = re.compile(r"^[0-9a-f]{64}$")


def test_shadow_event_reports_hex_digests() -> None:
    overrides = {
        "PUZZLE_ROOT_SEED": "hex-digests",
        "CLI_SHADOW_ENABLED": "1",
        "CLI_SHADOW_SAMPLE_RATE": "1.0",
    }
    result = orchestrator.run_pipeline(env_overrides=overrides)
    event = result["shadow"]["event"]

    assert HEX64.match(event["puzzle_digest"])
    assert HEX64.match(event["solved_ref_digest"])
    assert HEX64.match(event["solve_trace_sha256"])
    assert HEX64.match(event["state_hash_sha256"])
    assert HEX64.match(event["envelope_jcs_sha256"])
