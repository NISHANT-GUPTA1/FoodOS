"""The dataset plants three faults on purpose. These tests prove the engine
finds them, and that the models beat the baseline they must beat.

OWNER: Person A (Data & Models).

Run:  python -m pytest tests/ -v

If one of these fails, either the generator has drifted or a detector has
broken. Both are worth stopping for: a demo where the engine no longer finds
the planted fault is a demo with nothing to show.
"""

from __future__ import annotations

import pytest

from foodos.data import catalog as C
from foodos.models import attribution, backtest, forecast, loader, rsl


@pytest.fixture(scope="session")
def tables():
    return loader.load_all()


@pytest.fixture(scope="session")
def report(tables):
    return attribution.attribute(tables=tables)


# --------------------------------------------------------------------------
# The dataset itself
# --------------------------------------------------------------------------

def test_all_tables_present(tables):
    for name in loader.TABLES:
        assert not tables[name].empty, f"{name} is empty"


def test_ninety_days_of_history(tables):
    assert tables["sales"]["business_date"].nunique() == 90


def test_forty_ingredients_and_fifteen_menu_lines(tables):
    products = tables["products"]
    assert int((products["is_dish"] == 0).sum()) == 40
    assert int((products["is_dish"] == 1).sum()) == 15      # 14 dishes + sides
    assert int((products["is_produce"] == 1).sum()) == 22


def test_mass_balance_holds(tables):
    """Nothing may be consumed or wasted that was never received.

    This is the invariant that broke silently once already: buried batches were
    being skipped rather than reordered, so the kitchen produced dishes without
    drawing the ingredients, and the yield benchmark quietly became nonsense.
    """
    events = tables["inventory_events"]
    received = events[events["type"] == "receive"].groupby("product_id")["qty"].sum()
    used = events[events["type"] != "receive"].groupby("product_id")["qty"].sum()
    for pid, out_qty in used.items():
        assert out_qty <= received.get(pid, 0.0) + 1e-6, f"{pid} consumed more than received"


def test_waste_is_a_plausible_share_of_purchases(tables, report):
    receipts = tables["goods_receipt"]
    purchases = float((receipts["qty_received"] * receipts["unit_cost"]).sum())
    share = report["total_value"] / purchases * 100
    assert 4.0 < share < 10.0, f"waste is {share:.1f}% of purchases"


def test_produce_dominates_wasted_weight(report):
    """The track is fruit and vegetables, so they must dominate the weight."""
    assert report["produce_share_kg_pct"] > 55.0


def test_all_five_causes_are_present(report):
    for cause in attribution.CAUSES:
        assert report["by_cause"][cause] > 0, f"no {cause} in the waste log"
    assert report["by_cause"]["overproduction"] > 40.0


# --------------------------------------------------------------------------
# PLANTED FAULT 1 — Friday chicken biryani over-production
# --------------------------------------------------------------------------

def test_fault_1_friday_biryani_is_detected(report):
    dishes = {d["product_id"]: d for d in report["detectors"]["overproduction"]["by_dish"]}
    biryani = dishes["DSH_CHBIRYANI"]

    assert biryani["worst_dow_name"] == "Fri", (
        f"worst biryani day detected as {biryani['worst_dow_name']}, expected Fri")
    assert biryani["worst_dow_over_pct"] > 25.0
    # and Friday must stand clearly above the dish's own baseline
    assert biryani["worst_dow_over_pct"] > biryani["over_pct"] * 1.4


def test_fault_1_biryani_is_a_top_overproduction_cost(report):
    top3 = [d["product_id"] for d in report["detectors"]["overproduction"]["by_dish"][:3]]
    assert "DSH_CHBIRYANI" in top3


# --------------------------------------------------------------------------
# PLANTED FAULT 2 — cauliflower yield 0.51 against a 0.58 standard
# --------------------------------------------------------------------------

def test_fault_2_cauliflower_yield_gap_is_detected(report):
    trim = {t["product_id"]: t for t in report["detectors"]["trim_yield"]}
    assert "ING_CAULI" in trim, "cauliflower yield gap not detected"

    cauli = trim["ING_CAULI"]
    assert cauli["actual_yield"] == pytest.approx(0.51, abs=0.02)
    assert cauli["standard_yield"] == pytest.approx(0.58, abs=0.001)
    assert cauli["avoidable_kg"] > 150


def test_fault_2_cauliflower_is_the_biggest_trim_offender(report):
    assert report["detectors"]["trim_yield"][0]["product_id"] == "ING_CAULI"


def test_no_false_yield_alarms(report):
    """Every ingredient flagged must genuinely be below its standard.

    Guards the failure this detector already had once: when salad and raita
    usage had no BOM behind it, gross consumption had no net to compare against
    and the engine confidently reported an 88% lemon loss that did not exist.
    """
    for t in report["detectors"]["trim_yield"]:
        assert t["gap_pts"] >= attribution.MIN_YIELD_GAP_PTS
        assert t["actual_yield"] > 0.35, (
            f"{t['name']} yield {t['actual_yield']} is implausible — "
            "some usage is probably missing a recipe")


