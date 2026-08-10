"""The five-stage loss pipeline, and the dataset generator.

    python -m foodos.agri.simulate --n 100000 --out data/agri/shipments.csv

Loss is produced by two independent removal processes running over five stages,
never by a single fudge factor:

  MECHANICAL   bruising, crushing, splitting, and the grade-out that follows.
               Accumulates as a dimensionless insult; survival is exp(-scale*D),
               which is bounded in [0, 1] by construction and cannot be pushed
               past 100% loss by a bad parameter.

  SPOILAGE     physiological decay. Accumulated thermal stress against a
               lognormal population of per-fruit life budgets — see `kinetics`.

They compound rather than add, because a fruit already crushed cannot also rot:

    surviving = (1 - mechanical_loss) * (1 - spoilage_loss)

The two are coupled in one direction, which matters: mechanical damage shortens
the life budget of what survives, so rough handling shows up twice — once as
fruit destroyed now, and again as fruit that spoils sooner. That second effect
is invisible in every loss model treating the two as separate line items, and it
is most of why crate choice matters more than operators expect.

Stage boundaries follow the NABCONS reporting split, so calibration targets map
onto stage sums with no re-interpretation:

    stages 1-3  harvest, field holding, farm gate    -> "farm operations"  8.37%
    stages 4-5  transit, mandi                       -> "market level"     3.25%

**Structure note.** The pipeline is split into `precompute()` and
`apply_scales()`. Everything expensive — the diurnal Arrhenius quadrature — is
independent of the two fitted scalars, so the calibrator computes it once and
then bisects over a pure multiply. That turns a two-minute fit into fifteen
seconds, and it is why `precompute` exists as a separate step rather than as an
optimisation someone bolted on later.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from foodos.agri import kinetics
from foodos.agri.commodity import CELSIUS_TO_KELVIN, R_GAS, TOMATO, Commodity
from foodos.agri.scenario import (
    FIELD_HOLDING_ABSOLUTE_C,
    FIELD_HOLDING_TEMP_OFFSET_C,
    HARVEST_DAMAGE,
    HARVEST_START_HOUR,
    PACKAGING_DAMAGE_FACTOR,
    PACKAGING_DIURNAL_DAMPING,
    TRANSPORT_ABSOLUTE_C,
    TRANSPORT_TEMP_OFFSET_C,
    TRANSPORT_VIBRATION_PER_HOUR,
    ScenarioBatch,
    diurnal_mean_rate,
    sample_diverse,
)

STAGES = ("harvest", "field_holding", "farm_gate", "transit", "mandi")
FARM_STAGES = ("harvest", "field_holding", "farm_gate")
MARKET_STAGES = ("transit", "mandi")

#: Mechanical insult from packing and from unloading, before the packaging
#: multiplier. Handling events, not durations — a crate is dropped the same
#: number of times whether the journey is two hours or twenty.
#:
#: The farm-side insult is set well above the market-side one on purpose. That
#: ratio is a modelling claim, and it is the claim NABCONS itself makes: loss is
#: concentrated in harvesting, field sorting and farm-gate packing rather than
#: in the haul. Getting the ratio wrong is not cosmetic — an earlier draft had
#: unloading and vibration large enough to consume the entire market-level
#: budget on their own, which left the calibrator no room for spoilage and drove
#: the spoilage scalar into its bracket floor.
PACK_INSULT = 0.016
UNLOAD_INSULT = 0.0040

#: Hours between the last fruit picked and the truck leaving. Sorting, grading
#: and loading. Short, but it happens at the hottest part of the farm day.
FARM_GATE_HOURS = 1.5

#: Mandi yards are shaded but unventilated.
MANDI_TEMP_OFFSET_C = 1.0


@dataclass(frozen=True)
class CalibrationParams:
    """The two fitted scalars, and nothing else.

    Kept to two on purpose. There are exactly two published targets, so a third
    knob would make the fit underdetermined — at which point "calibrated to
    NABCONS" stops meaning anything, because infinitely many parameter sets
    would hit the same two numbers.

    Both default to 1.0, meaning "the measured parameters, untouched". The
    fitted values landing near 1.0 is itself the result worth reporting: it says
    the published biophysics and the published survey agree without forcing.
    """

    mechanical_scale: float = 1.0
    spoilage_scale: float = 1.0


#: Fitted by `python -m foodos.agri.calibrate`. Regenerate rather than hand-edit.
FITTED = CalibrationParams(mechanical_scale=1.1795, spoilage_scale=1.0469)


@dataclass(frozen=True)
class StagePhysics:
    """Per-stage damage and stress, before either fitted scalar is applied.

    This is the expensive half of the pipeline and the half that never changes
    during a calibration sweep.
    """

    batch: ScenarioBatch
    damage: dict[str, np.ndarray] = field(default_factory=dict)
    stress: dict[str, np.ndarray] = field(default_factory=dict)
    transit_equivalent_temp_c: np.ndarray | None = None


def _map(codes: np.ndarray, table: dict, default=0.0) -> np.ndarray:
    """Look a questionnaire answer up in a physical-effect table."""
    out = np.full(len(codes), default, dtype=float)
    for key, value in table.items():
        if value is None:
            continue
        out[codes == str(key)] = float(value)
    return out


def _absolute_temp_mask(codes: np.ndarray, table: dict) -> tuple[np.ndarray, np.ndarray]:
    """Rows held at a controlled temperature, and what that temperature is."""
    mask = np.zeros(len(codes), dtype=bool)
    temps = np.zeros(len(codes), dtype=float)
    for key, value in table.items():
        hit = codes == str(key)
        mask |= hit
        temps[hit] = float(value)
    return mask, temps


def _stage_rate(
    commodity: Commodity,
    batch: ScenarioBatch,
    start_hour: np.ndarray,
    duration_hours: np.ndarray,
    offset_c: np.ndarray,
    controlled_mask: np.ndarray,
    controlled_temp_c: np.ndarray,
    amplitude_c: np.ndarray,
) -> np.ndarray:
    """Mean Arrhenius multiplier for one stage, controlled rows short-circuited."""
    rate = diurnal_mean_rate(
        commodity,
        start_hour=start_hour,
        duration_hours=duration_hours,
        ambient_mean_c=batch.ambient_mean_c,
        amplitude_c=amplitude_c,
        temp_offset_c=offset_c,
    )
    if controlled_mask.any():
        rate = rate.copy()
        rate[controlled_mask] = kinetics.arrhenius_rate_multiplier(
            controlled_temp_c[controlled_mask], commodity
        )
    return rate


def equivalent_temperature_c(rate, commodity: Commodity):
    """Invert an Arrhenius multiplier back to the flat temperature producing it.

    RUL is quoted at a temperature, not at a rate, so the diurnal-averaged
    transit rate is converted back. The result runs *above* mean air
    temperature — that gap is the convexity correction, surfaced where a user
    can see it rather than buried in a quadrature.
    """
    rate = np.maximum(np.asarray(rate, dtype=float), 1e-9)
    inv_kelvin = (
        1.0 / commodity.kelvin_ref() - np.log(rate) * R_GAS / commodity.ea_j_per_mol
    )
    return 1.0 / inv_kelvin - CELSIUS_TO_KELVIN


def precompute(batch: ScenarioBatch) -> StagePhysics:
    """Run the physics. Pure, vectorised, independent of the fitted scalars."""
    commodity = batch.commodity
    n = batch.n

    pkg_damage = _map(batch.packaging, PACKAGING_DAMAGE_FACTOR, default=1.0)
    pkg_damping = _map(batch.packaging, PACKAGING_DIURNAL_DAMPING, default=0.0)
    damped_amplitude = batch.diurnal_amplitude_c * (1.0 - pkg_damping)

    clock = _map(batch.harvest_window, HARVEST_START_HOUR, default=8.0)
    damage: dict[str, np.ndarray] = {}
    stress: dict[str, np.ndarray] = {}

    # --- stage 1: harvest ----------------------------------------------------
    # The act of picking, plus whatever the vision model already sees at intake.
    damage["harvest"] = (
        _map(batch.harvest_method, HARVEST_DAMAGE, default=0.010)
        + batch.visual_damage_fraction
    )
    stress["harvest"] = np.zeros(n)

    # --- stage 2: field holding ---------------------------------------------
    # Field heat. Fruit in the sun runs well above air temperature, and this is
    # the stage a pre-dawn harvest actually attacks.
    field_ctrl_mask, field_ctrl_temp = _absolute_temp_mask(
        batch.field_holding, FIELD_HOLDING_ABSOLUTE_C
    )
    field_rate = _stage_rate(
        commodity, batch, clock, batch.field_hours,
        _map(batch.field_holding, FIELD_HOLDING_TEMP_OFFSET_C, default=0.5),
        field_ctrl_mask, field_ctrl_temp, batch.diurnal_amplitude_c,
    )
    damage["field_holding"] = np.zeros(n)
    stress["field_holding"] = (batch.field_hours / 24.0) * field_rate
    clock = clock + batch.field_hours

    # --- stage 3: farm gate --------------------------------------------------
    # Sorting, grading, packing. A handling event, so the insult does not scale
    # with time — but the packaging choice multiplies it and every later one.
    gate_hours = np.full(n, FARM_GATE_HOURS)
    gate_rate = _stage_rate(
        commodity, batch, clock, gate_hours, np.full(n, 0.5),
        np.zeros(n, dtype=bool), np.zeros(n), batch.diurnal_amplitude_c,
    )
    damage["farm_gate"] = PACK_INSULT * pkg_damage
    stress["farm_gate"] = (gate_hours / 24.0) * gate_rate
    clock = clock + gate_hours

    # --- stage 4: transit ----------------------------------------------------
    # Vibration accumulates per hour and scales with road roughness and with how
    # little the packaging isolates the fruit from the deck.
    transit_ctrl_mask, transit_ctrl_temp = _absolute_temp_mask(
        batch.transport_mode, TRANSPORT_ABSOLUTE_C
    )
    transit_rate = _stage_rate(
        commodity, batch, clock, batch.transit_hours,
        _map(batch.transport_mode, TRANSPORT_TEMP_OFFSET_C, default=3.0),
        transit_ctrl_mask, transit_ctrl_temp, damped_amplitude,
    )
    vibration = _map(batch.transport_mode, TRANSPORT_VIBRATION_PER_HOUR, default=0.0006)
    damage["transit"] = (
        vibration * batch.transit_hours * batch.road_roughness * pkg_damage
    )
    stress["transit"] = (batch.transit_hours / 24.0) * transit_rate
    clock = clock + batch.transit_hours

    # --- stage 5: mandi ------------------------------------------------------
    mandi_rate = _stage_rate(
        commodity, batch, clock, batch.mandi_holding_hours,
        np.full(n, MANDI_TEMP_OFFSET_C),
        np.zeros(n, dtype=bool), np.zeros(n), batch.diurnal_amplitude_c,
    )
    damage["mandi"] = UNLOAD_INSULT * pkg_damage
    stress["mandi"] = (batch.mandi_holding_hours / 24.0) * mandi_rate

    return StagePhysics(
        batch=batch,
        damage=damage,
        stress=stress,
        transit_equivalent_temp_c=equivalent_temperature_c(transit_rate, commodity),
    )


def stage_losses(
    physics: StagePhysics, params: CalibrationParams
) -> dict[str, np.ndarray]:
    """Apply the two scalars. Cheap — this is what the calibrator bisects on."""
    commodity = physics.batch.commodity
    sigma = commodity.life_spread_sigma
    n = physics.batch.n

    damage = np.zeros(n)
    stress = np.zeros(n)
    previous = np.zeros(n)
    out: dict[str, np.ndarray] = {}

    for stage in STAGES:
        damage = damage + physics.damage[stage]
        stress = stress + params.spoilage_scale * physics.stress[stage]

        life_median = kinetics.life_budget_median_by_factor(
            commodity, physics.batch.maturity_factor, np.clip(damage, 0.0, 0.6)
        )
        mechanical = 1.0 - np.exp(-params.mechanical_scale * damage)
        spoilage = kinetics.spoilage_fraction(stress, life_median, sigma)
        total = 1.0 - (1.0 - mechanical) * (1.0 - spoilage)

        out[f"loss_{stage}"] = total - previous
        out[f"cum_loss_{stage}"] = total.copy()
        out[f"cum_stress_{stage}"] = stress.copy()
        previous = total

    out["accumulated_damage"] = damage
    out["life_budget_median_days"] = kinetics.life_budget_median_by_factor(
        commodity, physics.batch.maturity_factor, np.clip(damage, 0.0, 0.6)
    )
    out["farm_operations_loss"] = sum(out[f"loss_{s}"] for s in FARM_STAGES)
    out["market_level_loss"] = sum(out[f"loss_{s}"] for s in MARKET_STAGES)
    out["total_loss"] = out["cum_loss_mandi"]
    return out


def apply_scales(physics: StagePhysics, params: CalibrationParams) -> pd.DataFrame:
    """Scaled losses, assembled into the emitted row shape."""
    batch = physics.batch
    computed = stage_losses(physics, params)

    frame = pd.DataFrame(batch.as_dict())
    for key, value in computed.items():
        frame[key] = value

    # RUL as reported to the user: measured the moment the truck leaves the farm
    # gate, looking forward at the transit temperature it is about to see.
    frame["rul_hours_at_dispatch"] = kinetics.remaining_useful_life_hours(
        computed["cum_stress_farm_gate"],
        computed["life_budget_median_days"],
        physics.transit_equivalent_temp_c,
        batch.commodity,
    )
    frame["transit_equivalent_temp_c"] = physics.transit_equivalent_temp_c
    frame["quality_score"] = (100.0 * (1.0 - computed["total_loss"])).clip(0.0, 100.0)
    frame["mass_lost_kg"] = computed["total_loss"] * batch.quantity_kg
    return frame


def simulate(
    batch: ScenarioBatch, params: CalibrationParams | None = None
) -> pd.DataFrame:
    """Run every shipment through the five stages. One row each.

    Pure: no database, no I/O, no RNG. Same scenario in, same frame out, which
    is what lets the calibrator bisect on it and the tests assert exact numbers.
    """
    return apply_scales(precompute(batch), params or FITTED)


def summarise(frame: pd.DataFrame) -> dict[str, float]:
    """Mean loss by NABCONS reporting stage, as percentages."""
    return {
        "farm_operations_pct": float(frame["farm_operations_loss"].mean() * 100.0),
        "market_level_pct": float(frame["market_level_loss"].mean() * 100.0),
        "total_pct": float(frame["total_loss"].mean() * 100.0),
        "median_rul_hours": float(frame["rul_hours_at_dispatch"].median()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate the calibrated synthetic shipment dataset."
    )
    parser.add_argument("--n", type=int, default=100_000)
    parser.add_argument("--seed", type=int, default=11)
    parser.add_argument("--out", type=Path, default=Path("data/agri/shipments.csv"))
    args = parser.parse_args()

    frame = simulate(sample_diverse(TOMATO, args.n, seed=args.seed))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(args.out, index=False)

    stats = summarise(frame)
    print(f"{len(frame):,} shipments x {len(frame.columns)} columns -> {args.out}")
    print(f"  farm operations   {stats['farm_operations_pct']:6.2f} %")
    print(f"  market level      {stats['market_level_pct']:6.2f} %")
    print(f"  total             {stats['total_pct']:6.2f} %")
    print(f"  median RUL        {stats['median_rul_hours']:6.1f} h")
    print(
        "\nThese are the DIVERSE training distribution, which spans good practice"
        "\nthat is rare in the field, so they are not meant to match NABCONS."
        "\nThe baseline sampler is what does: python -m foodos.agri.calibrate"
    )


if __name__ == "__main__":
    main()
