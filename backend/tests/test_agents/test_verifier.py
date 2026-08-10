"""The Verifier blocks. This file is the proof.

Owner: Person D.
"""

from __future__ import annotations

from foodos.agents.demo_facts import planner_facts
from foodos.agents.facts import UNIT_INR, UNIT_KG, UNIT_PCT, UNIT_TEXT, Fact, FactSet
from foodos.agents.verifier import Verifier

GOOD_TEMPLATE = (
    "Run {{special_dish_name}} tonight — {{batch_qty_kg}} on hand covers "
    "{{special_portions}} and brings back {{special_value_inr}}."
)


def _rendered(facts: FactSet, template: str = GOOD_TEMPLATE) -> str:
    from foodos.agents.templates import render

    return render(template, facts)


# --- the happy path ----------------------------------------------------------

def test_a_faithful_output_passes(verifier):
    facts = planner_facts()
    result = verifier.check(
        agent="planner", template=GOOD_TEMPLATE, rendered=_rendered(facts), facts=facts
    )
    assert result.passed, result.explain()
    assert result.findings == []


def test_all_six_deterministic_checks_run(verifier):
    facts = planner_facts()
    result = verifier.check(
        agent="planner", template=GOOD_TEMPLATE, rendered=_rendered(facts), facts=facts
    )
    assert result.checks_run == [
        "malformed_output",
        "unknown_fact",
        "untraceable_number",
        "hallucinated_entity",
        "direction_mismatch",
        "ungrounded_output",
    ]


# --- C3, the one that matters ------------------------------------------------

def test_a_tampered_figure_is_blocked(verifier):
    """The headline failure: correct shape, wrong number."""
    facts = planner_facts()
    tampered = _rendered(facts).replace("₹6,680", "₹31,900")

    result = verifier.check(agent="planner", template=GOOD_TEMPLATE, rendered=tampered, facts=facts)

    assert result.blocked
    assert "untraceable_number" in result.blocking_codes
    assert "31,900" in result.explain()


def test_a_plausible_rounding_is_still_blocked(verifier):
    """'about 6,700' is not 6,680. Close is not traceable."""
    facts = planner_facts()
    rendered = _rendered(facts).replace("₹6,680", "₹6,700")
    result = verifier.check(agent="planner", template=GOOD_TEMPLATE, rendered=rendered, facts=facts)
    assert result.blocked


def test_a_unit_conversion_the_agent_did_itself_is_blocked(verifier):
    """4.4 kg restated as 4400 g is arithmetic, and arithmetic is not the agent's job."""
    facts = planner_facts()
    rendered = _rendered(facts).replace("4.4 kg", "4400 g")
    result = verifier.check(agent="planner", template=GOOD_TEMPLATE, rendered=rendered, facts=facts)
    assert result.blocked
    assert "untraceable_number" in result.blocking_codes


def test_each_bad_number_is_reported_once(verifier):
    facts = planner_facts()
    rendered = _rendered(facts).replace("₹6,680", "₹31,900") + " Again: ₹31,900."
    result = verifier.check(agent="planner", template=GOOD_TEMPLATE, rendered=rendered, facts=facts)
    assert len([f for f in result.findings if f.code == "untraceable_number"]) == 1


def test_digits_inside_a_text_fact_are_traceable(verifier):
    """Batch ids and pickup times carry digits and came from the engine like everything else."""
    facts = FactSet(
        [
            Fact("batch_id", "B-1042", UNIT_TEXT, "batch"),
            Fact("pickup_by", "6:30 pm", UNIT_TEXT, "deadline"),
        ]
    )
    template = "Batch {{batch_id}} must be collected by {{pickup_by}}."
    result = verifier.check(
        agent="communicator", template=template, rendered=_rendered(facts, template), facts=facts
    )
    assert result.passed, result.explain()


# --- the other checks --------------------------------------------------------

def test_an_invented_dish_is_blocked(verifier):
    facts = planner_facts()
    rendered = _rendered(facts).replace("Paneer Butter Masala", "Mutton Rogan Josh")
    result = verifier.check(agent="planner", template=GOOD_TEMPLATE, rendered=rendered, facts=facts)

    assert result.blocked
    assert "hallucinated_entity" in result.blocking_codes


