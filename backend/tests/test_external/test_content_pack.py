"""The content pack — the keys A and B were promised, and the numbers that must not drift.

Contract 3 names the keys each content file must contain. A missing key does not
crash at import; it crashes at hour 27 inside a request, on a laptop that is
plugged into a projector. These tests move that failure to the commit that
causes it.

The value assertions are deliberately loose bands, not equalities. This file is
not a copy of the constants — a test that re-states every number tells you only
that somebody edited two files, and it makes the content pack impossible to tune.
It asserts the things that are *wrong* rather than merely different: a Q10 that
is not a Q10, a price that is per quintal, a questionnaire question that changes
no feature.
"""

from __future__ import annotations

import pytest

from foodos import content
from foodos.agents.facts import format_indian
from foodos.external.agmarknet import COMMODITY_ALIASES


# ------------------------------------------------------------------ commodities
def test_tomato_carries_every_key_contract_3_promised():
    tomato = content.commodity("tomato")
    for key in (
        "base_shelf_life_hours",
        "ref_temp_c",
        "q10",
        "respiration_rate_mg_co2_per_kg_h",
        "q_crit",
        "nabcons_farm_loss_pct",
        "nabcons_market_loss_pct",
    ):
        assert key in tomato, f"{key} is in Contract 3 and A reads it"


def test_the_nabcons_baselines_are_the_published_figures():
    """The one calibration the cut order says must never be cut.

    8.37% farm and 3.25% market are NABCONS 2022 for tomato. They are the entire
    credibility of the loss figure, so they are pinned exactly rather than to a
    band — if somebody tunes these to make a model fit, the model was wrong.
    """
    tomato = content.commodity("tomato")
    assert tomato["nabcons_farm_loss_pct"] == pytest.approx(8.37)
    assert tomato["nabcons_market_loss_pct"] == pytest.approx(3.25)


def test_the_two_nabcons_stages_are_not_quoted_as_one_number():
    """Farm and market are consecutive stages, not addends.

    Adding them is how the "30-40% of Indian produce is wasted" claim gets built,
    and a judge who knows the sector will catch it. The content pack says so
    explicitly so the deck cannot quietly do it.
    """
    tomato = content.commodity("tomato")
    assert "not addends" in tomato["nabcons_note"].lower().replace("addend", "addend")


def test_shelf_life_is_in_hours_and_the_reference_temperature_is_not_a_chiller():
    """Tomato is not a leafy green. Below 10 degC it suffers chilling injury.

    A ref_temp_c of 4 would silently tell the optimiser that colder is always
    better, and it would recommend freezing the fruit to death.
    """
    tomato = content.commodity("tomato")
    assert 120.0 < tomato["base_shelf_life_hours"] < 600.0, "that is days, not hours"
    assert 10.0 <= tomato["ref_temp_c"] <= 16.0
    assert tomato["ref_temp_c"] > tomato["chilling_injury_below_c"]


def test_q10_is_a_plausible_q10():
    q10 = content.commodity("tomato")["q10"]
    assert 1.5 < q10 < 3.5, "outside this band it is not a Q10, it is a typo"


def test_maturity_and_damage_factors_only_shorten_life():
    """Both are multipliers on remaining life. A factor above 1 for damage would
    mean bruising a tomato makes it last longer."""
    tomato = content.commodity("tomato")
    assert all(0.0 < v <= 1.0 for v in tomato["damage_factors"].values())
    assert tomato["damage_factors"]["none"] == 1.0
    maturity = tomato["maturity_factors"]
    assert maturity["mature_green"] > maturity["turning"] > maturity["red_ripe"]


def test_an_unknown_commodity_raises_rather_than_returning_tomato():
    """Only tomato is in scope. A silent fallback would let a second commodity
    look like it works right up until its numbers were questioned."""
    with pytest.raises(content.ContentError):
        content.commodity("mango")


def test_the_agmarknet_key_resolves_through_the_loader():
    assert content.commodity("tomato")["agmarknet_key"] in COMMODITY_ALIASES.values()


# --------------------------------------------------------------------- mandis
def test_every_mandi_carries_the_four_keys_b_routes_on():
    for mandi_id, row in content.mandis().items():
        for key in (
            "distance_km",
            "typical_transit_hours",
            "daily_absorption_kg",
            "agmarknet_key",
        ):
            assert key in row, f"{mandi_id} is missing {key}"
        assert row["daily_absorption_kg"] > 0


