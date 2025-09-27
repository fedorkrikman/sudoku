from decimal import Decimal
import hashlib

from orchestrator import orchestrator, sampling


def _u64(hash_salt: str | None, run_id: str, puzzle_digest: str | None, sticky: bool) -> int:
    material = (hash_salt or "")
    if not sticky:
        material += run_id
    material += "sudoku" + "shadow" + (puzzle_digest or "")
    digest = hashlib.sha256(material.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big", signed=False)


def test_sampling_sticky_ignores_run_identifier() -> None:
    salt = "sticky-salt"
    digest = "a" * 64
    run_one = sampling.hit(salt, "run-A", digest, Decimal("0.75"), sticky=True)
    run_two = sampling.hit(salt, "run-B", digest, Decimal("0.75"), sticky=True)
    assert run_one == run_two
    assert _u64(salt, "run-A", digest, True) == _u64(salt, "run-B", digest, True)


def test_sampling_non_sticky_includes_run_identifier() -> None:
    salt = "sticky-salt"
    digest = "b" * 64
    assert _u64(salt, "run-A", digest, False) != _u64(salt, "run-B", digest, False)


def test_shadow_policy_reports_sticky_override() -> None:
    overrides = {
        "PUZZLE_ROOT_SEED": "sticky-policy",
        "CLI_SHADOW_ENABLED": "1",
        "CLI_SHADOW_SAMPLE_RATE": "1.0",
        "CLI_SHADOW_STICKY": "1",
    }
    result = orchestrator.run_pipeline(env_overrides=overrides)
    policy = result["modules"]["solver"]["shadow_policy"]
    assert policy["sticky"] is True
