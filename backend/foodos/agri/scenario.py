"""The shipment scenario — the questionnaire, as a sampleable feature space.

Every field here is something an FPO manager can answer in one tap without an
instrument. That constraint is the product: the moment a feature needs a probe,
a logger or a lab, the 30-second questionnaire becomes a 30-minute one and
nobody fills it in twice.

Two samplers, and keeping them apart is what stops the calibration eating its
own tail:

  `sample_baseline`  modal Indian practice for tomato — what the NABCONS survey
                     was actually measuring. Used *only* to fit the two
                     calibration scalars. Narrow on purpose.

  `sample_diverse`   the whole questionnaire space, including the good practice
                     nobody currently follows. Used to generate training data.
                     Wide on purpose.

Fit on the first, train on the second, and the model has to extrapolate off the
calibration point to be useful — which is exactly the property that makes the
held-out behavioural checks in `tests/test_agri/` mean something.

Temperatures are handled as diurnal cycles rather than daily means. Arrhenius is
convex, so the average of the rate is strictly greater than the rate at the
average — using a mean temperature would quietly under-predict every loss, and
would erase the difference between a pre-dawn and a midday harvest, which is one
of the few free interventions in the whole system.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

import numpy as np

from foodos.agri.commodity import Commodity

# --------------------------------------------------------------------------
# Questionnaire vocabulary, and what each answer does physically
# --------------------------------------------------------------------------


class HarvestMethod(StrEnum):
    MANUAL = "manual"
    MECHANICAL = "mechanical"


class HarvestWindow(StrEnum):
    PRE_DAWN = "pre_dawn"  # 04:00-07:00
    MORNING = "morning"  # 07:00-10:00
    MIDDAY = "midday"  # 10:00-15:00
    AFTERNOON = "afternoon"  # 15:00-18:00


class FieldHolding(StrEnum):
    OPEN_SUN = "open_sun"
    SHADE = "shade"
    COLD_ROOM = "cold_room"


class Packaging(StrEnum):
    LOOSE_BULK = "loose_bulk"
    GUNNY_BAG = "gunny_bag"
    WOODEN_CRATE = "wooden_crate"
    VENTILATED_PLASTIC_CRATE = "ventilated_plastic_crate"


class TransportMode(StrEnum):
    OPEN_TRUCK = "open_truck"
    TARPAULIN = "tarpaulin"
    REFRIGERATED = "refrigerated"


#: Base mechanical insult from the harvest act itself, dimensionless.
#: Mechanical harvesting of a soft fruit is rougher than a careful hand pick;
#: this is the only place in the model where manual labour wins outright.
HARVEST_DAMAGE = {
    HarvestMethod.MANUAL: 0.010,
    HarvestMethod.MECHANICAL: 0.028,
}

#: Clock hour the harvest window starts. Drives the diurnal phase the fruit
#: enters at, which is what makes pre-dawn harvesting worth anything.
HARVEST_START_HOUR = {
    HarvestWindow.PRE_DAWN: 5.0,
    HarvestWindow.MORNING: 8.0,
    HarvestWindow.MIDDAY: 12.0,
    HarvestWindow.AFTERNOON: 16.0,
}

#: Degrees above ambient air the produce mass itself sits at. Fruit in direct
#: sun runs well above air temperature — the field-heat term everyone
#: underestimates.
FIELD_HOLDING_TEMP_OFFSET_C = {
    FieldHolding.OPEN_SUN: 6.0,
    FieldHolding.SHADE: 0.5,
    FieldHolding.COLD_ROOM: None,  # absolute, see FIELD_HOLDING_ABSOLUTE_C
}
FIELD_HOLDING_ABSOLUTE_C = {FieldHolding.COLD_ROOM: 13.0}

#: Multiplier on accumulated mechanical damage during packing and transit, and
#: the fraction of the diurnal swing the packaging damps out.
PACKAGING_DAMAGE_FACTOR = {
    Packaging.LOOSE_BULK: 2.20,  # crush loading from stack height
    Packaging.GUNNY_BAG: 1.55,
    Packaging.WOODEN_CRATE: 1.10,  # splinters and nail heads, but it stacks
    Packaging.VENTILATED_PLASTIC_CRATE: 0.72,
}
PACKAGING_DIURNAL_DAMPING = {
    Packaging.LOOSE_BULK: 0.00,
    Packaging.GUNNY_BAG: 0.10,
    Packaging.WOODEN_CRATE: 0.20,
    Packaging.VENTILATED_PLASTIC_CRATE: 0.30,
}

#: Degrees above ambient inside the load, and the per-hour vibration insult.
#: A tarpaulin shades the load but cuts airflow; at road speed the net is a
#: small gain over an open deck, not the large one operators assume.
TRANSPORT_TEMP_OFFSET_C = {
    TransportMode.OPEN_TRUCK: 3.0,
    TransportMode.TARPAULIN: 1.5,
    TransportMode.REFRIGERATED: None,
}
TRANSPORT_ABSOLUTE_C = {TransportMode.REFRIGERATED: 10.0}
TRANSPORT_VIBRATION_PER_HOUR = {
    TransportMode.OPEN_TRUCK: 0.00060,
    TransportMode.TARPAULIN: 0.00060,
    TransportMode.REFRIGERATED: 0.00040,  # air-ride suspension is standard
}


@dataclass
class ScenarioBatch:
    """`n` shipments, columnar. Every array has length `n`.

    Columnar rather than a list of objects because the whole point is to
    simulate a hundred thousand of these at once, and a Python loop over 100k
    objects is a minute you do not have at hour two.
    """

    n: int
    commodity: Commodity

    # --- Layer 1: questionnaire ---------------------------------------------
    quantity_kg: np.ndarray
    harvest_method: np.ndarray  # str codes
    harvest_window: np.ndarray
    field_holding: np.ndarray
    field_hours: np.ndarray
    packaging: np.ndarray
    transport_mode: np.ndarray
    transit_hours: np.ndarray
    mandi_holding_hours: np.ndarray

    # --- Layer 2: vision ------------------------------------------------------
    #: Continuous maturity, as a multiple of reference (turning) life. Real
    #: fruit sits between USDA colour stages, so the sampler works in factors
    #: and the discrete stage is derived for display only.
    maturity_factor: np.ndarray
    #: Surface damage fraction the vision model reports at intake.
    visual_damage_fraction: np.ndarray

    # --- Layer 3: external ----------------------------------------------------
    ambient_mean_c: np.ndarray
    diurnal_amplitude_c: np.ndarray
    road_roughness: np.ndarray  # 1.0 = national highway, 2.0 = rural link road

    meta: dict = field(default_factory=dict)

    def as_dict(self) -> dict[str, np.ndarray]:
        return {
            "quantity_kg": self.quantity_kg,
            "harvest_method": self.harvest_method,
            "harvest_window": self.harvest_window,
            "field_holding": self.field_holding,
            "field_hours": self.field_hours,
            "packaging": self.packaging,
            "transport_mode": self.transport_mode,
            "transit_hours": self.transit_hours,
            "mandi_holding_hours": self.mandi_holding_hours,
            "maturity_factor": self.maturity_factor,
            "visual_damage_fraction": self.visual_damage_fraction,
            "ambient_mean_c": self.ambient_mean_c,
            "diurnal_amplitude_c": self.diurnal_amplitude_c,
            "road_roughness": self.road_roughness,
        }


# --------------------------------------------------------------------------
# Diurnal temperature integration
# --------------------------------------------------------------------------

#: Quadrature points per exposure. Arrhenius is smooth; 24 points resolves a
#: diurnal sinusoid to well under a percent, and the cost is one (n, 24) array.
_QUAD_POINTS = 24


def diurnal_mean_rate(
    commodity: Commodity,
    start_hour,
    duration_hours,
    ambient_mean_c,
    amplitude_c,
    temp_offset_c=0.0,
    absolute_temp_c=None,
):
    """Mean deterioration rate over an exposure that spans a diurnal cycle.

    Averages the *rate*, not the temperature. Arrhenius is convex, so those two
    differ and the difference is not small: a load swinging 26-38 C deteriorates
    measurably faster than one held flat at 32 C. Averaging temperature first
    would hide that, and with it every argument for moving work into the night.

    `absolute_temp_c` short-circuits the cycle for a controlled environment — a
    reefer or a cold room does not care what the sun is doing.
    """
    from foodos.agri.kinetics import arrhenius_rate_multiplier

    duration_hours = np.asarray(duration_hours, dtype=float)

    if absolute_temp_c is not None:
        rate = arrhenius_rate_multiplier(absolute_temp_c, commodity)
        return np.broadcast_to(rate, duration_hours.shape).astype(float)

    start_hour = np.asarray(start_hour, dtype=float)
    ambient_mean_c = np.asarray(ambient_mean_c, dtype=float)
    amplitude_c = np.asarray(amplitude_c, dtype=float)

    # Sample the exposure at its own midpoints so a short exposure resolves as
    # sharply as a long one.
    frac = (np.arange(_QUAD_POINTS, dtype=float) + 0.5) / _QUAD_POINTS
    clock = start_hour[:, None] + duration_hours[:, None] * frac[None, :]

    # Daily minimum near 03:00, maximum near 15:00 — the standard shifted cosine
    # used for Indian station data.
    phase = 2.0 * np.pi * (clock - 15.0) / 24.0
    temp = ambient_mean_c[:, None] + amplitude_c[:, None] * 0.5 * np.cos(phase)
    temp = temp + np.asarray(temp_offset_c, dtype=float).reshape(-1, 1)

    return arrhenius_rate_multiplier(temp, commodity).mean(axis=1)


# --------------------------------------------------------------------------
# Samplers
# --------------------------------------------------------------------------


def _choice(rng, options: dict, n: int) -> np.ndarray:
    keys = list(options)
    probs = np.array([options[k] for k in keys], dtype=float)
    probs = probs / probs.sum()
    return rng.choice(np.array([str(k) for k in keys]), size=n, p=probs)


def sample_baseline(commodity: Commodity, n: int, seed: int = 7) -> ScenarioBatch:
    """Modal Indian tomato practice — the population NABCONS surveyed.

    Deliberately narrow. This is the calibration set, so it must describe what
    the survey measured, not what the product hopes to sell. Good practice is
    present only at the rate it actually occurs: cold rooms and reefers are rare
    at the farm gate, which is the entire reason the loss figure is 8.37%.
    """
    rng = np.random.default_rng(seed)

    return ScenarioBatch(
        n=n,
        commodity=commodity,
        quantity_kg=rng.uniform(2_000, 12_000, n),
        harvest_method=_choice(
            rng, {HarvestMethod.MANUAL: 0.93, HarvestMethod.MECHANICAL: 0.07}, n
        ),
        harvest_window=_choice(
            rng,
            {
                HarvestWindow.PRE_DAWN: 0.14,
                HarvestWindow.MORNING: 0.38,
                HarvestWindow.MIDDAY: 0.34,
                HarvestWindow.AFTERNOON: 0.14,
            },
            n,
        ),
        field_holding=_choice(
            rng,
            {
                FieldHolding.OPEN_SUN: 0.46,
                FieldHolding.SHADE: 0.50,
                FieldHolding.COLD_ROOM: 0.04,
            },
            n,
        ),
        field_hours=rng.gamma(shape=2.2, scale=1.9, size=n).clip(0.2, 14.0),
        packaging=_choice(
            rng,
            {
                Packaging.LOOSE_BULK: 0.22,
                Packaging.GUNNY_BAG: 0.34,
                Packaging.WOODEN_CRATE: 0.24,
                Packaging.VENTILATED_PLASTIC_CRATE: 0.20,
            },
            n,
        ),
        transport_mode=_choice(
            rng,
            {
                TransportMode.OPEN_TRUCK: 0.62,
                TransportMode.TARPAULIN: 0.35,
                TransportMode.REFRIGERATED: 0.03,
            },
            n,
        ),
        # Most tomato volume reaches an APMC within a few hours — the Kolar to
        # Delhi haul everyone quotes is the tail, not the mode. Lognormal with a
        # 5 h median reproduces that shape and keeps the 40 h run inside the
        # distribution instead of dominating it.
        transit_hours=np.exp(rng.normal(np.log(5.0), 0.60, n)).clip(1.0, 48.0),
        mandi_holding_hours=rng.gamma(shape=1.6, scale=2.2, size=n).clip(0.5, 30.0),
        maturity_factor=rng.normal(0.95, 0.22, n).clip(0.42, 1.75),
        visual_damage_fraction=rng.beta(1.7, 42.0, n).clip(0.0, 0.35),
        # Annual mean across Indian tomato marketing, not peak summer. The rabi
        # crop is large, so a 29 C average would describe only the worst season
        # and would inflate every calibrated spoilage figure.
        ambient_mean_c=rng.normal(25.0, 5.5, n).clip(10.0, 42.0),
        diurnal_amplitude_c=rng.normal(9.5, 2.0, n).clip(3.0, 17.0),
        road_roughness=rng.normal(1.45, 0.32, n).clip(0.85, 2.4),
        meta={"sampler": "baseline", "seed": seed},
    )


def sample_diverse(commodity: Commodity, n: int, seed: int = 11) -> ScenarioBatch:
    """The full questionnaire space — the training distribution.

    Practice choices are near-uniform rather than at their real-world rates, so
    the model sees enough refrigerated, pre-dawn and crated shipments to learn
    what they do. Training on the baseline mix instead would leave the model
    almost blind to every intervention the product exists to recommend.
    """
    rng = np.random.default_rng(seed)

    return ScenarioBatch(
        n=n,
        commodity=commodity,
        quantity_kg=rng.uniform(500, 20_000, n),
        harvest_method=_choice(
            rng, {HarvestMethod.MANUAL: 0.6, HarvestMethod.MECHANICAL: 0.4}, n
        ),
        harvest_window=_choice(
            rng,
            {
                HarvestWindow.PRE_DAWN: 0.25,
                HarvestWindow.MORNING: 0.25,
                HarvestWindow.MIDDAY: 0.25,
                HarvestWindow.AFTERNOON: 0.25,
            },
            n,
        ),
        field_holding=_choice(
            rng,
            {
                FieldHolding.OPEN_SUN: 0.34,
                FieldHolding.SHADE: 0.33,
                FieldHolding.COLD_ROOM: 0.33,
            },
            n,
        ),
        field_hours=rng.uniform(0.1, 16.0, n),
        packaging=_choice(
            rng,
            {
                Packaging.LOOSE_BULK: 0.25,
                Packaging.GUNNY_BAG: 0.25,
                Packaging.WOODEN_CRATE: 0.25,
                Packaging.VENTILATED_PLASTIC_CRATE: 0.25,
            },
            n,
        ),
        transport_mode=_choice(
            rng,
            {
                TransportMode.OPEN_TRUCK: 0.34,
                TransportMode.TARPAULIN: 0.33,
                TransportMode.REFRIGERATED: 0.33,
            },
            n,
        ),
        transit_hours=rng.uniform(1.0, 52.0, n),
        mandi_holding_hours=rng.uniform(0.5, 48.0, n),
        maturity_factor=rng.uniform(0.42, 1.75, n),
        # Reaches much closer to zero than the baseline draw. A training set
        # whose cleanest shipment still arrives 8% damaged teaches the model
        # nothing about what an undamaged load looks like, and the near-clean
        # end is exactly where the "your handling is fine, your timing is not"
        # recommendation lives.
        visual_damage_fraction=rng.beta(1.2, 26.0, n).clip(0.0, 0.45),
        ambient_mean_c=rng.uniform(12.0, 43.0, n),
        diurnal_amplitude_c=rng.uniform(2.0, 18.0, n),
        road_roughness=rng.uniform(0.85, 2.5, n),
        meta={"sampler": "diverse", "seed": seed},
    )
