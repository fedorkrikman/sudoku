#!/usr/bin/env python3
"""Shadow sampling overhead guardrail computation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List, Sequence

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EVENTS = ROOT / "logs" / "examples" / "shadowlog_v1_sample.json"
REPORT_DEFAULT = ROOT / "reports" / "shadow_overhead" / "report.json"

def _load_events(path: Path) -> List[Dict[str, object]]:
    if not path.exists():
        return []
    raw = path.read_text("utf-8")
    raw = raw.strip()
    if not raw:
        return []
    events: List[Dict[str, object]] = []
    if raw.startswith("["):
        payload = json.loads(raw)
        if isinstance(payload, list):
            events.extend(item for item in payload if isinstance(item, dict))
    elif raw.startswith("{"):
        payload = json.loads(raw)
        if isinstance(payload, dict):
            events.append(payload)
    else:
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                events.append(payload)
    return events



def _compute_metrics(events: Sequence[Dict[str, object]]) -> Dict[str, float]:
    sampled = [event for event in events if bool(event.get("sampled"))]
    if not sampled:
        return {
            "shadow_fraction": 0.0,
            "avg_delta_ms": 0.0,
            "overhead_pct": 0.0,
            "mismatch_rate": 0.0,
        }
    shadow_fraction = sum(float(event.get("sample_rate", 0.0)) for event in sampled) / len(sampled)
    deltas = [float(event.get("perf_delta_ms", 0.0)) for event in sampled if isinstance(event.get("perf_delta_ms"), (int, float))]
    avg_delta = sum(deltas) / len(deltas) if deltas else 0.0
    durations = [float(event.get("time_ms", 0.0)) for event in sampled if isinstance(event.get("time_ms"), (int, float)) and float(event.get("time_ms", 0.0)) > 0]
    baseline = sum(durations) / len(durations) if durations else 1.0
    overhead_pct = 100.0 * shadow_fraction * (avg_delta / baseline)
    mismatches = [event for event in sampled if str(event.get("category", "")).upper() != "OK" or str(event.get("verdict_status", "ok")).lower() != "ok"]
    mismatch_rate = len(mismatches) / len(sampled)
    return {
        "shadow_fraction": shadow_fraction,
        "avg_delta_ms": avg_delta,
        "overhead_pct": overhead_pct,
        "mismatch_rate": mismatch_rate,
    }


def _decide_action(metrics: Dict[str, float]) -> str:
    overhead = metrics.get("overhead_pct", 0.0)
    mismatch_rate = metrics.get("mismatch_rate", 0.0)
    if overhead > 5.0:
        return "halve"
    if mismatch_rate > 0.002:
        return "raise"
    if mismatch_rate < 0.0002:
        return "lower"
    return "none"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default="prod", help="Profile (expected prod)")
    parser.add_argument("--window", type=int, default=10000, help="Sliding window size (events)")
    parser.add_argument("--events", type=Path, default=DEFAULT_EVENTS, help="Path to shadow log events")
    parser.add_argument("--out", type=Path, default=REPORT_DEFAULT, help="Path to JSON report")
    args = parser.parse_args(argv)

    events = _load_events(args.events)
    if args.window and len(events) > args.window:
        events = events[-args.window :]

    metrics = _compute_metrics(events)
    action = _decide_action(metrics)

    report = {
        "profile": args.profile,
        "overhead_pct": round(metrics["overhead_pct"], 3),
        "mismatch_rate": round(metrics["mismatch_rate"], 6),
        "shadow_fraction": round(metrics["shadow_fraction"], 6),
        "avg_delta_ms": round(metrics["avg_delta_ms"], 3),
        "action": action,
        "events_analyzed": len(events),
    }
    report_path = args.out
    report_path.parent.mkdir(parents=True, exist_ok=True)
    canonical = json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    report_path.write_text(canonical + "\n", encoding="utf-8")

    print(
        f"Shadow overhead {action.upper() if action != 'none' else 'OK'}: "
        f"overhead={report['overhead_pct']}% mismatch_rate={report['mismatch_rate']}"  # noqa: E501
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
