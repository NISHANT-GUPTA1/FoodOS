"""AGMARKNET / e-NAM wholesale prices.

Moved here from `foodos/ingest/` by B at H2 — this describes the mandi, not our
inventory, which makes it external data rather than an ingest path. D owns it
from that commit onward. Every call site imports `from foodos.external import
agmarknet`; there is no shim, because B updated them all in the same commit.

**A file connector, not a network client.** AGMARKNET publishes daily mandi
arrivals and prices as a downloadable CSV, and that is what this module reads.
Nothing here opens a socket: the demo runs in aeroplane mode, and a live
scheduled pull is the sort of integration that eats a day and adds nothing the
judge can see. Drop `agmarknet.csv` next to the rest of the dataset and it
loads; leave it out and every screen behaves exactly as it did before.

Two surfaces, for the two nodes:

    load() / latest_for()   the kitchen node — CSV into `MarketPrice`, then the
                            most recent quotation for a product, as a reference
                            beside a rescue figure. Unchanged.
    mandi_prices()          the agri node, Contract 3 — destination price
                            context for the Market agent and the optimiser's
                            revenue term. Reads a committed snapshot, needs no
                            database, and is the one the batch screens call.

The published shape, which is what `ALIASES` accepts:

    State, District, Market, Commodity, Variety, Grade,
    Arrival_Date, Min_Price, Max_Price, Modal_Price

**Prices are quoted per quintal.** One quintal is 100 kg, so every figure is
divided by 100 on the way in and the table stores rupees per kilogram. Getting
this wrong inflates every produce price by two orders of magnitude, which is
why the conversion lives here and not at the call site.

What the price is used for, and what it is deliberately not used for: it is
attached to a rescue item as an external reference, so a category manager can
see the mandi rate beside the recovery figure. It does **not** feed
`optimiser.score()`. A wholesale quotation from a market this batch is not in
is context for a human, not a cost term — wiring it into the objective would
change every rupee figure in the demo on the strength of a name match.
"""

from __future__ import annotations

import csv
import re
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from foodos.content import ContentError
from foodos.content import commodity as commodity_constants
from foodos.content import mandis as mandi_content
from foodos.external import snapshot
from foodos.schema.tables import MarketPrice

FILENAME = "agmarknet.csv"

SNAPSHOT_NAME = "mandi_prices.json"

KG_PER_QUINTAL = 100.0

# Published header -> canonical field. Case- and punctuation-insensitive, so
# "Modal_Price", "Modal Price" and "modal price (Rs./Quintal)" all resolve.
ALIASES: dict[str, tuple[str, ...]] = {
    "state": ("state",),
    "district": ("district",),
    "market": ("market", "market name", "mandi"),
    "commodity": ("commodity", "commodity name"),
    "variety": ("variety",),
    "grade": ("grade",),
    "arrival_date": ("arrival date", "price date", "date"),
    "min_price": ("min price", "minimum price", "min price rs quintal"),
    "max_price": ("max price", "maximum price", "max price rs quintal"),
    "modal_price": ("modal price", "modal price rs quintal"),
}

# Our product names -> the AGMARKNET commodity vocabulary. The two differ more
# than you would expect: a kitchen says "Coriander leaves", the mandi says
# "Coriander(Leaves)", and nothing matches on a bare string compare.
COMMODITY_ALIASES: dict[str, str] = {
    "tomato": "Tomato",
    "onion": "Onion",
    "potato": "Potato",
    "cauliflower": "Cauliflower",
    "spinach": "Spinach",
    "coriander": "Coriander(Leaves)",
    "green chilli": "Green Chilli",
    "chilli": "Green Chilli",
    "ginger": "Ginger(Green)",
    "garlic": "Garlic",
    "carrot": "Carrot",
    "capsicum": "Capsicum",
    "cabbage": "Cabbage",
    "brinjal": "Brinjal",
    "okra": "Bhindi(Ladies Finger)",
    "bhindi": "Bhindi(Ladies Finger)",
    "ladies finger": "Bhindi(Ladies Finger)",
    "green peas": "Green Peas",
    "peas": "Green Peas",
    "mint": "Mint(Pudina)",
    "pudina": "Mint(Pudina)",
    "curry leaves": "Curry Leaves",
    "lemon": "Lemon",
    "french beans": "French Beans (Frasbean)",
    "beans": "French Beans (Frasbean)",
    "mushroom": "Mushroom",
    "cucumber": "Cucumbar(Kheera)",
    "banana": "Banana",
}

