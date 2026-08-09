"""Backtest, the lambda frontier, and the two stub tracks."""

from __future__ import annotations

from foodos.engine import simulator, tracks
from foodos.engine.context import default_context


def test_backtest_evaluates_on_unseen_days(session, ctx):
    result = simulator.backtest(session, ctx, train_days=20, eval_days=10)
    assert result.days_evaluated > 0
    assert result.products_evaluated > 0
    # The train window must end before the eval window starts.
    assert result.train_end < result.eval_start
    assert result.actual_waste_kg > 0


def test_backtest_beats_the_habitual_production(session, ctx):
    """The fixture over-preps on purpose, so the newsvendor should save money."""
    result = simulator.backtest(session, ctx, train_days=30, eval_days=14)
    assert result.saving_kg > 0
    assert result.saving_money > 0


def test_backtest_reports_accuracy_against_a_naive_baseline(session, ctx):
    result = simulator.backtest(session, ctx, train_days=30, eval_days=14)
    assert result.median_abs_error >= 0
    assert result.naive_abs_error >= 0
    assert 0.0 <= result.interval_coverage <= 1.0


def test_frontier_is_monotone_in_lambda(session, ctx):
    points = simulator.frontier(session, ctx, lambdas=(0.0, 1.0, 3.0))
    quantities = [p["total_recommended_qty"] for p in points]
    assert quantities == sorted(quantities, reverse=True)
    wastes = [p["expected_waste_kg"] for p in points]
    assert wastes == sorted(wastes, reverse=True)


def test_retail_track_reuses_the_batch_decision_path(session, store):
    rows = tracks.retail_view(session, default_context(store.id))
    assert rows
    row = rows[0]
    assert row["best_action"]
    assert row["uplift_vs_doing_nothing"] >= 0
    assert 0.0 <= row["waste_probability"] <= 1.0


def test_production_track_rounds_to_feasible_lots(session, plant):
    rows = tracks.production_view(session, default_context(plant.id))
    assert rows
    for row in rows:
        assert row["recommended_qty"] % row["min_lot"] == 0
        assert row["recommended_qty"] > 0
        assert row["demand_low"] <= row["demand_high"]


def test_lot_size_scales_with_demand(session, plant):
    """A fixed lot across every SKU would put cakes on a 400-unit batch."""
    rows = {r["product"]: r for r in tracks.production_view(session, default_context(plant.id))}
    bread = next(r for k, r in rows.items() if "Bread" in k)
    cake = next(r for k, r in rows.items() if "Cake" in k)
    assert bread["min_lot"] > cake["min_lot"]
    assert cake["recommended_qty"] < bread["recommended_qty"]


def test_production_saving_is_scored_against_the_lot_actually_chosen(session, plant):
    """Rounding up to a feasible lot can erase the gain; the plan must say so."""
    for row in tracks.production_view(session, default_context(plant.id)):
        if row["recommended_qty"] >= row["habitual_qty"]:
            assert row["saving_money"] <= 0.01, row["product"]


def test_production_recommends_below_the_habitual_run(session, plant):
    rows = tracks.production_view(session, default_context(plant.id))
    assert any(r["unconstrained_optimum"] < r["habitual_qty"] for r in rows)
