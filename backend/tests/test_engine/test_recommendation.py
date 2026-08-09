"""Recommendation lifecycle and the acceptance-rate metric."""

from __future__ import annotations

from datetime import timedelta

import pytest

from foodos.engine import recommendation
from foodos.schema.enums import Horizon, RecommendationStatus


def test_generate_produces_both_horizons(session, ctx):
    rows = recommendation.generate(session, ctx, target=ctx.today + timedelta(days=1))
    assert rows, "the seeded kitchen should produce recommendations"
    horizons = {str(r.horizon) for r in rows}
    assert Horizon.PREVENT in horizons
    assert horizons & {Horizon.PRESERVE, Horizon.RECOVER}


def test_every_recommendation_carries_a_baseline_and_a_reason(session, ctx):
    rows = recommendation.generate(session, ctx)
    for rec in rows:
        assert rec.rationale_text, rec.subject_label
        assert rec.rationale_facts
        assert rec.recommended_value is not None
        assert rec.baseline_value is not None


def test_accept_and_override_move_the_status(session, ctx):
    rows = recommendation.generate(session, ctx)
    session.flush()

    accepted = recommendation.accept(session, rows[0].id)
    assert accepted.status == RecommendationStatus.ACCEPTED

    overridden = recommendation.override(
        session, rows[1].id, "Friday footfall is always higher", value=70.0
    )
    assert overridden.status == RecommendationStatus.OVERRIDDEN
    assert overridden.override_reason
    assert overridden.override_value == 70.0


def test_acceptance_rate_counts_only_decided_recommendations(session, ctx):
    rows = recommendation.generate(session, ctx)
    session.flush()
    recommendation.accept(session, rows[0].id)
    recommendation.accept(session, rows[1].id)
    recommendation.override(session, rows[2].id, "chef disagrees")
    session.flush()

    stats = recommendation.acceptance_rate(session, ctx.site_id)
    assert stats["decided"] == 3
    assert stats["accepted"] == 2
    assert stats["acceptance_rate"] == pytest.approx(2 / 3, abs=1e-4)


def test_outcome_enables_realised_vs_projected(session, ctx):
    rows = recommendation.generate(session, ctx)
    session.flush()
    rec = rows[0]
    recommendation.record_outcome(
        session, rec.id, actual_value=rec.recommended_value,
        actual_saving_kg=rec.expected_saving_kg * 0.8,
        actual_saving_money=rec.expected_saving_money * 0.8,
    )
    session.flush()
    report = recommendation.realised_vs_projected(session, ctx.site_id)
    assert report["projected_money"] > 0
    assert report["realisation_rate"] is not None


def test_the_friday_biryani_fault_is_found(session, ctx):
    """The fixture plants a ~34% Friday over-prep. The engine must find it."""
    friday = ctx.today + timedelta(days=1)
    assert friday.weekday() == 4, "the demo clock should sit the day before Friday"

    rows = recommendation.generate(session, ctx, target=friday)
    biryani = next(
        (r for r in rows if "Biryani" in r.subject_label and r.horizon == Horizon.PREVENT),
        None,
    )
    assert biryani is not None, "the planted fault should surface as a recommendation"
    assert biryani.recommended_value < biryani.baseline_value
    assert biryani.expected_saving_money > 0