_NORMALISE = re.compile(r"[^a-z0-9]+")


def _norm(value: str) -> str:
    return _NORMALISE.sub(" ", str(value).strip().lower()).strip()


_LOOKUP: dict[str, str] = {}
for _canonical, _variants in ALIASES.items():
    _LOOKUP[_norm(_canonical)] = _canonical
    for _variant in _variants:
        _LOOKUP.setdefault(_norm(_variant), _canonical)


def _to_float(value) -> float:
    """Published prices carry thousands separators and the odd stray symbol."""
    if value is None:
        return 0.0
    cleaned = re.sub(r"[^0-9.\-]", "", str(value))
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def _to_date(value) -> date | None:
    """AGMARKNET writes dd/mm/yyyy; accept ISO too, since exports vary."""
    raw = ("" if value is None else str(value)).strip()
    if not raw:
        return None
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d %b %Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def commodity_for(product_name: str) -> str | None:
    """Map one of our product names onto an AGMARKNET commodity.

    Longest alias first, so "green peas" is not swallowed by "peas" and
    "curry leaves" is not read as a coriander leaf.
    """
    lowered = _norm(product_name)
    for token in sorted(COMMODITY_ALIASES, key=len, reverse=True):
        if token in lowered:
            return COMMODITY_ALIASES[token]
    return None


def load(session: Session, data_dir: Path) -> dict:
    """Load `agmarknet.csv` if it is there. Absence is not an error."""
    path = data_dir / FILENAME
    if not path.exists():
        return {"loaded": 0, "source": None}

    with path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        headers = reader.fieldnames or []
        mapping = {h: _LOOKUP[_norm(h)] for h in headers if _norm(h) in _LOOKUP}
        unmapped = [h for h in headers if h not in mapping]
        rows = [{mapping[k]: v for k, v in row.items() if k in mapping} for row in reader]

    loaded = 0
    skipped = 0
    for row in rows:
        arrival = _to_date(row.get("arrival_date"))
        commodity = (row.get("commodity") or "").strip()
        if not commodity or arrival is None:
            skipped += 1
            continue
        session.add(
            MarketPrice(
                commodity=commodity,
                variety=(row.get("variety") or "").strip() or None,
                grade=(row.get("grade") or "").strip() or None,
                state=(row.get("state") or "").strip() or None,
                district=(row.get("district") or "").strip() or None,
                market=(row.get("market") or "").strip() or "unknown",
                arrival_date=arrival,
                min_price_per_kg=round(_to_float(row.get("min_price")) / KG_PER_QUINTAL, 4),
                max_price_per_kg=round(_to_float(row.get("max_price")) / KG_PER_QUINTAL, 4),
                modal_price_per_kg=round(
                    _to_float(row.get("modal_price")) / KG_PER_QUINTAL, 4
                ),
            )
        )
        loaded += 1

    session.flush()
    return {
        "loaded": loaded,
        "skipped": skipped,
        "unmapped_columns": unmapped,
        "source": str(path),
    }


