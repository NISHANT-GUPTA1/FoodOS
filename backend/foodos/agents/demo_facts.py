"""The three planted pathologies, as fact sets.

These are the numbers the demo turns on. They are agreed with Person A at H0-3 and written
down here so that the deck, the demo script and the agent layer cannot drift apart — and
so the agents are runnable end to end before the engine exists.

Every figure traces to backend/foodos/content/. The derivations are in docs/pathologies.md.
When Person A's generator is live, these are replaced by the API builders in runner.py and
the numbers should land within a rounding of these. If they do not, one of the two is wrong
and we want to find that out in rehearsal, not on stage.

Owner: Person D.
"""

from __future__ import annotations

from .facts import (
    UNIT_DAYS,
    UNIT_INR,
    UNIT_KG,
    UNIT_PCT,
    UNIT_PORTIONS,
    UNIT_TEXT,
    Fact,
    FactSet,
)


def today_facts() -> FactSet:
    """Kitchen-level KPIs. The three numbers on the Today screen."""
    return FactSet(
        [
            Fact("kg_at_risk", 47.2, UNIT_KG, "kilograms at risk today", source="engine:/api/today"),
            Fact("value_at_risk", 18400, UNIT_INR, "value at risk today", source="engine:/api/today"),
            Fact("preventable_share", 62, UNIT_PCT, "share of today's risk that was preventable", source="engine:/api/today"),
        ]
    )


def diagnostician_facts() -> FactSet:
    """Pathology 1 — chronic over-production of Gobi Manchurian on soft weekdays.

    Attribution of today's at-risk value. Shares sum to a hundred; the Diagnostician names
    the top one and the mechanism behind it.
    """
    return FactSet(
        [
            Fact("top_contributor_name", "Plan drift", UNIT_TEXT, "largest contributor", source="engine:/api/why"),
            Fact("top_contributor_share", 38, UNIT_PCT, "its share of value at risk", source="engine:/api/why"),
            Fact("second_contributor_name", "Chiller temperature", UNIT_TEXT, "second contributor", source="engine:/api/why"),
            Fact("second_contributor_share", 26, UNIT_PCT, "its share of value at risk", source="engine:/api/why"),
            Fact("worst_dish_name", "Gobi Manchurian", UNIT_TEXT, "dish carrying the most plan drift", source="engine:/api/why"),
            Fact("planned_portions", 80, UNIT_PORTIONS, "portions the prep sheet called for", source="engine:/api/plan"),
            Fact("recommended_portions", 63, UNIT_PORTIONS, "portions the optimiser recommends", source="engine:/api/plan"),
            Fact("demand_change_pct", 14, UNIT_PCT, "fall in weekday demand since the forecast was set",
                 source="engine:/api/why", direction="down"),
            Fact("value_at_risk", 18400, UNIT_INR, "value at risk today", source="engine:/api/today"),
            Fact("zone_name", "Under-counter chiller", UNIT_TEXT, "storage zone involved", source="engine:/api/ledger"),
        ]
    )


def planner_facts() -> FactSet:
    """Pathology 2 — paneer decaying fast in a warm under-counter chiller.

    4.4 kg of cubed paneer in COLD_2 at 9.2 degC. Against a 4 degC reference and a Q10 of
    3.0 for fresh dairy, its five-day base life collapses to well under a day once the cut
    penalty applies. The optimiser's answer is a Paneer Butter Masala special sized to what
    the forecast says will actually sell.
    """
    return FactSet(
        [
            Fact("batch_id", "B-1042", UNIT_TEXT, "batch identifier", source="engine:/api/ledger"),
            Fact("batch_ingredient_name", "Paneer", UNIT_TEXT, "ingredient at risk", source="engine:/api/ledger"),
            Fact("batch_zone_name", "Under-counter chiller", UNIT_TEXT, "where it is stored", source="engine:/api/ledger"),
            Fact("batch_qty_kg", 4.4, UNIT_KG, "quantity on hand", precision=1, source="engine:/api/ledger"),
            Fact("batch_rsl_days", 0.7, UNIT_DAYS, "remaining shelf life", precision=1, source="model:rsl"),
            Fact("batch_value_inr", 1496, UNIT_INR, "value of the batch at cost", source="engine:/api/ledger"),
            Fact("special_dish_name", "Paneer Butter Masala", UNIT_TEXT, "dish the optimiser selected", source="engine:/api/rescue"),
            Fact("special_portions", 36, UNIT_PORTIONS, "portions the batch covers at forecast sell-through", source="engine:/api/rescue"),
            Fact("special_value_inr", 6680, UNIT_INR, "contribution recovered by running the special", source="engine:/api/rescue"),
            Fact("station_name", "Gravy", UNIT_TEXT, "prep station that owns the work", source="content:recipes"),
            Fact("rezone_gain_days", 1.1, UNIT_DAYS, "life bought by moving it to the walk-in", precision=1, source="engine:/api/rescue"),
        ]
    )


def communicator_facts() -> FactSet:
    """Pathology 3 — Sunday over-order of boneless chicken, best recovered by transfer.

    9.6 kg raw, valued at cost. Transfer to a sister outlet recovers ninety per cent of that
    after transport and handling, which beats every other eligible channel. The message has
    to arrive before the collection window closes, which is why an agent writes it and not a
    person who is currently plating.
    """
    return FactSet(
        [
            Fact("batch_id", "B-1057", UNIT_TEXT, "batch identifier", source="engine:/api/ledger"),
            Fact("outlet_name", "Indiranagar", UNIT_TEXT, "receiving outlet", source="engine:/api/rescue"),
            Fact("batch_ingredient_name", "Chicken Boneless", UNIT_TEXT, "ingredient being transferred", source="engine:/api/ledger"),
            Fact("batch_qty_kg", 9.6, UNIT_KG, "quantity to transfer", precision=1, source="engine:/api/ledger"),
            Fact("batch_rsl_days", 1.4, UNIT_DAYS, "remaining shelf life", precision=1, source="model:rsl"),
            Fact("transfer_value_inr", 2419, UNIT_INR, "value recovered by the transfer", source="engine:/api/rescue"),
            Fact("disposal_saving_inr", 2534, UNIT_INR, "advantage over disposal, including avoided disposal cost", source="engine:/api/rescue"),
            Fact("pickup_by", "6:30 pm", UNIT_TEXT, "collection deadline that keeps the cold chain intact", source="engine:/api/rescue"),
            Fact("channel_name", "Transfer to sister outlet", UNIT_TEXT, "channel the optimiser ranked first", source="engine:/api/rescue"),
        ]
    )


#: What the Rescue screen shows greyed out for batch B-1057, and why. Excluded options are
#: rendered with the reason attached — never dropped.
EXCLUDED_CHANNELS_B1057 = [
    {"channel": "app_flash_deal", "reason_code": "state_not_accepted",
     "reason": "This channel does not accept stock in this state", "detail": "batch is raw, channel takes cooked or prepped"},
    {"channel": "ngo_donation", "reason_code": "day_unavailable",
     "reason": "This channel does not operate today", "detail": "collections run Monday, Wednesday and Friday"},
    {"channel": "animal_feed", "reason_code": "missing_requirement",
     "reason": "A required condition is not met", "detail": "poultry cannot go to a no-meat-contact stream"},
]


ALL = {
    "today": today_facts,
    "diagnostician": diagnostician_facts,
    "planner": planner_facts,
    "communicator": communicator_facts,
}
