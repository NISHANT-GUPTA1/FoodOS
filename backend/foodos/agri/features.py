"""Layer 4 feature fusion — questionnaire, vision and external data into one matrix.

The whole design constraint of this module is **no leakage**, and it is worth
being precise about what that means here, because the usual definition is too
weak for a simulated dataset.

The obvious leak would be feeding the model a column derived from the label.
The subtler and more damaging one is feeding it the *physics*: hand a
gradient-booster the accumulated thermal stress and it will reproduce the loss
almost exactly, and you will have learned nothing except that division works.
Every reported accuracy figure would then be a statement about arithmetic
rather than about the model.

So the feature set is restricted to what a user can actually supply before the
outcome exists:

    Layer 1  questionnaire  harvest, handling, packaging, transport, durations
    Layer 2  vision         maturity, visual damage
    Layer 3  external       weather, road quality

plus pure clock arithmetic — dispatch hour, total exposure hours — which any
competent feature engineer would add and which contains no decay model.

Nothing computed by `simulate()` may appear. `FORBIDDEN_FEATURES` names those
columns and `assert_no_leakage()` enforces it, so a future change that quietly
adds `cum_stress_transit` to the matrix fails a test instead of shipping a
flattering accuracy number.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from foodos.agri.scenario import (
    HARVEST_START_HOUR,
    FieldHolding,
    HarvestMethod,
    HarvestWindow,
    Packaging,
    ScenarioBatch,
    TransportMode,
)
from foodos.agri.simulate import FARM_GATE_HOURS

#: Categorical questionnaire answers, with their full vocabulary pinned. Fixed
#: category lists matter: a single-row inference batch contains one packaging
#: type, and without a pinned vocabulary its encoding would differ from the one
#: the model trained on and every prediction would be quietly wrong.
CATEGORICAL_FEATURES: dict[str, list[str]] = {
    "harvest_method": [str(v) for v in HarvestMethod],
    "harvest_window": [str(v) for v in HarvestWindow],
    "field_holding": [str(v) for v in FieldHolding],
    "packaging": [str(v) for v in Packaging],
    "transport_mode": [str(v) for v in TransportMode],
}

#: Continuous inputs, straight from the three ingestion layers.
NUMERIC_FEATURES: list[str] = [
    "field_hours",
    "transit_hours",
    "mandi_holding_hours",
    "maturity_factor",
    "visual_damage_fraction",
    "ambient_mean_c",
    "diurnal_amplitude_c",
    "road_roughness",
    "quantity_kg",
]

#: Clock arithmetic only. No decay model, no temperature response — just when
#: things happen and for how long.
DERIVED_FEATURES: list[str] = [
    "dispatch_hour",
    "total_exposure_hours",
    "arrival_hour",
    "post_harvest_hours_before_transit",
]

FEATURE_NAMES: list[str] = (
    list(CATEGORICAL_FEATURES) + NUMERIC_FEATURES + DERIVED_FEATURES
)

#: Outputs of `simulate()`. Any of these appearing in the matrix is a leak.
FORBIDDEN_FEATURES: frozenset[str] = frozenset(
    {
        "total_loss",
        "farm_operations_loss",
        "market_level_loss",
        "accumulated_damage",
        "life_budget_median_days",
        "rul_hours_at_dispatch",
        "transit_equivalent_temp_c",
        "quality_score",
        "mass_lost_kg",
    }
    | {f"loss_{s}" for s in ("harvest", "field_holding", "farm_gate", "transit", "mandi")}
    | {f"cum_loss_{s}" for s in ("harvest", "field_holding", "farm_gate", "transit", "mandi")}
    | {f"cum_stress_{s}" for s in ("harvest", "field_holding", "farm_gate", "transit", "mandi")}
)

#: Prediction targets. Both are simulator outputs, which is the point — the
#: model is a surrogate for the simulator. See `risk_model` for what that does
#: and does not entitle anyone to claim.
TARGETS: dict[str, str] = {
    "loss": "total_loss",
    "rul": "rul_hours_at_dispatch",
}


def _harvest_hour(codes: np.ndarray) -> np.ndarray:
    out = np.full(len(codes), 8.0)
    for key, hour in HARVEST_START_HOUR.items():
        out[codes == str(key)] = float(hour)
    return out


def build_features(source: ScenarioBatch | pd.DataFrame) -> pd.DataFrame:
    """The feature matrix, from a scenario batch or an emitted frame.

    Accepting both matters: training reads the CSV the generator wrote, while
    inference has a live scenario and no simulator output at all. One function
    for both is the only way to guarantee the two see identical encodings.
    """
    raw = source.as_dict() if isinstance(source, ScenarioBatch) else source
    frame = pd.DataFrame({name: np.asarray(raw[name]) for name in FEATURE_NAMES[:0]})

    for name in CATEGORICAL_FEATURES:
        frame[name] = pd.Categorical(
            [str(v) for v in np.asarray(raw[name])],
            categories=CATEGORICAL_FEATURES[name],
        )
    for name in NUMERIC_FEATURES:
        frame[name] = np.asarray(raw[name], dtype=float)

    harvest_hour = _harvest_hour(np.asarray(raw["harvest_window"]))
    field_hours = np.asarray(raw["field_hours"], dtype=float)
    transit_hours = np.asarray(raw["transit_hours"], dtype=float)
    mandi_hours = np.asarray(raw["mandi_holding_hours"], dtype=float)

    before_transit = field_hours + FARM_GATE_HOURS
    frame["dispatch_hour"] = (harvest_hour + before_transit) % 24.0
    frame["post_harvest_hours_before_transit"] = before_transit
    frame["total_exposure_hours"] = before_transit + transit_hours + mandi_hours
    frame["arrival_hour"] = (harvest_hour + before_transit + transit_hours) % 24.0

    return frame[FEATURE_NAMES]


def assert_no_leakage(frame: pd.DataFrame) -> None:
    """Raise if any simulator output has found its way into the matrix."""
    leaked = FORBIDDEN_FEATURES.intersection(frame.columns)
    if leaked:
        raise ValueError(
            f"simulator outputs leaked into the feature matrix: {sorted(leaked)}. "
            "Every accuracy figure computed from this would be meaningless."
        )


def categorical_feature_names() -> list[str]:
    """Names LightGBM should treat as categorical rather than ordinal."""
    return list(CATEGORICAL_FEATURES)
