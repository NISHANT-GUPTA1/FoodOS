"""Contract 1 · `fuse()` — the single feature-vector builder.

FoodOS-Team-Split-v2.md §2. Everything downstream builds its inputs through
this one function, so there is exactly one place where a missing layer is
given a default and exactly one place to look when a number is wrong.

This is an adapter, not a model. It assembles the five ingestion layers into
the `base` dict `foodos.agri` already consumes — no physics, no training, no
second feature space.

**A batch with no photos and no weather must still score** (§3, H8-12). Every
layer is optional; each one that is missing falls back to the commodity
default and is named in `_missing` so a caller can say which parts of the
picture it had.
"""

from __future__ import annotations

from typing import Any

#: Defaults for a mid-season Karnataka shipment. Deliberately unremarkable —
#: a missing layer should degrade a prediction, not caricature it.
DEFAULTS: dict[str, Any] = {
    "quantity_kg": 10_000.0,
    "harvest_method": "manual",
    "harvest_window": "early_morning",
    "field_holding": "shade",
    "field_hours": 4.0,
    "packaging": "ventilated_plastic_crate",
    "transport_mode": "open_truck",
    "transit_hours": 24.0,
    "mandi_holding_hours": 6.0,
    "maturity_factor": 1.0,
    "visual_damage_fraction": 0.03,
    "ambient_mean_c": 29.0,
    "diurnal_amplitude_c": 9.0,
    "road_roughness": 1.4,
}

#: The questionnaire answers D writes, keyed by `feature_key`, mapped onto the
#: scenario field each one feeds. Anything not listed passes through by name.
_HUMAN_KEYS = {
    "harvest_window": "harvest_window",
    "harvest_method": "harvest_method",
    "post_harvest_shade": "field_holding",
    "field_heat_hours_over_30c": "field_hours",
    "field_heat_hours": "field_hours",
    "packaging_type": "packaging",
    "transport_mode": "transport_mode",
    "yard_hold_hours": "mandi_holding_hours",
}

#: Ripening stage to the multiplier the kinetics read. Riper fruit has less
#: life budget left at dispatch, which is what the factor scales.
_MATURITY_FACTOR = {
    "mature_green": 0.80,
    "breaker": 0.90,
    "turning": 1.00,
    "pink": 1.10,
    "light_red": 1.20,
    "red": 1.35,
}

#: Free-text damage bands to a fraction, for when no photos were supplied.
_DAMAGE_FRACTION = {"none": 0.01, "light": 0.03, "moderate": 0.08, "heavy": 0.16}


def fuse(
    human: dict | None = None,
    vision: dict | None = None,
    weather: dict | None = None,
    route: dict | None = None,
    commodity: dict | None = None,
) -> dict:
    """Build one feature vector from the five layers.

    `human`     D's questionnaire answers, keyed by feature_key
    `vision`    `cv.inference.extract_photo_features()` output
    `weather`   `external.weather.route_weather()` output
    `route`     `external.routes.route_profile()` output
    `commodity` `content.commodity()` row

    Returns the `base` dict `foodos.agri` consumes, plus a `_missing` list
    naming the layers that were absent. `_missing` is metadata, not a feature —
    callers strip it before handing the dict to the simulator.
    """
    human, vision = human or {}, vision or {}
    weather, route, commodity = weather or {}, route or {}, commodity or {}

    out = dict(DEFAULTS)
    missing = [
        name
        for name, layer in (
            ("human", human), ("vision", vision),
            ("weather", weather), ("route", route),
        )
        if not layer
    ]

    if commodity.get("base_shelf_life_hours"):
        out["_commodity_shelf_life_hours"] = float(commodity["base_shelf_life_hours"])

    # --- human -------------------------------------------------------------
    for key, value in human.items():
        if value in (None, ""):
            continue
        target = _HUMAN_KEYS.get(key, key)
        if target in DEFAULTS:
            out[target] = _coerce(target, value)

    if "maturity_stage" in human:
        out["maturity_factor"] = _MATURITY_FACTOR.get(str(human["maturity_stage"]), 1.0)
    if "damage_level" in human:
        out["visual_damage_fraction"] = _DAMAGE_FRACTION.get(
            str(human["damage_level"]), DEFAULTS["visual_damage_fraction"]
        )

    # --- vision ------------------------------------------------------------
    # Photos are probabilistic evidence, never a verdict (§3, H12-16). They
    # refine what the farmer said; they do not overrule the batch's identity.
    if vision.get("damage_share") is not None:
        out["visual_damage_fraction"] = float(vision["damage_share"])
    if vision.get("maturity_index") is not None:
        # 0-1 index onto the same multiplier range the stages use.
        out["maturity_factor"] = 0.80 + float(vision["maturity_index"]) * 0.55

    # --- weather -----------------------------------------------------------
    if weather.get("mean_temp_c") is not None:
        out["ambient_mean_c"] = float(weather["mean_temp_c"])
    if weather.get("max_temp_c") is not None and weather.get("mean_temp_c") is not None:
        # Amplitude is the swing the decay integrates over, not the peak.
        out["diurnal_amplitude_c"] = max(
            float(weather["max_temp_c"]) - float(weather["mean_temp_c"]), 0.0
        ) * 2.0

    # --- route -------------------------------------------------------------
    if route.get("transit_hours") is not None:
        out["transit_hours"] = float(route["transit_hours"])
    if route.get("vibration_index") is not None:
        out["road_roughness"] = 1.0 + float(route["vibration_index"])

    out["_missing"] = missing
    return out


def scenario_base(features: dict) -> dict:
    """Strip the metadata keys, leaving what the simulator accepts.

    A's ScenarioBatch rejects unknown columns, so anything this module adds for
    bookkeeping has to come back off before the dict is handed over.
    """
    return {k: v for k, v in features.items() if not k.startswith("_")}


def _coerce(field: str, value):
    if isinstance(DEFAULTS[field], float):
        try:
            return float(value)
        except (TypeError, ValueError):
            return DEFAULTS[field]
    return str(value)
