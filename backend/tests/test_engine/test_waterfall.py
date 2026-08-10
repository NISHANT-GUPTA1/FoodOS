"""Cascading-waterfall tiers, and the AGMARKNET price reference.

The load-bearing assertion in this file is the last one: the tier is a label
and the objective function still decides the order. If a future change makes
the ladder gate the ranking, that test goes red — which is the point.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from foodos.engine import queries, rescue, waterfall
from foodos.engine.optimiser import rank
from foodos.engine.risk import BatchRisk
from foodos.ingest import agmarknet
from foodos.schema.enums import ActionType


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


# ------------------------------------------------------------------- tiers


@pytest.mark.parametrize(
    "rsl_days, expected",
    [
        (5.0, "TIER_0_PRIMARY_FRESH"),      # 120 h
        (2.01, "TIER_0_PRIMARY_FRESH"),     # just over the 48 h line
        (1.5, "TIER_1_B2B_KITCHENS"),       # 36 h
        (0.8, "TIER_2_PROCESSING"),         # 19.2 h
        (0.3, "TIER_3_HUMANITARIAN"),       # 7.2 h
        (0.15, "TIER_4_ANIMAL_FEED"),       # 3.6 h
        (0.05, "TIER_5_BIOREFINERY"),       # 1.2 h
        (0.0, "TIER_5_BIOREFINERY"),
    ],
)
def test_the_ladder_reproduces_the_blueprint_hour_bands(rsl_days, expected):
    assert waterfall.tier_of_rsl(rsl_days).code == expected


def test_every_recover_exit_has_exactly_one_tier():
    recover = {
        ActionType.STAFF_MEAL, ActionType.MARKDOWN, ActionType.DEEP_MARKDOWN,
        ActionType.B2B_TRANSFER, ActionType.DONATE, ActionType.PROCESS,
        ActionType.ANIMAL_FEED, ActionType.COMPOST,
    }
    for action_type in recover:
        assert waterfall.tier_of_action(action_type) is not None, action_type


def test_the_baseline_and_prevent_quantities_are_not_diversions():
    assert waterfall.tier_of_action(ActionType.DO_NOTHING) is None
    assert waterfall.tier_of_action(ActionType.SET_PREP_QTY) is None


def test_the_tier_is_a_label_and_the_objective_function_still_ranks(session, ctx):
    """Spinach at 19 h sits in the ladder's Tier 2 processing band, but a
    kitchen 400 m away recovers more than a puree unit 8 km away. The engine
    must pick the money, not the band."""
    channels = queries.channels(session, ctx.site_id)
    risk = _risk(rsl_days=0.8)
    ranked = rank(rescue.build_actions(risk, channels, ctx), ctx)

    assert waterfall.tier_of_rsl(risk.rsl_days).code == "TIER_2_PROCESSING"
    best = waterfall.tier_of_action(ranked.best.action.action_type)
    assert best.rank < 2, "value beat the ladder, which is the whole design"

    # And the order really is by score, not by tier rank.
    scores = [s.value for s in ranked.ranked]
    assert scores == sorted(scores, reverse=True)


# --------------------------------------------------------------- agmarknet


def test_quintal_prices_are_converted_to_kilograms(tmp_path: Path, session):
    (tmp_path / agmarknet.FILENAME).write_text(
        "State,District,Market,Commodity,Variety,Grade,"
        "Arrival_Date,Min_Price,Max_Price,Modal_Price\n"
        "Karnataka,Kolar,Kolar,Tomato,Local,FAQ,10/02/2026,1530,2120,1800\n",
        encoding="utf-8",
    )
    report = agmarknet.load(session, tmp_path)
    assert report["loaded"] == 1

    ref = agmarknet.latest_for(session, "Tomato", date(2026, 2, 12))
    assert ref["modal_price_per_kg"] == pytest.approx(18.0)
    assert ref["days_stale"] == 2


def test_a_missing_file_is_not_an_error(tmp_path: Path, session):
    assert agmarknet.load(session, tmp_path) == {"loaded": 0, "source": None}


def test_commodity_names_map_across_the_two_vocabularies():
    assert agmarknet.commodity_for("Coriander leaves") == "Coriander(Leaves)"
    assert agmarknet.commodity_for("Green peas") == "Green Peas"
    assert agmarknet.commodity_for("Curry leaves") == "Curry Leaves"
    assert agmarknet.commodity_for("French beans") == "French Beans (Frasbean)"
    # Not a mandi commodity — no reference is the right answer.
    assert agmarknet.commodity_for("Chicken Biryani") is None
