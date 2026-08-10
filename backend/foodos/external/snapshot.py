"""Snapshot-first plumbing shared by all three connectors.

**Ruling 3: nothing opens a socket during the demo.** That is not a preference,
it is the acceptance criterion for the H34 aeroplane-mode rehearsal. So the
order of operations for every connector in this package is:

    1. committed snapshot under backend/data/external/   <- the demo path
    2. a live call, ONLY if the caller asked and the environment allows
    3. a documented deterministic model                   <- last resort, still valid

and the result is stamped with which one it was. **`source` is never hidden.**
A judge who sees data we disclosed as a snapshot asks a different question from
one who catches stale data we presented as live.

Network is opt-in, not opt-out. `FOODOS_ALLOW_NETWORK=1` turns it on; without
it `live()` returns `None` without resolving a hostname, so a machine with a
captive-portal wifi cannot hang a request for thirty seconds while a judge
watches a spinner. That failure mode is the reason this module exists.

Only stdlib `urllib` is used. `requests` is the nicer client, but adding a
dependency is B's call under §1 and the whole live path is a convenience — it
would be absurd to change `pyproject.toml` for a code path the demo never runs.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from foodos.config import DATA_DIR

SNAPSHOT_DIR: Path = DATA_DIR / "external"

SOURCE_SNAPSHOT = "snapshot"
SOURCE_LIVE = "live"
SOURCE_MODEL = "model"

# Short on purpose. A connector that blocks for ten seconds has already failed;
# falling back to the snapshot in two is strictly better than being right in ten.
TIMEOUT_SECONDS = 2.5


def network_allowed() -> bool:
    """Opt-in. Absent or falsey means no socket is opened, ever."""
    return os.environ.get("FOODOS_ALLOW_NETWORK", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def read(name: str) -> dict | None:
    """Read a committed snapshot. Returns `None` if it is absent or corrupt.

    Corrupt is treated exactly like absent: the caller has a model fallback and
    a half-written JSON file at 3 a.m. should degrade the demo, not end it.
    """
    path = SNAPSHOT_DIR / name
    if not path.exists():
        return None
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return doc if isinstance(doc, dict) else None


def write(name: str, payload: dict) -> Path:
    """Write a snapshot. Used by `foodos.external.capture`, never at request time."""
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    path = SNAPSHOT_DIR / name
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=False, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


def live(url: str, *, timeout: float = TIMEOUT_SECONDS) -> Any | None:
    """GET JSON, or `None`.

    Never raises. Every failure mode — network off, DNS, timeout, a 500, a body
    that is not JSON — collapses to `None` so the caller's fallback runs. A
    connector that can raise is a connector that can end a demo.
    """
    if not network_allowed():
        return None
    request = urllib.request.Request(url, headers={"User-Agent": "FoodOS/0.1"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
        return None


def stamp(payload: dict, source: str, **extra: Any) -> dict:
    """Attach the provenance fields every connector return carries.

    `source` is the one the UI renders. `basis` and `captured_at` are for the
    person who has to explain a figure afterwards, which on this team is D.
    """
    out = dict(payload)
    out["source"] = source
    for key, value in extra.items():
        if value is not None:
            out.setdefault(key, value)
    return out
