"""External data connectors — weather, road route, mandi prices. Person D.

**The one rule this package exists to enforce: nothing here needs a socket.**

`docs/FoodOS-Blueprint-Reconciliation.md` ruled out live telemetry and the
blueprint puts hardware on its own out-of-scope list, so every connector in
here is *snapshot-first*: it reads a committed file under
`backend/data/external/`, and only attempts a network call when the caller
explicitly asks for one and the environment allows it. Ruling 3 of
`FoodOS-Team-Split-v2.md` — the aeroplane-mode rehearsal at H34 is the
acceptance test. A connector that only works online is a connector that will
fail on stage.

Every return value carries a `source` field — `"snapshot"`, `"live"` or
`"model"` — and the UI renders it. **`source` is never hidden.** A judge who
spots stale data we disclosed asks a different question from one who spots
stale data we hid.

Contract 3 (D -> A + B), frozen at H3::

    route_weather(origin, destination, depart_at) -> dict
    route_profile(origin, destination, depart_at) -> dict
    mandi_prices(commodity, mandis, on)           -> dict

`agmarknet` was moved here from `foodos.ingest` by B at H2 per §1, and is D's
from that commit onward. Two import surfaces coexist deliberately:

    from foodos.external import agmarknet      # the module — B's kitchen-node
                                               # call sites (seed, screens) use
                                               # agmarknet.load / .latest_for
    from foodos.external import mandi_prices   # the Contract 3 function — the
                                               # agri batch screens use this

Both are re-exported below. Dropping the module export would break
`ingest/seed.py` and `api/routes/screens.py`, which is the sort of breakage
that shows up as a failed reseed twenty minutes before a rehearsal.
"""

from __future__ import annotations

from foodos.external import agmarknet
from foodos.external.agmarknet import mandi_prices
from foodos.external.routes import route_profile
from foodos.external.weather import route_weather

__all__ = [
    "agmarknet",
    "mandi_prices",
    "route_profile",
    "route_weather",
]