def latest_for(session: Session, product_name: str, as_of: date) -> dict | None:
    """Most recent quotation on or before `as_of` for this product's commodity.

    Returns the shape the API hands to C, or `None` when no AGMARKNET data is
    loaded or the product is not a recognised mandi commodity. A missing
    reference is normal — spices, dairy and prepared dishes have none.
    """
    commodity = commodity_for(product_name)
    if commodity is None:
        return None

    row = session.scalars(
        select(MarketPrice)
        .where(MarketPrice.commodity == commodity)
        .where(MarketPrice.arrival_date <= as_of)
        .order_by(MarketPrice.arrival_date.desc(), MarketPrice.id.desc())
        .limit(1)
    ).first()
    if row is None:
        return None

    return {
        "commodity": row.commodity,
        "market": row.market,
        "arrival_date": row.arrival_date.isoformat(),
        "days_stale": (as_of - row.arrival_date).days,
        "modal_price_per_kg": row.modal_price_per_kg,
        "min_price_per_kg": row.min_price_per_kg,
        "max_price_per_kg": row.max_price_per_kg,
        "source": row.source,
    }


# ------------------------------------------------------------- Contract 3 · agri
# Destination price context for the batch product. Deliberately database-free:
# it is called while a batch is being scored, before anything is persisted, and
# from `tests/test_external/` where there is no session at all.


def _mandi_ids(requested: list[str] | None) -> list[str]:
    known = mandi_content()
    if not requested:
        return list(known)
    return [str(m) for m in requested]


def _reference_price(commodity: str) -> float:
    """The fallback rate when no snapshot covers a mandi.

    From `commodities.yaml`, so even the degraded path quotes a number with a
    source rather than a literal invented at the call site.
    """
    try:
        return float(commodity_constants(commodity)["reference_price_per_kg"])
    except (ContentError, KeyError, TypeError, ValueError):
        return 15.0


def mandi_prices(commodity: str, mandis: list[str], on: str) -> dict:
    """Per-kilogram wholesale prices at the given mandis on a date.

    **Per kilogram, never per quintal.** AGMARKNET quotes per quintal and the
    /100 lives in this module and nowhere else — applying it twice at a call
    site is how a demo ends up quoting tomato at 19 paise a kilo, and applying
    it zero times is how it quotes Rs 1,950.

    Returns a row per requested mandi, always. A mandi with no quotation gets
    the commodity's reference price with `estimated: true` and a stale-days
    count, because a missing destination silently vanishing from the comparison
    is worse than a disclosed estimate — the optimiser would then rank a subset
    and present it as the whole field.
    """
    wanted = _mandi_ids(mandis)
    known = mandi_content()
    reference = _reference_price(commodity)

    doc = snapshot.read(SNAPSHOT_NAME)
    source = snapshot.SOURCE_SNAPSHOT if doc else snapshot.SOURCE_MODEL
    quotes = (doc or {}).get("prices") or {}
    captured_on = (doc or {}).get("on")

    prices: dict[str, dict] = {}
    for mandi_id in wanted:
        meta = known.get(mandi_id) or {}
        row = quotes.get(mandi_id) or {}
        modal = row.get("modal_price_per_kg")
        estimated = modal is None
        if estimated:
            modal = reference
        modal = float(modal)
        prices[mandi_id] = {
            "mandi": mandi_id,
            "display_name": meta.get("display_name", mandi_id),
            "agmarknet_key": meta.get("agmarknet_key"),
            "commodity": commodity,
            "modal_price_per_kg": round(modal, 2),
            "min_price_per_kg": round(float(row.get("min_price_per_kg", modal * 0.82)), 2),
            "max_price_per_kg": round(float(row.get("max_price_per_kg", modal * 1.18)), 2),
            "arrival_kg": row.get("arrival_kg"),
            "daily_absorption_kg": meta.get("daily_absorption_kg"),
            "arrival_date": row.get("arrival_date", captured_on),
            "estimated": estimated,
        }

    stale_days = None
    if captured_on:
        try:
            stale_days = (date.fromisoformat(str(on)) - date.fromisoformat(str(captured_on))).days
        except ValueError:
            stale_days = None

    return snapshot.stamp(
        {
            "commodity": commodity,
            "on": str(on),
            "unit": "INR_per_kg",
            "prices": prices,
            "days_stale": stale_days,
            "estimated_count": sum(1 for p in prices.values() if p["estimated"]),
        },
        source,
        captured_on=captured_on,
        basis=(doc or {}).get("basis"),
    )