def test_an_invented_dish_produces_one_finding_not_a_pile(verifier):
    facts = planner_facts()
    rendered = _rendered(facts).replace("Paneer Butter Masala", "Mutton Rogan Josh")
    result = verifier.check(agent="planner", template=GOOD_TEMPLATE, rendered=rendered, facts=facts)
    assert len([f for f in result.findings if f.code == "hallucinated_entity"]) == 1


def test_an_ingredient_named_inside_a_grounded_dish_is_fine(verifier):
    """'Paneer' appears inside the fact 'Paneer Butter Masala' and must not trip C4."""
    facts = planner_facts()
    result = verifier.check(
        agent="planner", template=GOOD_TEMPLATE, rendered=_rendered(facts), facts=facts
    )
    assert "hallucinated_entity" not in result.blocking_codes


def test_a_reversed_direction_is_blocked(verifier):
    facts = FactSet(
        [
            Fact("demand_change_pct", 14, UNIT_PCT, "fall in demand", direction="down"),
            Fact("contributor", "Plan drift", UNIT_TEXT, "contributor"),
        ]
    )
    template = "{{contributor}} — demand increased by {{demand_change_pct}} since Tuesday."
    result = verifier.check(
        agent="diagnostician", template=template, rendered=_rendered(facts, template), facts=facts
    )
    assert result.blocked
    assert "direction_mismatch" in result.blocking_codes


def test_the_correct_direction_passes(verifier):
    facts = FactSet(
        [
            Fact("demand_change_pct", 14, UNIT_PCT, "fall in demand", direction="down"),
            Fact("contributor", "Plan drift", UNIT_TEXT, "contributor"),
        ]
    )
    template = "{{contributor}} — demand fell by {{demand_change_pct}} since Tuesday."
    result = verifier.check(
        agent="diagnostician", template=template, rendered=_rendered(facts, template), facts=facts
    )
    assert result.passed, result.explain()


def test_prose_with_no_facts_at_all_is_blocked(verifier):
    facts = planner_facts()
    template = "Things look a bit tight in the chiller tonight, keep an eye on it."
    result = verifier.check(agent="planner", template=template, rendered=template, facts=facts)
    assert result.blocked
    assert "ungrounded_output" in result.blocking_codes


def test_a_reference_to_a_fact_that_does_not_exist_is_blocked(verifier):
    facts = planner_facts()
    template = "Recovering {{profit_next_quarter}} on {{special_dish_name}}."
    result = verifier.check(
        agent="planner", template=template, rendered="Recovering a lot on Paneer Butter Masala.",
        facts=facts,
    )
    assert result.blocked
    assert "unknown_fact" in result.blocking_codes


def test_an_unresolved_brace_is_blocked(verifier):
    facts = planner_facts()
    result = verifier.check(
        agent="planner",
        template=GOOD_TEMPLATE,
        rendered="Run {{special_dish_name}} tonight.",
        facts=facts,
    )
    assert result.blocked
    assert "malformed_output" in result.blocking_codes


# --- reporting ---------------------------------------------------------------

def test_explain_is_readable_enough_to_screenshot(verifier):
    facts = planner_facts()
    rendered = _rendered(facts).replace("₹6,680", "₹31,900")
    result = verifier.check(agent="planner", template=GOOD_TEMPLATE, rendered=rendered, facts=facts)
    text = result.explain()

    assert "BLOCKED" in text
    assert "untraceable_number" in text
    assert "special_value_inr=₹6,680" in text


def test_result_serialises_for_the_audit_log(verifier):
    facts = planner_facts()
    result = verifier.check(
        agent="planner", template=GOOD_TEMPLATE, rendered=_rendered(facts), facts=facts
    )
    payload = result.to_dict()
    assert payload["agent"] == "planner"
    assert payload["blocked"] is False
    assert isinstance(payload["findings"], list)


def test_verifier_works_without_a_content_pack():
    """C4 needs content; the other checks must still run if it is unavailable."""
    bare = Verifier(None)
    facts = planner_facts()
    rendered = _rendered(facts).replace("₹6,680", "₹31,900")
    result = bare.check(agent="planner", template=GOOD_TEMPLATE, rendered=rendered, facts=facts)
    assert result.blocked