# --------------------------------------------------------------------------
# PLANTED FAULT 3 — the receiving-dock temperature excursion
# --------------------------------------------------------------------------

def test_fault_3_dock_excursion_shortens_life(tables):
    receipts = tables["goods_receipt"]
    excursions = receipts[receipts["dock_dwell_hours"] > 2.0]
    assert not excursions.empty, "no dock excursion in the dataset"
    assert set(excursions["product_id"]) == {C.DOCK_EXCURSION["product_id"]}


def test_fault_3_printed_date_overstates_true_life(tables):
    led = rsl.ledger(tables)
    spinach = led[led["product_id"] == "ING_SPINACH"]
    assert not spinach.empty, "no spinach open at demo time"

    worst = spinach.loc[spinach["life_overstated_days"].idxmax()]
    assert worst["life_overstated_days"] > 2.0, (
        "the excursion batch should look several days fresher than it is")
    assert worst["rsl_days_computed"] < 2.0
    assert worst["qty_remaining"] > 5.0, "too little left to be worth showing"


def test_rsl_falls_as_storage_gets_warmer():
    """Physics sanity: the same crate must die sooner in a warmer room."""
    profile = rsl.profile_for_category("hard_veg")     # 10 days, so all three survive
    batch = {"received_at": "2026-02-10", "intake_grade": 0.95,
             "dock_dwell_hours": 0.5, "state": "whole"}
    cold = rsl.compute_rsl(batch, 4.0, profile, as_of="2026-02-11")
    warm = rsl.compute_rsl(batch, 12.0, profile, as_of="2026-02-11")
    hot = rsl.compute_rsl(batch, 20.0, profile, as_of="2026-02-11")
    assert cold > warm > hot > 0

    # leafy produce left in the same warm room for a day is simply gone
    leafy = rsl.profile_for_category("leafy")
    assert rsl.compute_rsl(batch, 25.0, leafy, as_of="2026-02-11") == 0.0

    # cutting produce collapses what is left of its life
    cut = rsl.compute_rsl({**batch, "state": "cut"}, 4.0, profile, as_of="2026-02-11")
    assert cut < cold


def test_rsl_matches_the_simulation(tables):
    """The RSL engine must reproduce the generator's own kinetics.

    They are two implementations of one rate law. If they drift apart, every
    number on the Ledger screen stops tracing back to the data.
    """
    led = rsl.ledger(tables, as_of=C.DEMO_TODAY)
    diff = (led["rsl_days_computed"] - led["rsl_days"]).abs()
    assert diff.max() < 0.05, f"RSL engine diverges from the simulation by {diff.max():.3f} d"


# --------------------------------------------------------------------------
# Forecaster and backtest
# --------------------------------------------------------------------------

@pytest.fixture(scope="session")
def bt(tables):
    return backtest.run_backtest(tables=tables)


def test_forecaster_beats_seasonal_naive(bt):
    """A forecast that cannot beat same-weekday-last-week has no business
    changing a prep quantity."""
    acc = bt["accuracy"]
    assert acc["beats_baseline"]
    assert acc["pinball_improvement_pct"] > 15.0


def test_confidence_band_is_honest(bt):
    """A 10-90 band should contain roughly 80% of actuals. Well outside that
    range and the interval is a decoration rather than a measurement."""
    coverage = bt["accuracy"]["interval_coverage_pct"]
    assert 72.0 <= coverage <= 95.0, f"coverage {coverage}%"


def test_backtest_saves_money_and_food_on_held_out_days(bt):
    assert bt["saving_money"] > 0
    assert bt["saving_kg"] > 0
    assert bt["overproduction_cut_pct"] > 25.0


def test_backtest_never_trains_on_the_days_it_scores(bt):
    assert bt["train_end"] < bt["test_start"]
    assert bt["test_days"] == 30


def test_lambda_trades_margin_for_food(tables):
    """The sustainability dial must be a real trade-off, not free money:
    more lambda buys more kilos and eventually costs cash."""
    frontier = backtest.lambda_frontier(values=(0.0, 50.0, 150.0), tables=tables)
    kgs = [f["saving_kg_monthly"] for f in frontier]
    cash = [f["saving_money_monthly"] for f in frontier]
    assert kgs == sorted(kgs), "raising lambda must save more food"
    assert cash[-1] < cash[0], "raising lambda must eventually cost margin"


def test_plan_covers_every_batch_prepared_dish(tables):
    products = tables["products"]
    plannable = products[(products["is_dish"] == 1) & (products["plannable"] == 1)]
    assert len(plannable) == 11          # 14 dishes - 3 fired to order
    for pid in plannable["product_id"]:
        dist = forecast.predict_quantiles(product_id=pid, target_date=C.PLAN_DATE)
        assert dist["q10"] <= dist["q50"] <= dist["q90"], f"{pid} quantiles cross"
        assert dist["q50"] > 0
