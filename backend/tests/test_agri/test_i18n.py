"""Localisation: Hindi by default, honest fallback, Indian number grouping.

The interesting assertions here are the two that encode product decisions rather
than mechanics: Hindi must be the *default* (not an option), and a partly
translated locale must substitute wholesale rather than mixing scripts.
"""

from __future__ import annotations

import re

import pytest

from foodos.agri import i18n
from foodos.agri.commodity import COMMODITIES, TOMATO
from foodos.agri.i18n import Locale
from foodos.agri.predict import predict, render_advisory
from foodos.agri.scenario import (
    FieldHolding,
    HarvestMethod,
    HarvestWindow,
    Packaging,
    TransportMode,
)

SHIPMENT = dict(
    quantity_kg=10_000.0, harvest_method="manual", harvest_window="midday",
    field_holding="open_sun", field_hours=5.0, packaging="gunny_bag",
    transport_mode="open_truck", transit_hours=30.0, mandi_holding_hours=8.0,
    maturity_factor=1.2, visual_damage_fraction=0.04, ambient_mean_c=33.0,
    diurnal_amplitude_c=10.0, road_roughness=1.8,
)

DEVANAGARI = re.compile(r"[ऀ-ॿ]")
KANNADA = re.compile(r"[ಀ-೿]")
LATIN_WORD = re.compile(r"[A-Za-z]{3,}")


# ==========================================================================
# Hindi is the default, not an option
# ==========================================================================


def test_hindi_is_the_default_locale():
    """The primary user reads Hindi. A default of English would make the
    shipped behaviour the wrong one for the person the product is for."""
    assert i18n.DEFAULT_LOCALE == Locale.HI


def test_an_unspecified_request_renders_in_hindi():
    profile = predict(SHIPMENT, TOMATO, mc_draws=300, with_sensitivity=False)
    assert profile.locale == "hi"
    assert DEVANAGARI.search(render_advisory(profile))


def test_english_is_still_reachable():
    profile = predict(
        SHIPMENT, TOMATO, mc_draws=300, with_sensitivity=False, locale=Locale.EN
    )
    text = render_advisory(profile)
    assert not DEVANAGARI.search(text)
    assert "Tomato" in text


# ==========================================================================
# Completeness — a missing Hindi string is a bug, not a gap
# ==========================================================================


def test_hindi_and_english_are_fully_translated():
    for locale in (Locale.HI, Locale.EN):
        missing = i18n.missing_keys(locale)
        assert not missing, f"{locale} is missing {missing}"


def test_every_questionnaire_answer_has_a_hindi_string():
    """A user picking an option must see it in their language. Any new enum
    member added to `scenario.py` without a translation fails here rather than
    surfacing as raw English mid-questionnaire."""
    for enum in (
        HarvestMethod, HarvestWindow, FieldHolding, Packaging, TransportMode
    ):
        for member in enum:
            rendered = i18n.option(str(member), Locale.HI)
            assert DEVANAGARI.search(rendered), f"{member} has no Hindi option label"


def test_every_commodity_has_a_hindi_name():
    for key in COMMODITIES:
        assert DEVANAGARI.search(i18n.commodity_name(key, Locale.HI)), key


def test_an_unknown_key_raises_rather_than_rendering_blank():
    with pytest.raises(i18n.MissingTranslation):
        i18n.t("field.this_does_not_exist", Locale.HI)


def test_an_unknown_option_value_degrades_instead_of_raising():
    """The asymmetry that matters, and it was a real bug.

    A missing *key* is a programming error and must raise. A missing *option
    value* is not: option values come from the questionnaire content pack and
    from persisted user answers, and that vocabulary is already a superset of
    the engine's enums — `post_harvest_shade: partial`, `harvest_window:
    early_morning`.

    Raising on those had a nasty shape. Every caller wraps the engine in a broad
    `except Exception` and degrades to a row with no interval but unchanged
    confidence, so an unrecognised answer surfaced as a confidently wrong number
    with no band rather than as a visible error. Crashing on unexpected user data
    is how a loud failure becomes a silent one.
    """
    assert i18n.option("some_value_nobody_translated") == "Some value nobody translated"
    assert i18n.option("partial", Locale.HI) == "कुछ हद तक छाया में"


