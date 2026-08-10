"""Fact formatting and token rendering.

Owner: Person D.
"""

from __future__ import annotations

import pytest

from foodos.agents.facts import (
    UNIT_CO2E,
    UNIT_DAYS,
    UNIT_INR,
    UNIT_KG,
    UNIT_PCT,
    UNIT_PORTIONS,
    UNIT_TEXT,
    Fact,
    FactSet,
    format_indian,
)
from foodos.agents.templates import (
    MalformedTemplateError,
    UnknownTokenError,
    render,
    tokens_in,
    unknown_tokens,
)


# --- Indian digit grouping ---------------------------------------------------

@pytest.mark.parametrize(
    "value,expected",
    [
        (0, "0"),
        (999, "999"),
        (1000, "1,000"),
        (18400, "18,400"),
        (100000, "1,00,000"),
        (1234567, "12,34,567"),
        (-18400, "-18,400"),
    ],
)
def test_indian_grouping(value, expected):
    assert format_indian(value) == expected


def test_grouping_keeps_decimals():
    assert format_indian(18400.55, 2) == "18,400.55"


# --- fact display ------------------------------------------------------------

@pytest.mark.parametrize(
    "fact,expected",
    [
        (Fact("a", 18400, UNIT_INR), "₹18,400"),
        (Fact("b", 38, UNIT_PCT), "38%"),
        (Fact("c", 4.4, UNIT_KG), "4.4 kg"),
        (Fact("d", 0.7, UNIT_DAYS), "0.7 days"),
        (Fact("e", 36, UNIT_PORTIONS), "36 portions"),
        (Fact("f", 9.73, UNIT_CO2E, precision=2), "9.73 kg CO₂e"),
        (Fact("g", "Paneer", UNIT_TEXT), "Paneer"),
    ],
)
def test_fact_display(fact, expected):
    assert fact.display == expected


def test_numeric_unit_rejects_text():
    with pytest.raises(TypeError):
        Fact("bad", "lots", UNIT_KG)


def test_direction_must_be_valid():
    with pytest.raises(ValueError):
        Fact("bad", 1, UNIT_PCT, direction="sideways")


def test_numeric_forms_do_not_include_rounded_variants():
    """0.7 days must not make the string '1' look traceable."""
    forms = Fact("rsl", 0.7, UNIT_DAYS).numeric_forms()
    assert "0.7" in forms
    assert "1" not in forms


# --- fact sets ---------------------------------------------------------------

def test_duplicate_keys_are_rejected():
    facts = FactSet([Fact("a", 1, UNIT_PCT)])
    with pytest.raises(ValueError):
        facts.add(Fact("a", 2, UNIT_PCT))


def test_missing_reports_what_is_absent():
    facts = FactSet([Fact("a", 1, UNIT_PCT)])
    assert facts.missing(["a", "b", "c"]) == ["b", "c"]


def test_unknown_key_error_lists_what_is_available():
    facts = FactSet([Fact("batch_qty_kg", 4.4, UNIT_KG)])
    with pytest.raises(KeyError) as excinfo:
        facts["batch_qty"]
    assert "batch_qty_kg" in str(excinfo.value)


def test_catalogue_shows_keys_and_never_values():
    """The heart of the mechanism: the agent is shown names, not numbers."""
    facts = FactSet(
        [
            Fact("value_at_risk", 18400, UNIT_INR, "value at risk today"),
            Fact("top_contributor_name", "Plan drift", UNIT_TEXT, "largest contributor"),
        ]
    )
    catalogue = facts.catalogue()

    assert "{{value_at_risk}}" in catalogue
    assert "value at risk today" in catalogue
    assert "18400" not in catalogue
    assert "18,400" not in catalogue
    assert "₹18,400" not in catalogue
    # Text facts are named in the catalogue only by label, never by value either.
    assert "Plan drift" not in catalogue


# --- rendering ---------------------------------------------------------------

def test_tokens_in_preserves_order_without_duplicates():
    assert tokens_in("{{b}} then {{a}} then {{b}}") == ["b", "a"]


def test_render_substitutes_displays():
    facts = FactSet([Fact("qty", 4.4, UNIT_KG), Fact("value", 6680, UNIT_INR)])
    assert render("{{qty}} worth {{value}}", facts) == "4.4 kg worth ₹6,680"


def test_render_tolerates_whitespace_in_tokens():
    facts = FactSet([Fact("qty", 4.4, UNIT_KG)])
    assert render("{{ qty }}", facts) == "4.4 kg"


def test_unknown_token_raises_and_names_the_alternatives():
    facts = FactSet([Fact("qty_kg", 4.4, UNIT_KG)])
    with pytest.raises(UnknownTokenError) as excinfo:
        render("{{qty}}", facts)
    assert "qty" in excinfo.value.unknown
    assert "qty_kg" in str(excinfo.value)


def test_unknown_tokens_can_be_listed_without_raising():
    facts = FactSet([Fact("a", 1, UNIT_PCT)])
    assert unknown_tokens("{{a}} and {{b}}", facts) == ["b"]


def test_half_written_token_is_malformed_not_silently_shown():
    facts = FactSet([Fact("qty", 4.4, UNIT_KG)])
    with pytest.raises(MalformedTemplateError):
        render("{{qty}} and {{ not a token }}", facts)


def test_non_strict_render_leaves_unknown_tokens_alone():
    facts = FactSet([Fact("a", 1, UNIT_PCT)])
    assert render("{{a}} {{b}}", facts, strict=False) == "1% {{b}}"
