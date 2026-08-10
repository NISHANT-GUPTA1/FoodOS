"""Compatibility shim — the module moved to `foodos.external.agmarknet`.

AGMARKNET describes the mandi, not our inventory, so it belongs with the other
external connectors rather than in the ingest path. The move is the one-time
relocation in §1 of the team split; this file stays behind so that B's
`ingest/seed.py`, `api/routes/screens.py` and `tests/test_engine/` keep
importing `foodos.ingest.agmarknet` and keep passing byte for byte.

Import the new path in new code. Nothing is deprecated loudly — a warning here
would fire on every seed run and teach the team to ignore warnings.
"""

from __future__ import annotations

from foodos.external.agmarknet import (  # noqa: F401
    ALIASES,
    COMMODITY_ALIASES,
    FILENAME,
    KG_PER_QUINTAL,
    commodity_for,
    latest_for,
    load,
    mandi_prices,
)

__all__ = [
    "ALIASES",
    "COMMODITY_ALIASES",
    "FILENAME",
    "KG_PER_QUINTAL",
    "commodity_for",
    "latest_for",
    "load",
    "mandi_prices",
]
