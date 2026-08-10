"""The checks that are not circular.

Two scalars were fitted so the simulator reproduces two NABCONS figures. Testing
that it reproduces them proves only that the bisection converged. **Every
assertion in this file is a claim from the food-science literature that was not
fitted to anything**, and any of them can fail — which is what makes them worth
running.

Grouped by what a hostile reviewer would attack:

  kinetics      does the temperature response match published tomato behaviour
  interventions do the free and cheap fixes actually help, in the right order
  monotonicity  does loss respond in the correct direction to every driver
  bounds        can any parameter drive the model outside physical limits
"""

from __future__ import annotations

import numpy as np
import pytest

from foodos.agri import kinetics
from foodos.agri.commodity import TOMATO, MaturityStage
from foodos.agri.scenario import (
    FieldHolding,
    HarvestWindow,
    Packaging,
    TransportMode,
    diurnal_mean_rate,
    sample_diverse,
)
from foodos.agri.simulate import simulate, summarise

from .conftest import make_controlled


def _loss(column: str = "total_loss", **overrides) -> float:
    """Mean value of one loss column for a controlled scenario."""
    n = 1
    for value in overrides.values():
        if not (np.isscalar(value) or isinstance(value, str)):
            n = max(n, len(value))
    return float(simulate(make_controlled(n, **overrides))[column].mean())


def _total_loss(**overrides) -> float:
    return _loss("total_loss", **overrides)


def _farm_loss(**overrides) -> float:
    """Loss booked through the farm gate — stages 1-3 only."""
    return _loss("cum_loss_farm_gate", **overrides)


# ==========================================================================
# Kinetics — published tomato behaviour, none of it fitted
# ==========================================================================


def test_q10_sits_inside_the_published_tomato_band():
    """Published tomato Q10 runs 2.0-3.0. Ea was chosen from the literature, not
    tuned, so this is a real constraint on it rather than a tautology."""
    q10 = kinetics.q10_at(20.0, TOMATO)
    assert 2.0 <= q10 <= 3.0, f"Q10 {q10:.2f} outside the published band"


def test_the_rate_is_one_at_the_reference_temperature():
    assert float(kinetics.arrhenius_rate_multiplier(TOMATO.ref_temp_c, TOMATO)) == (
        pytest.approx(1.0, abs=1e-9)
    )


def test_warmer_is_always_faster_above_the_chilling_threshold():
    temps = np.arange(13.0, 45.0, 1.0)
    rates = kinetics.arrhenius_rate_multiplier(temps, TOMATO)
    assert np.all(np.diff(rates) > 0)


def test_ten_degrees_warmer_multiplies_the_rate_by_q10():
    """The defining property of Q10. If this drifts, the Arrhenius form and the
    reported Q10 have stopped describing the same model."""
    for base in (15.0, 20.0, 25.0, 30.0):
        ratio = float(
            kinetics.arrhenius_rate_multiplier(base + 10.0, TOMATO)
            / kinetics.arrhenius_rate_multiplier(base, TOMATO)
        )
        assert ratio == pytest.approx(kinetics.q10_at(base, TOMATO), rel=1e-9)


def test_chilling_injury_makes_sub_zero_worse_than_cold_storage():
    """Tomato chill-injures below 12.5 C. Without this the optimiser eventually
    recommends freezing the load, which is confidently, expensively wrong."""
    best_rate, best_temp = min(
        (float(kinetics.arrhenius_rate_multiplier(t, TOMATO)), t)
        for t in np.arange(-2.0, 20.0, 0.5)
    )
    assert float(kinetics.arrhenius_rate_multiplier(-2.0, TOMATO)) > best_rate
    assert best_temp > 0.0, "the rate minimum must not sit at or below freezing"


def test_riper_fruit_has_less_life():
    stages = [
        MaturityStage.MATURE_GREEN,
        MaturityStage.BREAKER,
        MaturityStage.TURNING,
        MaturityStage.PINK,
        MaturityStage.LIGHT_RED,
        MaturityStage.RED,
    ]
    budgets = [float(kinetics.life_budget_median(TOMATO, s)) for s in stages]
    assert np.all(np.diff(budgets) < 0)


def test_the_diurnal_average_exceeds_the_rate_at_the_average_temperature():
    """Jensen's inequality, and the reason the model integrates a cycle instead
    of taking a daily mean. Arrhenius is convex, so a load swinging 24-36 C
    deteriorates strictly faster than one held flat at 30 C. Averaging
    temperature first would erase that — and with it every argument for moving
    work into the cool hours."""
    swinging = float(
        diurnal_mean_rate(
            TOMATO,
            start_hour=np.array([6.0]),
            duration_hours=np.array([24.0]),
            ambient_mean_c=np.array([30.0]),
            amplitude_c=np.array([12.0]),
        )[0]
    )
    flat = float(kinetics.arrhenius_rate_multiplier(30.0, TOMATO))
    assert swinging > flat * 1.02