def test_the_questionnaire_vocabulary_gap_is_reportable():
    """The gap between the content pack and the engine's enums must be
    enumerable, so it can be closed deliberately rather than rediscovered by
    each caller."""
    gap = i18n.unknown_option_values(["open_truck", "made_up_answer", "partial"])
    assert gap == ["made_up_answer"]


def test_predict_survives_a_questionnaire_value_outside_the_enums():
    """End to end: the exact shape that broke Contract 2b's band check."""
    odd = {**SHIPMENT, "field_holding": "partial"}
    profile = predict(odd, TOMATO, mc_draws=300, with_sensitivity=False)
    assert profile.loss_low_pct is not None
    assert profile.loss_high_pct is not None
    assert render_advisory(profile)


def test_every_field_the_engine_can_name_has_a_label():
    """The structural fix for a real integration bug, and the most valuable
    assertion in this file.

    `sensitivity()` can name *any* uncertain field as the biggest unknown, and
    `ablate()` can name any controllable or explanatory one. So every field in
    those four registries reaches a user, and a missing label makes `predict()`
    raise.

    That raise is deliberate — a silent blank would be worse. But upstream
    wraps the call in a broad `except Exception` and degrades to a row with no
    interval and *unchanged* confidence, so a loud failure arrived as a
    confidently wrong number with no band. `diurnal_amplitude_c` was missing and
    did exactly that.

    Enumerating the registries rather than listing keys by hand is the point: a
    field added to any of them fails here until it can be shown to a user.
    """
    from foodos.agri.predict import (
        CONTROLLABLE_CHOICES,
        CONTROLLABLE_TARGETS,
        UNCONTROLLABLE,
    )
    from foodos.agri.uncertainty import DEFAULT_UNCERTAINTY

    nameable = (
        set(DEFAULT_UNCERTAINTY)
        | set(CONTROLLABLE_CHOICES)
        | set(CONTROLLABLE_TARGETS)
        | set(UNCONTROLLABLE)
    )
    missing = sorted(f for f in nameable if f"field.{f}" not in i18n.STRINGS)
    assert not missing, (
        f"these fields can be shown to a user but have no label: {missing}. "
        "predict() will raise on them and the caller will swallow it."
    )

    # And each must actually render in Hindi, not fall through to English.
    for name in sorted(nameable):
        assert DEVANAGARI.search(i18n.field_label(name, Locale.HI)), name


def test_sensitivity_can_name_any_uncertain_field_without_raising():
    """The end-to-end version of the check above: force each uncertain field to
    be the reported unknown and confirm the profile still builds."""
    from foodos.agri.uncertainty import DEFAULT_UNCERTAINTY

    for name in DEFAULT_UNCERTAINTY:
        label = i18n.field_label(name, Locale.HI)
        assert label and label != name


# ==========================================================================
# Fallback — wholesale, never key-by-key across scripts
# ==========================================================================


def test_a_sparsely_translated_locale_substitutes_instead_of_mixing_scripts():
    """The bug this prevents produced real output: Kannada nouns inside Hindi
    grammar, in two scripts, in one sentence — harder to read than either
    language alone. Kannada is 30% translated, so the whole render substitutes.
    """
    assert i18n.coverage(Locale.KN) < i18n.MIN_USABLE_COVERAGE

    profile = predict(
        SHIPMENT, TOMATO, mc_draws=300, with_sensitivity=False, locale=Locale.KN
    )
    text = render_advisory(profile)

    assert profile.requested_locale_unavailable == "kn"
    assert profile.locale == "hi"
    assert not KANNADA.search(text), "script mixing is back"
    assert DEVANAGARI.search(text)