def test_absorption_can_actually_bind_on_a_demo_sized_consignment():
    """If every mandi absorbs a hundred times the load, the split never happens.

    The absorption cap is what turns "always Delhi" into "6 t Delhi, 4 t Jaipur".
    A cap that can never bind is a field nobody needed to fill in.
    """
    absorptions = [row["daily_absorption_kg"] for row in content.mandis().values()]
    assert min(absorptions) < 10_000 * 20, "no destination is remotely constrained"


def test_transit_hours_and_distance_agree_on_a_believable_speed():
    for mandi_id, row in content.mandis().items():
        if row["distance_km"] < 100:
            continue  # short local runs are dominated by loading, not driving
        speed = row["distance_km"] / row["typical_transit_hours"]
        assert 35.0 < speed < 75.0, f"{mandi_id} implies {speed:.0f} km/h"


# ------------------------------------------------------------------ packaging
def test_packaging_carries_the_three_keys_and_they_point_the_right_way():
    packs = content.packaging_types()
    for name, row in packs.items():
        for key in ("thermal_retention_factor", "crush_protection", "cost_per_kg"):
            assert key in row, f"{name} is missing {key}"
        assert 0.0 <= row["crush_protection"] <= 1.0
        assert row["cost_per_kg"] >= 0.0

    # A ventilated crate must shed heat better and protect better than a sack, or
    # the engine's cheapest and most useful recommendation inverts.
    crate = packs["ventilated_plastic_crate"]
    sack = packs["jute_bag"]
    assert crate["thermal_retention_factor"] < sack["thermal_retention_factor"]
    assert crate["crush_protection"] > sack["crush_protection"]


def test_reusable_packaging_is_costed_per_trip_not_at_purchase_price():
    """Charging a crate's full price to one consignment makes every reusable
    option look absurd. It is the most common way this comparison is got wrong."""
    crate = content.packaging_types()["ventilated_plastic_crate"]
    assert crate["cost_per_kg"] < 2.0
    assert crate["trips_before_replacement"] > 1


# ------------------------------------------------------------------- transport
def test_transport_modes_carry_the_four_keys():
    modes = content.transport_modes()
    for name in ("open_truck", "tarpaulin", "reefer"):
        row = modes[name]
        for key in (
            "cooling_factor",
            "vibration_penalty",
            "cost_per_km",
            "availability_hours",
        ):
            assert key in row, f"{name} is missing {key}"
        assert 0.0 <= row["cooling_factor"] <= 1.0


def test_a_reefer_costs_more_and_takes_longer_to_get():
    """The two constraints that let the engine decline a reefer.

    Without them it always says "use a reefer", which is a brochure rather than
    an optimiser, and it is wrong for a B+ field lot whose grade uplift will not
    cover the freight.
    """
    modes = content.transport_modes()
    assert modes["reefer"]["cost_per_km"] > modes["open_truck"]["cost_per_km"] * 1.4
    assert modes["reefer"]["availability_hours"] > modes["open_truck"]["availability_hours"] * 3


def test_the_reefer_setpoint_respects_chilling_injury():
    setpoint = content.transport_modes()["reefer"]["setpoint_c"]
    assert setpoint >= content.commodity("tomato")["chilling_injury_below_c"]


def test_a_split_is_costed_as_multi_drop_and_not_as_two_full_freight_bills():
    """Two 2,000 km trucks cost far more than one.

    A planner that costs a split as two full runs will reject every split; one
    that costs it as free will recommend splits that lose money in the field.
    Both constants exist so it can do neither.
    """
    doc = content.load("transport_modes.yaml")
    multi = doc["multi_drop"]
    assert multi["second_drop_charge_inr"] > 0
    assert multi["detour_km"]["delhi_apmc__jaipur_apmc"] > 0
    classes = doc["vehicle_classes"]
    # Smaller vehicle, cheaper trip, dearer per kilogram. That tension is the point.
    assert classes["lcv_4t"]["cost_per_km"] < classes["truck_10t"]["cost_per_km"]
    per_kg_small = classes["lcv_4t"]["cost_per_km"] / classes["lcv_4t"]["payload_kg"]
    per_kg_big = classes["truck_10t"]["cost_per_km"] / classes["truck_10t"]["payload_kg"]
    assert per_kg_small > per_kg_big


# --------------------------------------------------------------- questionnaire
def test_the_questionnaire_fits_inside_its_time_budget():
    """Under 12 questions, under 30 seconds, on a phone, with a truck waiting."""
    tree = content.questionnaire("tomato")
    assert len(tree["questions"]) <= 12
    assert tree["estimated_seconds"] <= 30


def test_every_question_writes_a_feature():
    """A question with no feature_key costs a farmer eight seconds and changes
    no number on any screen. There must never be one."""
    for question in content.questionnaire("tomato")["questions"]:
        assert question.get("feature_key"), f"{question['id']} writes nothing into fuse()"
        assert question.get("options"), f"{question['id']} has no answers"
        assert "default" in question, f"{question['id']} cannot be skipped"


