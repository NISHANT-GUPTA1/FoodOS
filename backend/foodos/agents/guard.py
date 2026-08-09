"""The number guard.

This module is the load-bearing wall under the sentence "the LLM never computes a number".

Rule: raw model output may not contain a numeral, in any notation, in any script. Not a
digit, not a spelled-out cardinal, not a Devanagari digit. If the model wants a number in
its sentence it must write a ``{{fact_key}}`` token and let Python put the number there.

A violation is not repaired and it is not ignored. The agent is retried with a correction,
and if it violates again the output is BLOCKED — the operator sees a fallback, never a
number the model chose.

Owner: Person D.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from .templates import TOKEN_RE


class NumberEmittedError(Exception):
    """Raised when raw model output contains a number the model chose itself."""

    def __init__(self, offenders: list[str], text: str) -> None:
        self.offenders = offenders
        self.text = text
        shown = ", ".join(repr(o) for o in offenders[:6])
        super().__init__(f"model emitted {len(offenders)} number(s) of its own: {shown}")


#: Cardinals, magnitudes and multipliers. Ordinals ("first", "second") are deliberately
#: absent — they are ranking words, not quantities, and blocking them costs us natural
#: sentences for no safety gain.
NUMBER_WORDS: frozenset[str] = frozenset(
    """
    zero one two three four five six seven eight nine ten
    eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen
    twenty thirty forty fifty sixty seventy eighty ninety
    hundred thousand lakh lakhs crore crores million millions billion billions
    half halves quarter quarters third thirds dozen dozens
    once twice thrice double triple quadruple
    """.split()
)

_WORD_RE = re.compile(r"[A-Za-z]+")

#: A whole number as written, so the report says "6,700" rather than six separate digits.
#: Covers ASCII, Devanagari and Arabic-Indic digits with their separators.
_DIGITS = "0-9०-९٠-٩"
_NUMERIC_RUN = re.compile(rf"[{_DIGITS}][{_DIGITS},]*(?:\.[{_DIGITS}]+)?")

#: Single characters that carry a numeric value without being digits: superscripts and
#: vulgar fractions. The obvious way around a plain \d, so it is closed here.
#: Subscripts are deliberately absent — the ₂ in CO₂e is chemistry, not a quantity.
_EXOTIC_DIGIT = re.compile(r"[¼-¾⅐-⅞²³¹⁰⁴-⁹]")

#: Roman numerals used as quantities. Bounded to standalone uppercase tokens so ordinary
#: capitalised words are untouched.
_ROMAN_RE = re.compile(r"\b(?=[MDCLXVI]{2,})M*(?:CM|CD|D?C{0,3})(?:XC|XL|L?X{0,3})(?:IX|IV|V?I{0,3})\b")


@dataclass(frozen=True)
class GuardReport:
    clean: bool
    offenders: tuple[str, ...]

    def __bool__(self) -> bool:
        return self.clean


def strip_tokens(text: str) -> str:
    """Remove ``{{fact_key}}`` tokens so the guard judges only what the model authored."""
    return TOKEN_RE.sub(" ", text)


def find_numbers(text: str, *, block_number_words: bool = True) -> list[str]:
    """Return every number the model wrote itself. Empty list means the output is clean.

    Offenders are reported as the model wrote them — "6,700", not six loose digits — and
    deduplicated, so a correction message reads like feedback rather than a hex dump.
    """
    body = strip_tokens(text)
    offenders: list[str] = []

    for match in _NUMERIC_RUN.finditer(body):
        offenders.append(match.group(0).rstrip(",."))

    for match in _EXOTIC_DIGIT.finditer(body):
        char = match.group(0)
        try:
            name = unicodedata.name(char).lower()
        except ValueError:  # pragma: no cover - every listed char is named
            name = "numeric character"
        offenders.append(f"{char} ({name})")

    for match in _ROMAN_RE.finditer(body):
        offenders.append(match.group(0))

    if block_number_words:
        for match in _WORD_RE.finditer(body):
            word = match.group(0).lower()
            if word in NUMBER_WORDS:
                offenders.append(word)

    seen: dict[str, None] = {}
    for offender in offenders:
        seen.setdefault(offender, None)
    return list(seen)


def inspect(text: str, *, block_number_words: bool = True) -> GuardReport:
    offenders = find_numbers(text, block_number_words=block_number_words)
    return GuardReport(clean=not offenders, offenders=tuple(offenders))


def assert_number_free(text: str, *, block_number_words: bool = True) -> None:
    """Raise :class:`NumberEmittedError` if the model wrote a number of its own."""
    offenders = find_numbers(text, block_number_words=block_number_words)
    if offenders:
        raise NumberEmittedError(offenders, text)


CORRECTION_NOTE = (
    "Your previous reply contained a number you wrote yourself: {offenders}.\n"
    "You are not permitted to state, estimate, round, convert or spell out any quantity.\n"
    "Rewrite the reply. Wherever a quantity belongs, put the matching {{fact_key}} token "
    "from the fact list and nothing else. Do not write the digit and the token together."
)


def correction_for(offenders: list[str]) -> str:
    return CORRECTION_NOTE.format(offenders=", ".join(offenders[:6]))
