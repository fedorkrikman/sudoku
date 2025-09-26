"""Light-weight JSONL logger with rotation support."""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

__all__ = ["configure", "append_event", "current_log_path"]

_DEFAULT_MAX_BYTES = 100 * 1024 * 1024
_LOCK = threading.Lock()
_LOG_DIR = Path("logs/shadow")
_MAX_BYTES = _DEFAULT_MAX_BYTES
_CURRENT_PATH: Path | None = None


def configure(base_dir: str | Path, *, max_bytes: int | None = None) -> None:
    """Configure the logger to use ``base_dir`` for all files."""

    global _LOG_DIR, _MAX_BYTES, _CURRENT_PATH
    _LOG_DIR = Path(base_dir)
    _MAX_BYTES = max_bytes or _DEFAULT_MAX_BYTES
    _CURRENT_PATH = None


def _date_prefix() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def _resolve_log_path() -> Path:
    global _CURRENT_PATH
    date_dir = _LOG_DIR / _date_prefix()
    date_dir.mkdir(parents=True, exist_ok=True)

    if _CURRENT_PATH is not None and _CURRENT_PATH.exists():
        if _CURRENT_PATH.stat().st_size < _MAX_BYTES:
            return _CURRENT_PATH

    counter = 0
    while True:
        candidate = date_dir / f"shadow_{counter:02d}.jsonl"
        if not candidate.exists() or candidate.stat().st_size < _MAX_BYTES:
            _CURRENT_PATH = candidate
            return candidate
        counter += 1


def append_event(event: Dict[str, Any]) -> Path:
    """Append ``event`` to the active JSONL file and return the file path."""

    payload = dict(event)
    payload.setdefault("ts", datetime.now(timezone.utc).isoformat(timespec="milliseconds"))

    line = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    with _LOCK:
        path = _resolve_log_path()
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    return path


def current_log_path() -> Path | None:
    return _CURRENT_PATH