# ==========================================================================
# Interventions — the recommendations the product exists to make
# ==========================================================================


def test_pre_dawn_harvest_beats_midday_on_field_heat():
    """The published claim is about *field heat*, so it is asserted on the farm
    stages where it applies. See the interaction test below for why the same
    comparison across the whole journey is not the same question."""
    pre_dawn = _farm_loss(
        harvest_window=HarvestWindow.PRE_DAWN, field_holding=FieldHolding.OPEN_SUN
    )
    midday = _farm_loss(
        harvest_window=HarvestWindow.MIDDAY, field_holding=FieldHolding.OPEN_SUN
    )
    assert pre_dawn < midday


def test_a_pre_dawn_harvest_is_wasted_if_the_truck_then_runs_through_the_afternoon():
    """A real finding from this model, and a product insight worth surfacing.

    Harvesting at 05:00 and holding four hours puts dispatch at 10:30, so a ten
    hour haul runs straight through the afternoon peak. Harvesting at midday
    pushes the same haul into the cool of the night. Measured end to end the two
    very nearly cancel — the field-heat saving is handed straight back in
    transit.

    So "harvest pre-dawn" is not advice on its own. "Harvest pre-dawn *and
    dispatch before the heat*" is, and a scheduler that optimises the harvest
    window without looking at the departure time will confidently recommend
    something worth nothing. Asserted loosely, as a guard on the interaction
    existing at all rather than on its exact size.
    """
    pre_dawn = _total_loss(
        harvest_window=HarvestWindow.PRE_DAWN, field_holding=FieldHolding.OPEN_SUN
    )
    midday = _total_loss(
        harvest_window=HarvestWindow.MIDDAY, field_holding=FieldHolding.OPEN_SUN
    )
    assert abs(pre_dawn - midday) < 0.02, (
        "the transit-window effect should very nearly cancel the field-heat "
        f"saving; got {pre_dawn:.4f} vs {midday:.4f}"
    )


def test_shade_beats_open_sun_in_the_field():
    assert _total_loss(field_holding=FieldHolding.SHADE) < _total_loss(
        field_holding=FieldHolding.OPEN_SUN
    )


def test_packaging_ranks_in_the_published_order():
    """Ventilated plastic < wooden crate < gunny < loose bulk, on loss. This
    ordering is the one thing an FPO can change with a capital purchase, so
    getting the direction wrong would be an expensive recommendation."""
    losses = [
        _total_loss(packaging=p)
        for p in (
            Packaging.VENTILATED_PLASTIC_CRATE,
            Packaging.WOODEN_CRATE,
            Packaging.GUNNY_BAG,
            Packaging.LOOSE_BULK,
        )
    ]
    assert np.all(np.diff(losses) > 0), losses


def test_refrigerated_transport_beats_an_open_deck():
    reefer = _total_loss(transport_mode=TransportMode.REFRIGERATED, transit_hours=30.0)
    open_truck = _total_loss(transport_mode=TransportMode.OPEN_TRUCK, transit_hours=30.0)
    assert reefer < open_truck


def test_a_reefer_earns_more_on_a_long_haul_than_a_short_one():
    """The intervention has to be worth *more* when there is more transit to
    protect, otherwise the optimiser cannot rank spending on it."""

    def saving(hours: float) -> float:
        return _total_loss(
            transport_mode=TransportMode.OPEN_TRUCK, transit_hours=hours
        ) - _total_loss(transport_mode=TransportMode.REFRIGERATED, transit_hours=hours)

    assert saving(36.0) > saving(6.0)


def test_getting_out_of_the_field_sooner_helps():
    assert _total_loss(field_hours=1.0) < _total_loss(field_hours=10.0)


# ==========================================================================
# Monotonicity — direction of response to every continuous driver
# ==========================================================================


