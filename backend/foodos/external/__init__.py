"""External data connectors — weather, road route, mandi prices.

**The one rule this package exists to enforce: nothing here needs a socket.**

`docs/FoodOS-Blueprint-Reconciliation.md` ruled out live telemetry and the
blueprint puts hardware on its own out-of-scope list, so every connector in
here is *snapshot-first*: it reads a committed file under
`backend/data/external/`, and only attempts a network call when the caller
explicitly asks for one and the environment allows it. The aeroplane-mode
rehearsal at H34 is the acceptance test. A connector that only works online is
a connector that will fail on stage.

Every return value carries a `source` field — `"snapshot"` or `"live"` — and
the UI renders it. **`source` is never hidden.** A judge who spots stale data
we disclosed asks a different question from one who spots stale data we hid.

Contract 3 (D -> A + B), frozen at H3::

    route_weather(origin, destination, depart_at) -> dict
    route_profile(origin, destination, depart_at) -> dict
    mandi_prices(commodity, mandis, on)           -> dict

`agmarknet.py` moved here from `foodos/ingest/` — it describes the mandi, not
our inventory, which makes it external data rather than an ingest path.
`foodos.ingest.agmarknet` still resolves, so B's seed and API keep importing
the old path unchanged.
"""

from __future__ import annotations

from foodos.external.agmarknet import mandi_prices
from foodos.external.routes import route_profile
from foodos.external.weather import route_weather

__all__ = ["mandi_prices", "route_profile", "route_weather"]
