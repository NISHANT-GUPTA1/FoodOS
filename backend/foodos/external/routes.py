"""Road route profile — distance, honest transit time, and road roughness.

Contract 3::

    route_profile(origin, destination, depart_at) -> {
        "distance_km": 2150, "transit_hours": 36.5, "road_quality": "mixed",
        "vibration_index": 0.6, "source": "snapshot" | "live" | "model",
    }

**Scope, from §10:** a distance and duration lookup. Not live traffic, not fleet
tracking, not turn-by-turn. Those were ruled out before the clock started and
they do not come back at hour 28.

**Why `depart_at` is an argument.** Transit on this corridor is not a constant.
A truck leaving Kolar at 09:00 spends its first two hours in Bengaluru-bound
traffic; the same truck leaving at 22:00 does not. That difference is roughly
two hours of shelf life, which is the same order as the entire benefit of a
tarpaulin — so a route connector that ignores departure time quietly hides one
of the two levers the demo is about.

**`vibration_index` is the term nobody expects to matter and does.** Mechanical
damage from road roughness compounds with the fruit's existing bruising, and it
is why the engine will sometimes prefer a longer, smoother lane. It multiplies
`transport_modes.yaml::vibration_penalty`; 1.0 means "the roughness the penalty
was quoted for".
"""

from __future__ import annotations

from datetime import datetime

from foodos.content import ContentError, mandis
from foodos.external import snapshot

SNAPSHOT_NAME = "routes.json"

# Road quality by lane, and the vibration index that goes with it. These are the National
# Highway corridors, not district roads: NH-44 Bengaluru-Delhi is four-lane or better for
# almost its whole length, with the rough sections through central India. Ratings follow
# the NHAI corridor condition classes; the index is the multiplier on the per-1,000-km
# vibration penalty in transport_modes.yaml.
_ROAD_QUALITY = {
    "good": 0.45, # four-lane or six-lane divided highway, resurfaced
    "mixed": 0.60, # mostly highway with rough or under-construction stretches
    "poor": 0.95, # single-lane state highway or district road
}

# Per-lane overrides. Everything else falls back to the generic model below.
_LANES: dict[str, dict] = {
    "kolar_hub__delhi_apmc": {
        "road_quality": "mixed",
        "toll_inr": 6850,
        "rest_stops": 3,
        "notes": "NH-44 the whole way. The rough stretch is Nagpur to Jhansi.",
    },
    "kolar_hub__jaipur_apmc": {
        "road_quality": "mixed",
        "toll_inr": 6200,
        "rest_stops": 3,
    },
    "kolar_hub__hyderabad_bowenpally": {
        "road_quality": "good",
        "toll_inr": 1450,
        "rest_stops": 1,
    },
    "kolar_hub__chennai_koyambedu": {
        "road_quality": "good",
        "toll_inr": 640,
        "rest_stops": 0,
    },
    "kolar_hub__bengaluru_apmc": {
        "road_quality": "good",
        "toll_inr": 180,
        "rest_stops": 0,
    },
    "kolar_hub__kolar_apmc": {
        "road_quality": "good",
        "toll_inr": 0,
        "rest_stops": 0,
    },
}

# Departure-hour penalty in hours, applied to the first leg only. Bengaluru's outbound
# congestion on the Kolar road is the morning and evening peaks; a night departure clears
# it entirely. Values are the difference between peak and free-flow running time on the
# first 120 km, which is where the whole effect lives.
_DEPARTURE_PENALTY_HOURS = {
    range(0, 5): -0.4, # empty roads; slightly faster than the schedule
    range(5, 8): 0.0,
    range(8, 12): 1.8, # morning peak out of the Bengaluru catchment
    range(12, 17): 0.6,
    range(17, 21): 2.1, # evening peak, the worst departure window on this lane
    range(21, 24): -0.3,
}

_DEFAULT_DISTANCE_KM = 500.0
_DEFAULT_TRANSIT_HOURS = 12.0


def lane_key(origin: str, destination: str) -> str:
    return f"{origin}__{destination}"


def _departure_penalty(hour: int) -> float:
    for window, penalty in _DEPARTURE_PENALTY_HOURS.items():
        if hour in window:
            return penalty
    return 0.0


def _parse(moment: str | datetime) -> datetime:
    if isinstance(moment, datetime):
        return moment.replace(tzinfo=None)
    return datetime.fromisoformat(str(moment).strip().replace("Z", ""))


def _from_content(origin: str, destination: str) -> dict | None:
    """Distance and schedule transit from mandis.yaml — D's own numbers."""
    try:
        row = mandis().get(destination)
    except ContentError:
        return None
    if not row:
        return None
    return {
        "distance_km": float(row.get("distance_km", _DEFAULT_DISTANCE_KM)),
        "transit_hours": float(
            row.get("typical_transit_hours", _DEFAULT_TRANSIT_HOURS)
        ),
    }


def route_profile(origin: str, destination: str, depart_at: str) -> dict:
    """Distance, departure-adjusted transit, road quality and vibration index.

    Never raises. An unknown destination degrades to a stated default and is
    stamped `degraded: true` rather than throwing — a batch bound somewhere the
    content pack has not heard of should still score, and should say so.
    """
    departure = _parse(depart_at)
    key = lane_key(origin, destination)
    lane = _LANES.get(key, {})

    base = None
    source = snapshot.SOURCE_MODEL
    degraded = False

    doc = snapshot.read(SNAPSHOT_NAME)
    if doc is not None:
        row = (doc.get("lanes") or {}).get(key)
        if row and row.get("distance_km") and row.get("transit_hours"):
            base = {
                "distance_km": float(row["distance_km"]),
                "transit_hours": float(row["transit_hours"]),
            }
            lane = {**lane, **{k: v for k, v in row.items() if k not in base}}
            source = snapshot.SOURCE_SNAPSHOT

    if base is None:
        base = _from_content(origin, destination)
        if base is None:
            base = {
                "distance_km": _DEFAULT_DISTANCE_KM,
                "transit_hours": _DEFAULT_TRANSIT_HOURS,
            }
            degraded = True

    quality = str(lane.get("road_quality", "mixed"))
    vibration = _ROAD_QUALITY.get(quality, _ROAD_QUALITY["mixed"])

    penalty = _departure_penalty(departure.hour)
    transit = max(base["transit_hours"] + penalty, 0.25)

    return snapshot.stamp(
        {
            "origin": origin,
            "destination": destination,
            "depart_at": departure.isoformat(timespec="minutes"),
            "distance_km": round(base["distance_km"], 1),
            "transit_hours": round(transit, 1),
            "scheduled_transit_hours": round(base["transit_hours"], 1),
            "departure_penalty_hours": round(penalty, 1),
            "road_quality": quality,
            "vibration_index": vibration,
            "toll_inr": lane.get("toll_inr"),
            "rest_stops": lane.get("rest_stops"),
            "notes": lane.get("notes"),
        },
        source,
        degraded=degraded or None,
    )
