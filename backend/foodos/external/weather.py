"""Route weather — the hourly temperature series a batch actually travels through.

Contract 3::

    route_weather(origin, destination, depart_at) -> {
        "hourly": [{"h": 0, "temp_c": 28.4, "rh": 74, "solar": 0}, ...],
        "max_temp_c": ..., "mean_temp_c": ..., "source": "snapshot" | "live" | "model",
    }

**Why this is an hourly series and not a single average.** The whole reason the
depart-earlier action exists is that shifting departure by six hours changes
*which hours of the diurnal curve the load is exposed to*, not the average
temperature of the corridor. Hand A a mean and the What-If slider becomes
decorative — every departure shift returns the same number and the judge who
drags it notices immediately.

**Why the snapshot is stored per WAYPOINT and not as one journey.** Weather on
a 2,150 km lane is two-dimensional: where the truck is, and what time it is
there. A single hourly series can only express one departure time. Slice such a
series at a departure twelve hours later and hour 0 silently becomes Agra's
weather instead of Kolar's — the load appears to start its journey at 31 degC
in the plains rather than 23 degC on the Karnataka plateau, and every departure
shift produces a confidently wrong number. So the snapshot holds one absolute
hourly series per waypoint along the lane, and this module reads position
(journey hour / transit) against time (departure + journey hour). That is what
makes the What-If slider move real physics rather than an artefact.

**Air, not pulp.** Every temperature here is shade air temperature at the
roadside. The fruit is hotter: solar gain on the top tier and respiration
self-heating are transport and packaging properties, applied by A using
`transport_modes.yaml::solar_gain_c` and `commodities.yaml::
respiration_heat_w_per_tonne`. Baking a truck's solar gain into a weather
figure would make the temperature wrong for every other mode.

Snapshot first, always. `foodos.external.capture` writes the committed files;
this module only reads them. The deterministic climatology below is the last
resort — a real model with cited normals, not a placeholder, because "no
snapshot for this lane" must still produce a scoreable batch.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta

from foodos.content import ContentError, mandis
from foodos.external import snapshot

# --- climatology anchors ------------------------------------------------------
# IMD 1991-2020 August normals for stations along the Kolar-north lanes: daily max,
# daily min, mean relative humidity, mean daytime cloud fraction. August on this
# corridor is monsoon in the south and centre and drier in the north-west, which is
# exactly why a single corridor average is useless.
_STATIONS: dict[str, dict] = {
    "kolar": {"tmax": 28.5, "tmin": 20.5, "rh": 76, "cloud": 0.70, "lat": 13.14, "lon": 78.13},
    "anantapur": {"tmax": 32.0, "tmin": 23.0, "rh": 64, "cloud": 0.55, "lat": 14.68, "lon": 77.60},
    "hyderabad": {"tmax": 30.5, "tmin": 23.0, "rh": 72, "cloud": 0.66, "lat": 17.38, "lon": 78.48},
    "nagpur": {"tmax": 30.5, "tmin": 24.0, "rh": 78, "cloud": 0.74, "lat": 21.15, "lon": 79.09},
    "gwalior": {"tmax": 34.5, "tmin": 26.5, "rh": 70, "cloud": 0.58, "lat": 26.22, "lon": 78.18},
    "agra": {"tmax": 35.0, "tmin": 27.0, "rh": 71, "cloud": 0.57, "lat": 27.18, "lon": 78.01},
    "delhi": {"tmax": 35.0, "tmin": 27.0, "rh": 73, "cloud": 0.60, "lat": 28.71, "lon": 77.17},
    "jaipur": {"tmax": 34.5, "tmin": 26.0, "rh": 66, "cloud": 0.52, "lat": 26.78, "lon": 75.78},
    "bengaluru": {"tmax": 28.0, "tmin": 20.0, "rh": 78, "cloud": 0.74, "lat": 12.97, "lon": 77.57},
    "chennai": {"tmax": 35.0, "tmin": 26.0, "rh": 70, "cloud": 0.55, "lat": 13.07, "lon": 80.19},
}

# The demo window sits in a MONSOON BREAK — a week or so of suppressed rainfall when the
# north-western plains run several degrees above normal. Not an invented worst case: it is
# the recurring August pattern that produces the tomato arrival gluts and price spikes
# this product exists for, and the honest reason a monsoon month is hot. Applied north of
# Nagpur only; the peninsula stays in the monsoon.
_MONSOON_BREAK_ANOMALY_C = 2.5
_BREAK_APPLIES_FROM_FRAC = 0.55

# Which stations a lane passes, and at what fraction of the journey. Fractions follow the
# lane distances in mandis.yaml. Anything not listed falls back to a two-point
# origin/destination interpolation, stamped degraded so nobody mistakes it for a
# captured corridor.
_LANES: dict[str, list[tuple[float, str]]] = {
    "kolar_hub__delhi_apmc": [
        (0.00, "kolar"),
        (0.14, "anantapur"),
        (0.26, "hyderabad"),
        (0.52, "nagpur"),
        (0.83, "gwalior"),
        (0.93, "agra"),
        (1.00, "delhi"),
    ],
    "kolar_hub__jaipur_apmc": [
        (0.00, "kolar"),
        (0.16, "anantapur"),
        (0.29, "hyderabad"),
        (0.58, "nagpur"),
        (0.88, "gwalior"),
        (1.00, "jaipur"),
    ],
    "kolar_hub__hyderabad_bowenpally": [
        (0.00, "kolar"),
        (0.55, "anantapur"),
        (1.00, "hyderabad"),
    ],
    "kolar_hub__chennai_koyambedu": [(0.00, "kolar"), (1.00, "chennai")],
    "kolar_hub__bengaluru_apmc": [(0.00, "kolar"), (1.00, "bengaluru")],
    "kolar_hub__kolar_apmc": [(0.00, "kolar"), (1.00, "kolar")],
}

_DEFAULT_STATION = {"tmax": 32.0, "tmin": 24.0, "rh": 70, "cloud": 0.60, "lat": 20.0, "lon": 78.0}

# Open-Meteo: free, no API key, hourly forecast. Only ever reached when
# FOODOS_ALLOW_NETWORK is set, which it is not during the demo.
_LIVE_URL = (
    "https://api.open-meteo.com/v1/forecast"
    "?latitude={lat}&longitude={lon}"
    "&hourly=temperature_2m,relative_humidity_2m,shortwave_radiation"
    "&forecast_days=4&timezone=Asia%2FKolkata"
)


def lane_key(origin: str, destination: str) -> str:
    return f"{origin}__{destination}"


def snapshot_name(origin: str, destination: str) -> str:
    return f"weather.{lane_key(origin, destination)}.json"


def waypoints(origin: str, destination: str) -> list[tuple[float, str]]:
    """The stations a lane passes, and where along it.

    An unknown lane degrades to its endpoints rather than raising — a batch
    bound somewhere the content pack has not heard of must still score.
    """
    lane = _LANES.get(lane_key(origin, destination))
    if lane is not None:
        return lane
    return [(0.0, str(origin).split("_")[0]), (1.0, str(destination).split("_")[0])]


def station(name: str) -> dict:
    return _STATIONS.get(name, _DEFAULT_STATION)


def _parse(moment: str | datetime) -> datetime:
    """Accept a datetime or an ISO string, with or without a trailing Z."""
    if isinstance(moment, datetime):
        return moment.replace(tzinfo=None)
    return datetime.fromisoformat(str(moment).strip().replace("Z", ""))


def _transit_hours(origin: str, destination: str) -> float:
    """The lane's transit time, from D's own content.

    Read from mandis.yaml rather than from routes.py so weather has no
    dependency on the route connector — either can be missing and the other
    still answers.
    """
    try:
        row = mandis().get(destination) or {}
    except ContentError:
        row = {}
    return float(row.get("typical_transit_hours") or 12.0)


def _hour_sample(climate: dict, clock_hour: float, frac: float) -> dict:
    """One hour of the diurnal curve at one station.

    Temperature is the standard sinusoid: minimum around 05:00, maximum around
    15:00. A well-behaved approximation, and unlike a flat daily mean it is
    right about the thing that matters — that a load moving between midnight
    and 06:00 sees a different world from one moving at 14:00.
    """
    mean = (climate["tmax"] + climate["tmin"]) / 2.0
    amplitude = (climate["tmax"] - climate["tmin"]) / 2.0
    temp = mean + amplitude * math.cos(2 * math.pi * (clock_hour - 15.0) / 24.0)

    if frac >= _BREAK_APPLIES_FROM_FRAC:
        ramp = (frac - _BREAK_APPLIES_FROM_FRAC) / (1.0 - _BREAK_APPLIES_FROM_FRAC)
        temp += _MONSOON_BREAK_ANOMALY_C * ramp

    # Humidity runs against temperature over the day: highest just before dawn.
    rh = min(max(climate["rh"] + (mean - temp) * 2.4, 28.0), 97.0)

    # Clear-sky shortwave, halved-cosine day arc, damped by cloud. 950 W/m2 is a
    # reasonable clear-sky noon peak at these latitudes in August.
    if 6.0 <= clock_hour <= 18.0:
        solar = 950.0 * math.sin(math.pi * (clock_hour - 6.0) / 12.0) * (
            1.0 - 0.62 * climate["cloud"]
        )
    else:
        solar = 0.0

    return {"temp_c": round(temp, 1), "rh": round(rh), "solar": round(max(solar, 0.0))}


def model_waypoints(
    origin: str, destination: str, start: datetime, hours: int
) -> list[dict]:
    """The deterministic climatology, one absolute hourly series per waypoint.

    This is also what `capture.py` writes when the network is off. Absolute
    timestamps, because a snapshot has to be readable at any departure time or
    the What-If slider cannot move it.
    """
    out: list[dict] = []
    for frac, name in waypoints(origin, destination):
        climate = station(name)
        series = []
        for index in range(hours):
            moment = start + timedelta(hours=index)
            series.append(
                {
                    "t": moment.isoformat(timespec="minutes"),
                    **_hour_sample(climate, moment.hour + moment.minute / 60.0, frac),
                }
            )
        out.append({"frac": frac, "station": name, "hourly": series})
    return out


def _index_by_time(series: list[dict]) -> dict[str, dict]:
    return {str(row["t"]): row for row in series if "t" in row}


def _journey(
    waypoint_rows: list[dict], depart_at: datetime, transit: float
) -> list[dict] | None:
    """Read position against time: the actual hours this load travels through.

    For journey hour `h` the truck is `h / transit` of the way along the lane at
    wall-clock `depart_at + h`. Both axes are honoured; that is the whole point
    of the waypoint layout.
    """
    if not waypoint_rows:
        return None
    indexed = [
        (float(row.get("frac", 0.0)), _index_by_time(row.get("hourly") or []))
        for row in waypoint_rows
    ]
    indexed.sort(key=lambda pair: pair[0])
    if not indexed or not any(times for _, times in indexed):
        return None

    hourly: list[dict] = []
    for hour in range(int(math.ceil(transit)) + 1):
        moment = depart_at + timedelta(hours=hour)
        key = moment.replace(minute=0, second=0, microsecond=0).isoformat(
            timespec="minutes"
        )
        frac = min(hour / max(transit, 1e-6), 1.0)

        lower = indexed[0]
        upper = indexed[-1]
        for entry in indexed:
            if entry[0] >= frac:
                upper = entry
                break
            lower = entry

        low_row, high_row = lower[1].get(key), upper[1].get(key)
        if low_row is None and high_row is None:
            return None  # the window does not cover this hour; caller falls back
        if low_row is None:
            low_row = high_row
        if high_row is None:
            high_row = low_row

        span = upper[0] - lower[0]
        weight = 0.0 if span <= 0 else (frac - lower[0]) / span
        hourly.append(
            {
                "h": hour,
                "temp_c": round(
                    float(low_row["temp_c"])
                    + (float(high_row["temp_c"]) - float(low_row["temp_c"])) * weight,
                    1,
                ),
                "rh": round(
                    float(low_row["rh"])
                    + (float(high_row["rh"]) - float(low_row["rh"])) * weight
                ),
                "solar": round(
                    float(low_row["solar"])
                    + (float(high_row["solar"]) - float(low_row["solar"])) * weight
                ),
            }
        )
    return hourly


def route_weather(origin: str, destination: str, depart_at: str) -> dict:
    """Hourly weather along a lane for a truck leaving at `depart_at`.

    Never raises and never returns an empty series. Order is snapshot, then
    live only if explicitly enabled, then the climatology model — and `source`
    says which one answered.
    """
    departure = _parse(depart_at)
    transit = _transit_hours(origin, destination)

    doc = snapshot.read(snapshot_name(origin, destination))
    if doc is not None:
        hourly = _journey(doc.get("waypoints") or [], departure, transit)
        if hourly:
            return _summarise(
                hourly,
                snapshot.SOURCE_SNAPSHOT,
                origin,
                destination,
                departure,
                transit,
                captured_at=doc.get("captured_at"),
                basis=doc.get("basis"),
            )
        # The snapshot exists but does not cover this departure — a slider dragged
        # past the captured window. Fall through to the model rather than clamp:
        # clamping would silently freeze the weather and make every further shift
        # look like it did nothing.

    fetched = live_waypoints(origin, destination, departure, transit)
    if fetched:
        hourly = _journey(fetched, departure, transit)
        if hourly:
            return _summarise(
                hourly,
                snapshot.SOURCE_LIVE,
                origin,
                destination,
                departure,
                transit,
                basis="open-meteo hourly forecast, per waypoint",
            )

    modelled = model_waypoints(
        origin, destination, departure, int(math.ceil(transit)) + 2
    )
    return _summarise(
        _journey(modelled, departure, transit) or [],
        snapshot.SOURCE_MODEL,
        origin,
        destination,
        departure,
        transit,
        basis="imd_1991_2020_august_normals + monsoon_break_anomaly",
        degraded=True,
    )


def live_waypoints(
    origin: str, destination: str, start: datetime, hours: float
) -> list[dict] | None:
    """One Open-Meteo call per waypoint. Off unless FOODOS_ALLOW_NETWORK is set.

    Used by `capture.py` to build a live-sourced snapshot, and reachable at
    request time for anyone who deliberately turns the network on. All-or-
    nothing: a partial corridor would mix live and modelled hours under one
    `source` stamp, and a provenance label that is only mostly true is worse
    than one that is honestly `model`.
    """
    if not snapshot.network_allowed():
        return None
    out: list[dict] = []
    for frac, name in waypoints(origin, destination):
        anchor = station(name)
        payload = snapshot.live(
            _LIVE_URL.format(lat=anchor["lat"], lon=anchor["lon"])
        )
        hourly = (payload or {}).get("hourly") or {}
        times = hourly.get("time") or []
        temps = hourly.get("temperature_2m") or []
        if not times or len(times) != len(temps):
            return None
        rh = hourly.get("relative_humidity_2m") or [70] * len(times)
        solar = hourly.get("shortwave_radiation") or [0] * len(times)
        out.append(
            {
                "frac": frac,
                "station": name,
                "hourly": [
                    {
                        "t": str(times[i])[:16],
                        "temp_c": temps[i],
                        "rh": rh[i] if rh[i] is not None else 70,
                        "solar": solar[i] if solar[i] is not None else 0,
                    }
                    for i in range(len(times))
                    if temps[i] is not None
                ],
            }
        )
    return out or None


def _summarise(
    hourly: list[dict],
    source: str,
    origin: str,
    destination: str,
    departure: datetime,
    transit: float,
    **extra,
) -> dict:
    temps = [row["temp_c"] for row in hourly] or [0.0]
    return snapshot.stamp(
        {
            "hourly": hourly,
            "max_temp_c": round(max(temps), 1),
            "min_temp_c": round(min(temps), 1),
            "mean_temp_c": round(sum(temps) / len(temps), 1),
            "hours_over_30c": sum(1 for t in temps if t > 30.0),
            "origin": origin,
            "destination": destination,
            "depart_at": departure.isoformat(timespec="minutes"),
            "transit_hours": transit,
        },
        source,
        **extra,
    )
