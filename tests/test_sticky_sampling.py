from __future__ import annotations

import hashlib
from decimal import Decimal, ROUND_DOWN

from orchestrator import sampling


def _u64(hash_salt: str | None, run_id: str, puzzle_digest: str | None, sticky: bool) -> int:
    material = [hash_salt or ""]
    if not sticky:
        material.append(run_id)
    material.extend(["sudoku", "shadow", puzzle_digest or ""])
    payload = "".join(material).encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big", signed=False)


def test_sticky_sampling_ignores_run_id() -> None:
    salt = "sticky"
    digest = "abc123"
    rate = Decimal("0.5")
    decision_a = sampling.hit(salt, "run-a", digest, rate, sticky=True)
    decision_b = sampling.hit(salt, "run-b", digest, rate, sticky=True)
    assert decision_a == decision_b
    assert _u64(salt, "run-a", digest, True) == _u64(salt, "run-b", digest, True)


def test_non_sticky_depends_on_run_id() -> None:
    salt = "non-sticky"
    digest = "abc123"
    rate = Decimal("0.5")
    run_a_u64 = _u64(salt, "run-a", digest, False)
    run_b_u64 = _u64(salt, "run-b", digest, False)
    assert run_a_u64 != run_b_u64
    scale = Decimal(1 << 64)
    expected_a = run_a_u64 < int((rate * scale).to_integral_value(rounding=ROUND_DOWN))
    expected_b = run_b_u64 < int((rate * scale).to_integral_value(rounding=ROUND_DOWN))
    assert sampling.hit(salt, "run-a", digest, rate, sticky=False) == expected_a
    assert sampling.hit(salt, "run-b", digest, rate, sticky=False) == expected_b