@pytest.mark.parametrize(
    "field, values, expect_increasing",
    [
        ("ambient_mean_c", np.arange(16.0, 40.0, 2.0), True),
        ("transit_hours", np.arange(2.0, 48.0, 4.0), True),
        ("field_hours", np.arange(0.5, 14.0, 1.5), True),
        ("mandi_holding_hours", np.arange(1.0, 30.0, 3.0), True),
        ("road_roughness", np.arange(0.9, 2.5, 0.2), True),
        ("visual_damage_fraction", np.arange(0.0, 0.4, 0.04), True),
        # More life at harvest must mean less loss.
        ("maturity_factor", np.arange(0.45, 1.75, 0.12), False),
    ],
)
def test_loss_is_monotonic_in_every_driver(field, values, expect_increasing):
    frame = simulate(make_controlled(len(values), **{field: values}))
    diffs = np.diff(frame["total_loss"].to_numpy())
    if expect_increasing:
        assert np.all(diffs > 0), f"{field} should increase loss"
    else:
        assert np.all(diffs < 0), f"{field} should decrease loss"


def test_rul_falls_as_the_forward_temperature_rises():
    temps = np.arange(10.0, 40.0, 2.0)
    frame = simulate(make_controlled(len(temps), ambient_mean_c=temps))
    assert np.all(np.diff(frame["rul_hours_at_dispatch"].to_numpy()) < 0)


def test_the_transit_equivalent_temperature_exceeds_the_mean_air_temperature():
    """The convexity correction, surfaced in a field a user can read. If these
    were equal the diurnal integration would not be doing anything."""
    frame = simulate(
        make_controlled(
            1,
            ambient_mean_c=30.0,
            diurnal_amplitude_c=12.0,
            transport_mode=TransportMode.OPEN_TRUCK,
        )
    )
    assert float(frame["transit_equivalent_temp_c"].iloc[0]) > 30.0


# ==========================================================================
# Bounds — can any input drive the model somewhere physically impossible
# ==========================================================================


def test_loss_stays_inside_zero_and_one_under_extremes():
    frame = simulate(sample_diverse(TOMATO, 20_000, seed=3))
    for column in ("total_loss", "farm_operations_loss", "market_level_loss"):
        assert frame[column].min() >= -1e-12, column
        assert frame[column].max() <= 1.0 + 1e-12, column
    assert frame["rul_hours_at_dispatch"].min() >= 0.0
    assert frame["quality_score"].between(0.0, 100.0).all()


def test_stage_losses_sum_to_the_total():
    """Loss is booked per stage and reported as a farm/market split. If those
    stop reconciling, every number attributed to a stage is wrong."""
    frame = simulate(sample_diverse(TOMATO, 5_000, seed=5))
    recombined = frame["farm_operations_loss"] + frame["market_level_loss"]
    assert np.allclose(recombined, frame["total_loss"], atol=1e-12)


def test_a_pristine_instant_shipment_loses_almost_nothing():
    """The zero case. Cold, immediate, undamaged, crated — anything more than a
    trace of loss here means a stage is charging a fixed toll it should not."""
    loss = _total_loss(
        field_hours=0.1,
        transit_hours=0.5,
        mandi_holding_hours=0.5,
        visual_damage_fraction=0.0,
        maturity_factor=1.75,
        ambient_mean_c=14.0,
        diurnal_amplitude_c=2.0,
        field_holding=FieldHolding.COLD_ROOM,
        transport_mode=TransportMode.REFRIGERATED,
        packaging=Packaging.VENTILATED_PLASTIC_CRATE,
        road_roughness=0.9,
    )
    assert loss < 0.05, f"pristine shipment lost {loss:.1%}"


def test_the_simulator_is_deterministic():
    first = simulate(sample_diverse(TOMATO, 1_000, seed=17))
    second = simulate(sample_diverse(TOMATO, 1_000, seed=17))
    assert np.allclose(first["total_loss"], second["total_loss"], atol=0.0)


def test_the_diverse_training_set_covers_a_wide_loss_range():
    """A training set clustered at one loss level teaches a model nothing. This
    guards the sampler, not the physics: if someone narrows the ranges, the
    dataset silently stops being useful and no other test would notice.

    Note the floor. The best percentile still loses a few percent, because five
    handling stages always cost something — there is no zero-loss route through
    a harvest, a pack, a haul and an unload. That irreducible floor is a real
    property of the model, not a defect, and it is asserted rather than wished
    away: a sampler that started producing genuinely zero-loss shipments would
    be skipping a stage.
    """
    frame = simulate(sample_diverse(TOMATO, 20_000, seed=11))
    losses = frame["total_loss"]
    assert losses.quantile(0.01) < 0.07, "no near-clean shipments in the training set"
    assert losses.quantile(0.95) > 0.35, "no severe-loss shipments in the training set"
    assert losses.min() > 0.0, "five handling stages cannot be free"
    assert 0.0 < summarise(frame)["total_pct"] < 100.0