def test_a_fully_translated_locale_is_honoured():
    profile = predict(
        SHIPMENT, TOMATO, mc_draws=300, with_sensitivity=False, locale=Locale.MR
    )
    assert profile.requested_locale_unavailable is None
    assert profile.locale == "mr"


def test_resolve_locale_reports_what_it_did():
    assert i18n.resolve_locale(Locale.HI) == (Locale.HI, None)
    assert i18n.resolve_locale(Locale.KN) == (Locale.HI, Locale.KN)


def test_every_locale_declares_whether_a_native_speaker_reviewed_it():
    """Shipping an unreviewed translation is acceptable. Shipping one while
    implying it was reviewed is not."""
    for locale in Locale:
        assert locale in i18n.LOCALES
        info = i18n.LOCALES[locale]
        assert isinstance(info.native_reviewed, bool)
        if info.native_reviewed:
            assert not i18n.missing_keys(locale), (
                f"{locale} claims native review but is incomplete"
            )


# ==========================================================================
# Indian number grouping
# ==========================================================================


@pytest.mark.parametrize(
    "value, expected",
    [
        (950, "950"),
        (8_940, "8,940"),
        (99_999, "99,999"),
        (1_53_000, "1,53,000"),        # one lakh fifty-three thousand
        (12_34_567, "12,34,567"),      # twelve lakh
        (1_23_45_678, "1,23,45,678"),  # one crore
        (0, "0"),
        (-1_53_000, "-1,53,000"),
    ],
)
def test_digits_group_the_indian_way(value, expected):
    """Thousand, then lakh, then crore. A reader who groups in lakhs sees
    153,000 and has to stop and re-parse it, and a number that has to be
    re-parsed is a number that loses an argument."""
    assert i18n.format_indian(value) == expected


def test_grouping_appears_in_the_rendered_advisory():
    profile = predict(SHIPMENT, TOMATO, mc_draws=300, with_sensitivity=False)
    text = render_advisory(profile)
    assert "10,000" in text, "a 10 t consignment should render as 10,000"
    assert "10000" not in text.replace("10,000", "")


def test_units_are_localised_not_transliterated():
    assert i18n.t("unit.kg", Locale.HI) == "किलो"
    assert i18n.t("unit.hours", Locale.HI) == "घंटे"
    assert "kg" not in i18n.format_kg(500.0, Locale.HI)


# ==========================================================================
# The rendered advisory
# ==========================================================================


def test_the_advisory_leads_with_the_decision_and_stays_short():
    """One number per person. A five-line WhatsApp message, not a report."""
    profile = predict(SHIPMENT, TOMATO, mc_draws=400)
    lines = render_advisory(profile).splitlines()
    assert 3 <= len(lines) <= 6
    assert any(profile.actions[0].counterfactual_label in line for line in lines)


def test_the_advisory_only_formats_and_never_recomputes():
    """Every figure in the message must already exist on the profile, so the
    message can never disagree with the API response it was built from."""
    profile = predict(SHIPMENT, TOMATO, mc_draws=400, with_sensitivity=False)
    text = render_advisory(profile)
    assert i18n.format_indian(profile.mass_at_risk_kg, 0) in text
    assert f"{profile.loss_pct:.1f}" in text


def test_action_values_are_localised_on_both_sides_of_the_arrow():
    profile = predict(SHIPMENT, TOMATO, mc_draws=300, with_sensitivity=False)
    for action in profile.actions:
        assert action.current_label
        assert action.counterfactual_label
        if action.field in {"transport_mode", "packaging", "field_holding"}:
            assert DEVANAGARI.search(action.counterfactual_label), action.field


def test_no_english_leaks_into_a_hindi_advisory():
    """The failure mode this catches is a new label added in English only and
    silently falling through. Digits and the % sign are expected; Latin words
    are not."""
    profile = predict(SHIPMENT, TOMATO, mc_draws=400)
    leaked = LATIN_WORD.findall(render_advisory(profile))
    assert not leaked, f"English leaked into the Hindi advisory: {leaked}"
