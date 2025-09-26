from __future__ import annotations

from contracts.jsoncanon import jcs_dump, jcs_sha256


def test_canonical_order_and_numbers():
    payload_a = {"b": 2, "a": 1.0}
    payload_b = {"a": 1, "b": 2}
    assert jcs_dump(payload_a) == jcs_dump(payload_b)
    assert jcs_sha256(payload_a) == jcs_sha256(payload_b)


def test_rejects_nan():
    import math
    import pytest

    with pytest.raises(ValueError):
        jcs_dump({"value": math.nan})
