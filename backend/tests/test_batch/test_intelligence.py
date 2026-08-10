"""Re-scoring: does the number move, in the right direction, for the right reason."""

from __future__ import annotations

from datetime import timedelta

from foodos.engine import batch_identity as identity
from foodos.engine import batch_intelligence as intelligence
from foodos.schema.enums import BatchEventType, BatchLifecycle, MaturityStage

from .conftest import HARVEST


def _rescore(session, batch, hours, reason):
    return intelligence.rescore(
        session, batch, as_of=HARVEST + timedelta(hours=hours), reason=reason
    )


# ---------------------------------------------------------------- the basics


def test_registration_produces_a_full_profile(session, make_batch):
    batch = make_batch()
    identity.apply_event(session, batch, BatchEventType.ASSESSED, occurred_at=HARVEST)
    snap = _rescore(session, batch, 1, "registered")

    assert snap.sequence == 1
    assert 0 < snap.loss_pct < 100
    assert snap.rul_hours > 0
    assert snap.level in {"LOW", "MEDIUM", "HIGH"}
    assert batch.risk is not None and batch.risk.loss_pct == snap.loss_pct
    assert batch.grade  # a letter a mandi trades on


def test_scoring_promotes_an_assessed_batch_to_dispatchable(session, make_batch):
    batch = make_batch()
    identity.apply_event(session, batch, BatchEventType.ASSESSED, occurred_at=HARVEST)
    assert BatchLifecycle(batch.status) is BatchLifecycle.ASSESSED
    _rescore(session, batch, 1, "registered")
    assert BatchLifecycle(batch.status) is BatchLifecycle.READY_FOR_DISPATCH


def test_snapshots_accumulate_and_are_never_overwritten(session, in_transit):
    first = _rescore(session, in_transit, 5, "dispatched")
    identity.apply_event(
        session, in_transit, BatchEventType.DELAY,
        occurred_at=HARVEST + timedelta(hours=20), payload={"duration_hours": 6},
    )
    second = _rescore(session, in_transit, 20, "delay")

    assert [s.sequence for s in in_transit.snapshots] == [1, 2]
    # The first belief survives the second, which is the whole point.
    assert first.rul_hours != second.rul_hours
    assert in_transit.snapshots[0].rul_hours == first.rul_hours


def test_every_snapshot_carries_the_inputs_it_was_computed_from(session, in_transit):
    snap = _rescore(session, in_transit, 5, "dispatched")
    for key in ("transit_hours", "ambient_mean_c", "maturity_factor", "quantity_kg"):
        assert key in snap.inputs, key


# ---------------------------------------------------------------- events move it


def test_a_delay_immediately_costs_mass(session, in_transit):
    """Reported the moment it starts, before any of it has been served.

    Loss must react at once — six more hours of Deccan afternoon are now known
    to be coming. RUL need not drop yet, because no extra time has actually
    passed; that is what the next test covers.
    """
    before = _rescore(session, in_transit, 6, "dispatched")
    identity.apply_event(
        session, in_transit, BatchEventType.DELAY,
        occurred_at=HARVEST + timedelta(hours=6), payload={"duration_hours": 6},
    )
    after = _rescore(session, in_transit, 6, "delay")

    assert after.loss_pct > before.loss_pct, "a delay must cost mass"
    assert after.inputs["transit_hours"] == before.inputs["transit_hours"] + 6
    assert after.rul_hours <= before.rul_hours, "life is never handed back"


def test_a_delay_costs_life_once_it_has_been_served(session, in_transit):
    """The realistic reporting order: a six-hour hold-up is known six hours on."""
    before = _rescore(session, in_transit, 6, "dispatched")
    identity.apply_event(
        session, in_transit, BatchEventType.DELAY,
        occurred_at=HARVEST + timedelta(hours=12), payload={"duration_hours": 6},
    )
    after = _rescore(session, in_transit, 12, "delay")

    assert after.rul_hours < before.rul_hours, "a delay must cost life"
    assert after.loss_pct > before.loss_pct


def test_rul_never_rises_after_a_delay(session, in_transit):
    """The regression this whole `rul_at_dispatch` distinction exists for.

    A longer journey runs further into cool overnight hours, which *raises*
    life-at-dispatch. Reporting that raw would tell a manager the hold-up did
    the tomatoes good.
    """
    before = _rescore(session, in_transit, 10, "dispatched")
    identity.apply_event(
        session, in_transit, BatchEventType.DELAY,
        occurred_at=HARVEST + timedelta(hours=10), payload={"duration_hours": 12},
    )
    after = _rescore(session, in_transit, 10, "delay")
    assert after.rul_hours <= before.rul_hours


def test_life_burns_down_as_the_clock_runs(session, in_transit):
    early = _rescore(session, in_transit, 6, "dispatched")
    late = _rescore(session, in_transit, 18, "checkpoint")
    assert late.rul_hours < early.rul_hours
    # Nothing about the journey changed — only the time elapsed.
    assert late.inputs["transit_hours"] == early.inputs["transit_hours"]


