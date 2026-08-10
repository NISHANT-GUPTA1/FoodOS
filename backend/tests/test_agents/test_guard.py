"""The number guard.

Owner: Person D.
"""

from __future__ import annotations

import pytest

from foodos.agents.guard import NumberEmittedError, assert_number_free, find_numbers, inspect


@pytest.mark.parametrize(
    "text",
    [
        "Cut {{dish_name}} from {{planned}} to {{recommended}} and keep {{saving_inr}}.",
        "Run the special tonight — the paneer will not hold past service.",
        "Move it to the walk-in chiller before the next prep round.",
        "We measure this in kg CO₂e, which is chemistry and not a quantity.",
        "",
    ],
)
def test_clean_output_passes(text):
    assert inspect(text).clean
    assert find_numbers(text) == []
    assert_number_free(text)  # must not raise


@pytest.mark.parametrize(
    "text,expected",
    [
        ("About 4.4 kg left.", "4.4"),
        ("Roughly 6,700 rupees.", "6,700"),
        ("Cut it to 63 portions.", "63"),
        ("It is 38% of the risk.", "38"),
    ],
)
def test_digits_are_caught(text, expected):
    offenders = find_numbers(text)
    assert expected in offenders


@pytest.mark.parametrize(
    "word",
    ["one", "two", "twenty", "half", "a dozen", "lakh", "crore", "double", "thousand"],
)
def test_number_words_are_caught(word):
    text = f"There are {word} portions left."
    assert find_numbers(text), f"{word!r} slipped through the guard"


def test_number_words_can_be_switched_off():
    text = "There are two portions left."
    assert find_numbers(text, block_number_words=False) == []
    assert find_numbers(text, block_number_words=True)


def test_words_containing_a_number_word_are_not_caught():
    """'none' contains 'one'. Blocking it would make the agents unable to write English."""
    for text in ["none of the stock", "someone should move it", "atonement", "wonder"]:
        assert find_numbers(text) == [], text


def test_ordinals_are_allowed():
    """'first' and 'second' are ranking words, not quantities."""
    assert find_numbers("the first contributor, then the second") == []


def test_non_ascii_digits_are_caught():
    assert find_numbers("६३ portions")  # Devanagari
    assert find_numbers("٦٣ portions")  # Arabic-Indic


def test_fractions_and_superscripts_are_caught():
    assert find_numbers("about ½ the stock")
    assert find_numbers("m² of prep space")


def test_roman_numerals_are_caught():
    assert find_numbers("batch XIV is at risk")


def test_subscripts_are_not_caught():
    """CO₂e must survive the guard, or the agents cannot discuss carbon at all."""
    assert find_numbers("this avoids CO₂e") == []


def test_numbers_inside_tokens_are_invisible_to_the_guard():
    """The token is the model's only legitimate way to reference a quantity."""
    assert find_numbers("we recovered {{value_inr}} on {{batch_id}}") == []


def test_offenders_are_deduplicated_and_readable():
    offenders = find_numbers("4.4 kg, then 4.4 kg again, and 6,700 rupees")
    assert offenders == ["4.4", "6,700"]


def test_assert_raises_with_the_offenders_attached():
    with pytest.raises(NumberEmittedError) as excinfo:
        assert_number_free("cut it to 63 portions")
    assert "63" in excinfo.value.offenders
    assert "63" in str(excinfo.value)