def test_a_silent_form_still_produces_a_complete_feature_vector():
    """A batch that answers nothing must still score — degraded, never crashed.
    Same rule `fuse()` runs on, asserted on the content that feeds it."""
    tree = content.questionnaire("tomato")
    defaults = tree["defaults"]
    for question in tree["questions"]:
        assert question["feature_key"] in defaults, question["id"]


def test_the_branch_rules_the_spec_asked_for_are_actually_wired():
    """A midday harvest opens the sun-exposure follow-up; a reefer closes the
    packaging thermal question."""
    questions = {q["id"]: q for q in content.questionnaire("tomato")["questions"]}

    sun = questions["field_heat_hours"]["show_if"][0]
    assert sun["question"] == "harvest_window"
    assert "midday" in sun["in"]

    cover = questions["load_cover"]["show_if"][0]
    assert cover["question"] == "transport_mode"
    assert "reefer" not in cover["in"], "a sealed reefer has no load to cover"


@pytest.mark.parametrize(
    ("question_id", "content_lookup"),
    [
        ("maturity_stage", lambda: content.commodity("tomato")["maturity_factors"]),
        ("damage_level", lambda: content.commodity("tomato")["damage_factors"]),
        ("packaging_type", content.packaging_types),
        ("transport_mode", content.transport_modes),
    ],
)
def test_answer_values_resolve_against_the_constants_they_index(question_id, content_lookup):
    """An option value with no matching constant falls back silently and the
    answer stops moving any number. Cheap to introduce, invisible until stage."""
    question = next(
        q for q in content.questionnaire("tomato")["questions"] if q["id"] == question_id
    )
    known = set(content_lookup())
    for option in question["options"]:
        assert option["value"] in known, f"{question_id}: {option['value']} indexes nothing"


def test_the_demo_batch_can_be_reproduced_from_the_form():
    """T1024's answers live beside the tree so the demo script and the model
    meet in content rather than in a fixture."""
    tree = content.questionnaire("tomato")
    answers = tree["demo_answers"]["T1024"]
    assert set(answers) == set(tree["defaults"])
    assert answers["field_heat_hours_over_30c"] == pytest.approx(
        content.load("commodities.yaml")["calibration"]["t1024"]["inputs"][
            "field_heat_hours_over_30c"
        ]
    )


# -------------------------------------------------------------- agri channels
def test_the_agri_block_did_not_disturb_the_kitchen_channels():
    """`ingest/channels.py` reads `channels:`. If the agri rows had been appended
    there, an unmapped id would reach the ORM as an invalid enum and break
    `python -m foodos.ingest.seed` — the one command that must never break."""
    doc = content.load("channels.yaml")
    kitchen_ids = {row["id"] for row in doc["channels"]}
    agri_ids = {row["id"] for row in doc["agri_channels"]}
    assert kitchen_ids & agri_ids == set()
    assert "dine_in_special" in kitchen_ids  # the kitchen node, untouched


def test_every_agri_channel_names_the_engine_type_b_will_construct():
    from foodos.schema.enums import ChannelType

    valid = {c.value for c in ChannelType}
    for row in content.agri_channels():
        assert row["engine_channel_type"] in valid, row["id"]
        assert 0.0 <= row["recovery_factor"] <= 1.0


def test_the_do_nothing_counterfactual_is_present_and_always_eligible():
    """Abandoning the lot is what actually happens today. Every figure the demo
    claims is measured against it, so it must be scoreable, not rhetorical."""
    baseline = [row for row in content.agri_channels() if row.get("is_baseline")]
    assert len(baseline) == 1
    assert baseline[0]["recovery_factor"] == 0.0
    assert baseline[0]["min_residual_life_hours"] == 0


def test_a_donation_does_not_look_like_a_cash_sale():
    """Social value is credited through mu, never smuggled into the revenue term."""
    donation = next(r for r in content.agri_channels() if r["id"] == "agri_ngo_donation")
    assert donation["recovery_factor"] < 0.1
    assert donation["social_value_per_kg"] > 0


# ------------------------------------------------------------------ formatting
def test_the_deck_and_the_ui_agree_on_indian_digit_grouping():
    """Rs 1,22,260 — lakhs, not millions. Getting this wrong is a small thing
    that makes every screen look foreign to the audience it is aimed at."""
    assert format_indian(122260) == "1,22,260"
    assert format_indian(153760) == "1,53,760"
    assert format_indian(8400) == "8,400"
