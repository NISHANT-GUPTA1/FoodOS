"""RECOVER — channel ranking, gates, and the honesty rules."""

from __future__ import annotations

import pytest

from foodos.engine import queries, rescue
from foodos.engine.optimiser import rank
from foodos.engine.planner import build_batch_decisions, build_ledger
from foodos.engine.risk import BatchRisk
from foodos.schema.enums import ChannelType


def _risk(**overrides) -> BatchRisk:
    defaults = dict(
        batch_id=1, product_id=1, label="Spinach", category="leafy_green", uom="kg",
        qty_on_hand=20.0, qty_kg=20.0, rsl_days=1.2, rsl_explanation="",
        expected_consumption=8.0, qty_at_risk=12.0, qty_at_risk_kg=12.0,
        waste_probability=0.71, value_at_risk=480.0,
        unit_cost=40.0, unit_price=0.0, intake_grade=0.92,
    )
    defaults.update(overrides)
    return BatchRisk(**defaults)


def test_channels_are_ranked_and_do_nothing_is_included(session, ctx):
    channels = queries.channels(session, ctx.site_id)
    actions = rescue.build_actions(_risk(), channels, ctx)
    assert any(a.is_baseline for a in actions)

    ranked = rank(actions, ctx)
    assert ranked.ranked, "at least one channel should be feasible"
    assert ranked.best.value > (ranked.baseline.value if ranked.baseline else 0)


def test_a_channel_needing_more_life_than_the_batch_has_is_excluded(session, ctx):
    channels = queries.channels(session, ctx.site_id)
    ranked = rank(rescue.build_actions(_risk(rsl_days=0.3), channels, ctx), ctx)
    assert ranked.excluded
    for scored in ranked.excluded:
        assert scored.exclusion_reason


def test_donation_eligibility_rule_is_applied_with_its_reason(session, ctx):
    channels = [
        c for c in queries.channels(session, ctx.site_id)
        if c.type == ChannelType.DONATION
    ]
    assert channels, "fixture must contain a donation channel"
    action = rescue.channel_action(channels[0], _risk(intake_grade=0.5), ctx)
    assert action.blocked_reason is not None
    assert "intake grade" in action.blocked_reason


def test_compost_and_feed_do_not_count_as_food_saved(session, ctx):
    channels = queries.channels(session, ctx.site_id)
    for channel in channels:
        action = rescue.channel_action(channel, _risk(), ctx)
        if channel.type in (ChannelType.COMPOST, ChannelType.ANIMAL_FEED):
            assert action.kg_food_saved == 0.0, channel.name
        elif channel.type == ChannelType.B2B_TRANSFER:
            assert action.kg_food_saved > 0, channel.name


def test_donation_earns_social_value_and_no_cash(session, ctx):
    channels = [
        c for c in queries.channels(session, ctx.site_id)
        if c.type == ChannelType.DONATION
    ]
    action = rescue.channel_action(channels[0], _risk(rsl_days=2.0), ctx)
    assert action.recovered_value == pytest.approx(0.0)
    assert action.social_value > 0


def test_seeded_kitchen_produces_at_risk_decisions(session, ctx):
    ledger = build_ledger(session, ctx)
    assert ledger, "the fixture should hold open batches"
    assert any(r.severity in ("critical", "high") for r in ledger)

    decisions = build_batch_decisions(session, ctx)
    assert decisions
    top = decisions[0]
    assert top.ranked.best is not None
    assert top.ranked.uplift() > 0


def test_the_spinach_excursion_shows_up_in_the_ledger(session, ctx):
    ledger = build_ledger(session, ctx)
    spinach = next(r for r in ledger if r.label == "Spinach")
    assert spinach.rsl_days < 3.0, "the planted dock excursion should bite"
    assert "31 C" in spinach.rsl_explanation
