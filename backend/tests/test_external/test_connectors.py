"""Contract 3 connectors, with the network unplugged.

Every test in this module runs under the `no_network` fixture, which poisons
`urllib.request.urlopen`. If any assertion here passes only because a socket
opened, the test fails instead.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from foodos.external import mandi_prices, route_profile, route_weather
from foodos.external import snapshot, weather

ORIGIN = "kolar_hub"
DEMO_DEPART = "2026-08-10T08:00:00"
LANES = ["delhi_apmc", "jaipur_apmc", "hyderabad_bowenpally", "bengaluru_apmc"]

VALID_SOURCES = {snapshot.SOURCE_SNAPSHOT, snapshot.SOURCE_LIVE, snapshot.SOURCE_MODEL}


# ------------------------------------------------------------------- weather
@pytest.mark.parametrize("destination", LANES)
def test_weather_answers_offline_for_every_demo_lane(destination):
    out = route_weather(ORIGIN, destination, DEMO_DEPART)

    assert out["source"] == snapshot.SOURCE_SNAPSHOT, (
        f"{destination} has no committed snapshot — run "
        "`python -m foodos.external.capture` and commit the result"
    )
    assert out["hourly"], "an empty hourly series scores nothing"
    assert out["hourly"][0]["h"] == 0
    assert [row["h"] for row in out["hourly"]] == list(range(len(out["hourly"])))
    assert out["min_temp_c"] <= out["mean_temp_c"] <= out["max_temp_c"]
    for row in out["hourly"]:
        assert 0.0 <= row["temp_c"] <= 55.0
        assert 0 <= row["rh"] <= 100
        assert 0 <= row["solar"] <= 1400


def test_weather_hour_zero_is_the_ORIGIN_not_the_destination():
    """Regression: the snapshot must be positional, not a single journey.

    A per-journey series sliced at a later departure hands back the weather at
    whatever point the truck had reached by then — hour 0 of a +32 h departure
    became Agra rather than Kolar, so the load appeared to start its journey in
    the plains at 31 degC instead of on the Karnataka plateau at 23 degC. Every
    departure shift was then confidently wrong. The snapshot stores one series
    per waypoint for exactly this reason.
    """
    kolar_august_dawn_max = 26.0  # IMD normal max at Kolar is 28.5; 08:00 is well under
    for shift_hours in (0, 12, 24, 36):
        departure = datetime(2026, 8, 10, 8, 0) + timedelta(hours=shift_hours)
        out = route_weather(ORIGIN, "delhi_apmc", departure.isoformat())
        assert out["hourly"][0]["temp_c"] < kolar_august_dawn_max, (
            f"hour 0 of a +{shift_hours} h departure is {out['hourly'][0]['temp_c']} degC "
            "— that is not Kolar at 08:00, the series is being read as a single journey"
        )


def test_departure_shift_actually_moves_the_weather():
    """The What-If slider's whole premise.

    If shifting departure does not change the hours the load travels through,
    Screen 4 is decorative and the judge dragging it sees the same number twice.
    """
    base = datetime(2026, 8, 10, 8, 0)
    means = {}
    for shift in (-12, -6, 0, 6):
        out = route_weather(ORIGIN, "delhi_apmc", (base + timedelta(hours=shift)).isoformat())
        assert out["source"] == snapshot.SOURCE_SNAPSHOT, (
            f"a {shift:+d} h shift fell outside the captured window — widen it in "
            "capture.py, the slider must not change provenance mid-drag"
        )
        means[shift] = out["mean_temp_c"]

    assert len(set(means.values())) > 1, "departure shift changed nothing"
    # Leaving earlier puts more of the journey in the dark. This is the direction
    # the demo's headline recommendation depends on being true.
    assert means[-6] < means[0], f"departing 6 h earlier got hotter: {means}"


def test_weather_degrades_to_the_model_for_an_uncaptured_lane():
    out = route_weather(ORIGIN, "surat_apmc", DEMO_DEPART)
    assert out["source"] == snapshot.SOURCE_MODEL
    assert out["degraded"] is True
    assert out["hourly"], "a lane with no snapshot must still produce a scoreable series"


def test_weather_falls_back_rather_than_clamping_outside_the_window():
    """A departure past the captured window must not silently freeze the series."""
    far = (datetime(2026, 8, 9, 0, 0) + timedelta(days=30)).isoformat()
    out = route_weather(ORIGIN, "delhi_apmc", far)
    assert out["source"] == snapshot.SOURCE_MODEL
    assert out["hourly"]


def test_weather_reports_air_temperature_not_a_truck_specific_figure():
    """Solar gain belongs to the transport mode, not to the corridor.

    August shade air on this lane peaks in the thirties. A series in the forties
    would mean somebody folded an open truck's top-tier solar gain into the
    weather, which makes the number wrong for a reefer and double-counted for A.
    """
    out = route_weather(ORIGIN, "delhi_apmc", DEMO_DEPART)
    assert out["max_temp_c"] < 40.0, "this looks like pulp temperature, not shade air"


# -------------------------------------------------------------------- routes
@pytest.mark.parametrize("destination", LANES)
def test_route_profile_answers_offline(destination):
    out = route_profile(ORIGIN, destination, DEMO_DEPART)
    assert out["source"] in VALID_SOURCES
    assert out["distance_km"] > 0
    assert out["transit_hours"] > 0
    assert out["road_quality"] in {"good", "mixed", "poor"}
    assert 0.0 < out["vibration_index"] <= 1.0


def test_route_transit_is_not_distance_over_a_constant():
    """Transit must be schedule time, not a naive average speed.

    2,150 km at 36.5 h is 59 km/h door to door, which is what a commercial FTL
    run on NH-44 actually achieves once rest and mandi queuing are counted. If
    this ever reads like 80 km/h, somebody has replaced a schedule with a
    division and every RUL figure downstream became optimistic.
    """
    out = route_profile(ORIGIN, "delhi_apmc", DEMO_DEPART)
    average_kmh = out["distance_km"] / out["transit_hours"]
    assert 40.0 < average_kmh < 70.0, f"{average_kmh:.0f} km/h is not a real lorry"


def test_departure_hour_changes_transit():
    """Leaving into the Bengaluru evening peak costs real hours."""
    quiet = route_profile(ORIGIN, "delhi_apmc", "2026-08-10T22:00:00")
    peak = route_profile(ORIGIN, "delhi_apmc", "2026-08-10T18:00:00")
    assert peak["transit_hours"] > quiet["transit_hours"]


def test_route_degrades_for_an_unknown_destination():
    out = route_profile(ORIGIN, "surat_apmc", DEMO_DEPART)
    assert out["degraded"] is True
    assert out["distance_km"] > 0


# --------------------------------------------------------------------- mandi
def test_mandi_prices_are_per_kilogram_not_per_quintal():
    """The /100 lives in the loader and must be applied exactly once.

    Applied twice, tomato is quoted at 19 paise a kilo; applied not at all, it is
    Rs 1,950. Both have happened to somebody's demo. This is the guard.
    """
    out = mandi_prices("tomato", ["delhi_apmc", "jaipur_apmc", "kolar_apmc"], "2026-08-10")
    assert out["unit"] == "INR_per_kg"
    for row in out["prices"].values():
        assert 2.0 < row["modal_price_per_kg"] < 200.0, row
        assert row["min_price_per_kg"] <= row["modal_price_per_kg"] <= row["max_price_per_kg"]


def test_mandi_prices_answer_offline_and_stamp_their_source():
    out = mandi_prices("tomato", ["delhi_apmc"], "2026-08-10")
    assert out["source"] == snapshot.SOURCE_SNAPSHOT
    assert out["estimated_count"] == 0
    assert out["prices"]["delhi_apmc"]["estimated"] is False


def test_every_requested_mandi_comes_back_even_without_a_quotation():
    """A destination that silently vanishes turns a comparison into a subset.

    The optimiser would then rank four options and present them as the whole
    field. A disclosed estimate is the lesser evil, and it is disclosed.
    """
    out = mandi_prices("tomato", ["delhi_apmc", "surat_apmc"], "2026-08-10")
    assert set(out["prices"]) == {"delhi_apmc", "surat_apmc"}
    assert out["prices"]["surat_apmc"]["estimated"] is True
    assert out["estimated_count"] == 1


def test_mandi_prices_default_to_every_known_destination():
    out = mandi_prices("tomato", [], "2026-08-10")
    assert "delhi_apmc" in out["prices"]
    assert "kolar_apmc" in out["prices"]


def test_delhi_carries_a_premium_over_the_origin_market():
    """The commercial premise of the whole demo, asserted rather than assumed."""
    out = mandi_prices("tomato", ["delhi_apmc", "kolar_apmc"], "2026-08-10")
    spread = (
        out["prices"]["delhi_apmc"]["modal_price_per_kg"]
        - out["prices"]["kolar_apmc"]["modal_price_per_kg"]
    )
    assert spread > 3.0, f"only Rs {spread:.2f}/kg of headroom — hauling north stops paying"


# ---------------------------------------------------------------- provenance
@pytest.mark.parametrize(
    "call",
    [
        lambda: route_weather(ORIGIN, "delhi_apmc", DEMO_DEPART),
        lambda: route_profile(ORIGIN, "delhi_apmc", DEMO_DEPART),
        lambda: mandi_prices("tomato", ["delhi_apmc"], "2026-08-10"),
    ],
    ids=["weather", "routes", "mandi"],
)
def test_source_is_always_stamped(call):
    """`source` is never hidden. The UI renders it; it has to be there to render."""
    assert call()["source"] in VALID_SOURCES


def test_network_is_opt_in_not_opt_out():
    assert snapshot.network_allowed() is False
    assert snapshot.live("https://example.invalid/whatever") is None


def test_a_corrupt_snapshot_degrades_instead_of_raising(tmp_path, monkeypatch):
    """A half-written JSON file at 3 a.m. must cost provenance, not the demo."""
    monkeypatch.setattr(snapshot, "SNAPSHOT_DIR", tmp_path)
    (tmp_path / weather.snapshot_name(ORIGIN, "delhi_apmc")).write_text(
        "{ this is not json", encoding="utf-8"
    )
    out = route_weather(ORIGIN, "delhi_apmc", DEMO_DEPART)
    assert out["source"] == snapshot.SOURCE_MODEL
    assert out["hourly"]


def test_no_snapshots_at_all_still_scores(tmp_path, monkeypatch):
    """A fresh clone before `capture.py` has ever run is still a working backend."""
    monkeypatch.setattr(snapshot, "SNAPSHOT_DIR", tmp_path)
    assert route_weather(ORIGIN, "delhi_apmc", DEMO_DEPART)["hourly"]
    assert route_profile(ORIGIN, "delhi_apmc", DEMO_DEPART)["distance_km"] > 0
    assert mandi_prices("tomato", ["delhi_apmc"], "2026-08-10")["prices"]
