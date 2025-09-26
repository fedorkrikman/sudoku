#!/usr/bin/env python3
"""Regenerate the acceptance corpus seeds deterministically."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "data" / "acceptance" / "acceptance_corpus_9x9_v1.json"
HASH_SALT = "acceptance_corpus_9x9_v1"


def _generate(count: int) -> Sequence[str]:
    seeds = []
    for index in range(count):
        material = f"{HASH_SALT}i={index}".encode("utf-8")
        digest = hashlib.sha256(material).digest()
        seeds.append(digest[:8].hex())
    return seeds


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=1000, help="Number of seeds to generate")
    parser.add_argument("--out", type=Path, default=TARGET, help="Target JSON file")
    args = parser.parse_args(argv)

    seeds = _generate(args.count)
    payload = {
        "name": HASH_SALT,
        "hash_salt": HASH_SALT,
        "count": len(seeds),
        "balance": "4:4:2",
        "immutable": True,
        "seeds": list(seeds),
    }
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text + "\n", encoding="utf-8")
    print(f"Wrote {len(seeds)} seeds to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
