"""External data connectors — Person D.

Weather, route and mandi price data. Everything in this package is a
**snapshot-first connector**: it reads a cached file from `backend/data/external/`
and only attempts a network call when explicitly asked. Ruling 3 of
FoodOS-Team-Split-v2.md — nothing opens a socket during the demo, and the
aeroplane-mode rehearsal at H34 has to pass.

Every connector stamps `source` as `"snapshot"` or `"live"` on what it returns,
and that field is never hidden from the UI.

`agmarknet` was moved here from `foodos.ingest` by B at H2 per §1. It is D's
from that commit onward. The re-export below is the import surface the rest of
the backend uses:

    from foodos.external import agmarknet

Contract 3 (§2) adds `weather.route_weather()` and `routes.route_profile()`
alongside it. They are D's to write; this file imports agmarknet only, so the
package stays importable before those modules land.
"""

from foodos.external import agmarknet

__all__ = ["agmarknet"]
