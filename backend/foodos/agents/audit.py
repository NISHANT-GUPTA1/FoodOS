"""Append-only audit log for every agent output, passed or blocked.

"The Verifier blocks bad output" is a claim. This file is the evidence. Every run appends
one JSON line: what the model wrote, what was rendered, which checks ran, which failed,
and whether the output was allowed through.

The demo screenshot at H16-22 is a tail of this file.

Owner: Person D.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_LOCK = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def append(path: Path, record: dict[str, Any]) -> None:
    """Append one record. Never raises into the caller — a broken log must not kill a demo."""
    entry = {"ts": _now(), **record}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(entry, ensure_ascii=False, default=str)
        with _LOCK:
            with path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
    except OSError as exc:  # pragma: no cover - disk dependent
        if os.getenv("FOODOS_DEBUG"):
            print(f"[audit] could not write {path}: {exc}")


def read_all(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def blocked_only(path: Path) -> list[dict[str, Any]]:
    return [r for r in read_all(path) if r.get("blocked")]


def summary(path: Path) -> dict[str, int]:
    records = read_all(path)
    return {
        "total": len(records),
        "passed": sum(1 for r in records if not r.get("blocked")),
        "blocked": sum(1 for r in records if r.get("blocked")),
        "number_violations": sum(1 for r in records if r.get("number_violations")),
    }
