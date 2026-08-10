"""The objective function and the feasibility gate."""

from __future__ import annotations

import pytest

from foodos.engine.actions import Action, do_nothing
from foodos.engine.optimiser import feasibility, rank, score
from foodos.schema.enums import ActionType, Horizon


def _action(**overrides) -> Action:
    defaults = dict(
        action_type=ActionType.B2B_TRANSFER,
        horizon=Horizon.RECOVER,
        label="Nearby buyer",
        subject_type="batch",
        subject_id=1,
        qty=10.0,
        qty_kg=10.0,
        recovered_value=800.0,
        cost=150.0,
        loss_probability=0.1,
        value_at_risk=1000.0,
        kg_food_saved=9.0,
        co2e_saved_kg=22.5,
    )
    defaults.update(overrides)
    return Action(**defaults)


def test_every_term_appears_in_the_total(ctx):
    scored = score(_action(), ctx)
    t = scored.terms
    recomputed = (
        t["recovered_value"] - t["cost"] - t["expected_loss"]
        + t["sustainability"] + t["social"]
    )
    assert recomputed == pytest.approx(t["total"])
    assert scored.value == pytest.approx(t["total"])


def test_lambda_scales_only_the_sustainability_term(ctx):
    a = _action()
    low = score(a, ctx.with_lambda(0.0))
    high = score(a, ctx.with_lambda(2.0))
    assert low.terms["sustainability"] == 0.0
    assert high.terms["sustainability"] > 0
    assert high.value > low.value
    assert low.terms["recovered_value"] == high.terms["recovered_value"]


def test_rsl_gate_blocks_a_channel_that_cannot_arrive_in_time(ctx):
    a = _action(rsl_days=0.2, lead_time_hours=24.0)
    gate = feasibility(a, ctx)
    assert not gate.ok
    assert "remaining life" in gate.reason


def test_minimum_quantity_gate(ctx):
    a = _action(qty=2.0, min_qty_required=10.0)
    gate = feasibility(a, ctx)
    assert not gate.ok
    assert "minimum" in gate.reason


def test_builder_supplied_block_is_respected(ctx):
    a = _action(blocked_reason="does not accept dairy")
    assert not feasibility(a, ctx).ok
    assert score(a, ctx).exclusion_reason == "does not accept dairy"


def test_excluded_options_are_returned_never_hidden(ctx):
    actions = [
        _action(label="feasible"),
        _action(label="too slow", rsl_days=0.1, lead_time_hours=48.0),
        _action(label="too small", qty=1.0, min_qty_required=25.0),
    ]
    ranked = rank(actions, ctx)
    assert [s.action.label for s in ranked.ranked] == ["feasible"]
    assert len(ranked.excluded) == 2
    assert all(s.exclusion_reason for s in ranked.excluded)


def test_ranking_is_by_value_and_uplift_is_measured_against_doing_nothing(ctx):
    actions = [
        _action(label="poor", recovered_value=200.0),
        _action(label="best", recovered_value=900.0),
        do_nothing("batch", 1, "Spinach", value_at_risk=1000.0),
    ]
    ranked = rank(actions, ctx)
    assert ranked.best.action.label == "best"
    assert ranked.baseline is not None
    assert ranked.baseline.value == pytest.approx(-1000.0)
    assert ranked.uplift() > 0


def test_doing_nothing_is_always_scored(ctx):
    """'Rs 1,650 recovered against Rs 0' only means something if Rs 0 was scored."""
    baseline = do_nothing("batch", 1, "Paneer", value_at_risk=620.0)
    scored = score(baseline, ctx)
    assert scored.feasible
    assert scored.value == pytest.approx(-620.0)