def test_heat_exposure_is_time_weighted_not_a_replacement(session, in_transit):
    """Three hours at 41 C on a thirty-six hour haul is not a thirty-six hour
    journey at 41 C. Overwriting the mean would triple the thermal load."""
    before = _rescore(session, in_transit, 8, "dispatched")
    identity.apply_event(
        session, in_transit, BatchEventType.TEMPERATURE_EXPOSURE,
        occurred_at=HARVEST + timedelta(hours=8), payload={"temp_c": 41, "hours": 3},
    )
    after = _rescore(session, in_transit, 8, "heat")

    ambient_before = before.inputs["ambient_mean_c"]
    assert ambient_before < after.inputs["ambient_mean_c"] < 41
    assert after.loss_pct > before.loss_pct


def test_a_handoff_does_not_move_the_number(session, in_transit):
    """Re-scoring on a change of owner would make the figure move for a reason
    nobody could explain."""
    assert not BatchEventType.HANDOFF.rescores


def test_arrival_replaces_the_estimate_with_the_measurement(session, in_transit):
    identity.apply_event(
        session, in_transit, BatchEventType.ARRIVED,
        occurred_at=HARVEST + timedelta(hours=45),
    )
    snap = _rescore(session, in_transit, 45, "arrived")
    # Dispatched at +5 h, arrived at +45 h — a measured 40 hours, not the
    # declared 36.
    assert snap.inputs["transit_hours"] == 40.0


# ---------------------------------------------------------------- direction


def test_a_reefer_beats_an_open_truck_all_else_equal(session, make_batch):
    from foodos.schema.enums import TransportMode

    hot = make_batch(transport=TransportMode.OPEN_TRUCK)
    cold = make_batch(transport=TransportMode.REEFER)
    for b in (hot, cold):
        _rescore(session, b, 1, "test")
    assert cold.risk.loss_pct < hot.risk.loss_pct
    assert cold.risk.rul_hours > hot.risk.rul_hours


def test_riper_fruit_has_less_life(session, make_batch):
    green = make_batch(maturity=MaturityStage.LOW)
    ripe = make_batch(maturity=MaturityStage.HIGH)
    for b in (green, ripe):
        _rescore(session, b, 1, "test")
    assert ripe.risk.rul_hours < green.risk.rul_hours


def test_a_shorter_haul_loses_less(session, make_batch):
    near = make_batch(transit_hours=4.0)
    far = make_batch(transit_hours=40.0)
    for b in (near, far):
        _rescore(session, b, 1, "test")
    assert near.risk.loss_pct < far.risk.loss_pct


def test_maturity_buckets_stay_within_the_harvest_range(session):
    """Pink, light-red and red are stages a tomato *reaches*, not stages anyone
    loads onto a thirty-six hour truck. Mapping onto them scored an ordinary
    Kolar-Delhi haul at 51% loss."""
    factors = intelligence.MATURITY_FACTOR
    assert factors[MaturityStage.HIGH] >= 1.0
    assert factors[MaturityStage.LOW] > factors[MaturityStage.MEDIUM] > factors[MaturityStage.HIGH]


# ---------------------------------------------------------------- honesty


def test_defaults_come_from_the_calibrated_population(session):
    """An unanswered question means "looks like the population we measured" —
    not a pessimistic guess, and not an optimistic one."""
    base = intelligence.DEFAULT_BASE
    assert base["ambient_mean_c"] == 25.0  # annual mean, not peak summer
    assert base["transit_hours"] == 5.0    # lognormal median, not the tail


def test_a_fallback_row_carries_no_interval_and_no_model_run(session, make_batch):
    """An A outage degrades the number; it never 500s the screen — and it must
    never dress a heuristic up as a prediction."""
    batch = make_batch(commodity="unobtainium")
    snap = _rescore(session, batch, 1, "registered")

    assert snap.low is None and snap.high is None
    assert snap.model_run_id is None
    assert str(snap.confidence) == "LOW"
    assert snap.rul_hours > 0 and snap.loss_pct >= 0


def test_confidence_rises_with_evidence(session, make_batch):
    from foodos.schema.tables import BatchAssessment

    bare = make_batch()
    assert intelligence._confidence(bare) == intelligence.Confidence.LOW

    # A questionnaire alone is still LOW: it is self-reported, and the input it
    # is worst at — damage — is the one photos measure.
    answered = make_batch()
    answered.assessment = BatchAssessment(answers={"harvest_window": "morning"})
    session.flush()
    assert intelligence._confidence(answered) == intelligence.Confidence.LOW

    from foodos.schema.tables import WeatherExposure

    with_route = make_batch()
    with_route.assessment = BatchAssessment(answers={"harvest_window": "morning"})
    with_route.weather.append(WeatherExposure(hour_offset=0, temp_c=28.0))
    session.flush()
    assert intelligence._confidence(with_route) == intelligence.Confidence.MEDIUM


def test_photos_beat_the_questionnaire_on_damage(session, make_batch):
    from foodos.schema.tables import BatchAssessment

    batch = make_batch()
    batch.damage_factor = "high"
    batch.assessment = BatchAssessment(
        answers={}, photo_features={"visual_damage_fraction": 0.01}
    )
    session.flush()
    base = intelligence.build_base(batch)
    # The vision model measured; the farmer estimated.
    assert base["visual_damage_fraction"] == 0.01
