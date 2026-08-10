"""Computed facts — the only numbers that may ever reach an operator.

Every number FoodOS shows is a :class:`Fact`. A Fact is produced by the engine or the
models, carried into an agent as structured input, and rendered into language by Python
string substitution. The language model sees fact KEYS and never fact VALUES in a form it
can arithmetic on, and it emits a template full of ``{{key}}`` tokens that Python fills in.

That is the whole mechanism behind "the LLM never computes a number". It is not a prompt
instruction that we hope holds. The model is structurally unable to put a number in the
output, because the substitution happens after it has finished writing.

Owner: Person D.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Iterator, Mapping

# Units the renderer knows how to format. Anything else is rendered as plain text.
UNIT_INR = "INR"
UNIT_KG = "kg"
UNIT_PCT = "pct"
UNIT_DAYS = "days"
UNIT_HOURS = "hours"
UNIT_PORTIONS = "portions"
UNIT_CO2E = "co2e"
UNIT_TEXT = "text"

#: Direction lexicons. A fact that declares ``direction="down"`` may not be described with
#: an "up" word, and vice versa. The Verifier enforces this — it is the cheapest possible
#: guard against an agent that gets the numbers right and the story backwards.
DIRECTION_WORDS: Mapping[str, tuple[str, ...]] = {
    "up": ("increase", "increased", "increasing", "rose", "risen", "rising",
           "grew", "growing", "higher", "up", "gain", "gained", "surge", "surged"),
    "down": ("decrease", "decreased", "decreasing", "fell", "fallen", "falling",
             "dropped", "dropping", "lower", "down", "decline", "declined",
             "shrank", "reduced", "reducing"),
}


def format_indian(amount: float, precision: int = 0) -> str:
    """Format a number with Indian digit grouping: 1234567 -> '12,34,567'.

    The audience for this demo reads lakhs, not millions. Getting this wrong is a small
    thing that makes every screen look foreign.
    """
    negative = amount < 0
    text = f"{abs(amount):.{precision}f}"
    whole, _, frac = text.partition(".")

    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        whole = ",".join(parts + [tail])

    out = whole if not frac else f"{whole}.{frac}"
    return f"-{out}" if negative else out


@dataclass(frozen=True)
class Fact:
    """One computed number (or one computed name) with everything needed to render it.

    ``value`` is authoritative. ``display`` is derived. Nothing anywhere in the agent layer
    is allowed to construct a display string by hand.
    """

    key: str
    value: Any
    unit: str = UNIT_TEXT
    label: str = ""
    precision: int = 0
    source: str = "engine"
    direction: str | None = None  # "up" | "down" | None

    def __post_init__(self) -> None:
        if self.direction not in (None, "up", "down"):
            raise ValueError(f"fact {self.key!r}: direction must be 'up', 'down' or None")
        if self.unit != UNIT_TEXT and not isinstance(self.value, (int, float)):
            raise TypeError(
                f"fact {self.key!r}: unit {self.unit!r} requires a numeric value, "
                f"got {type(self.value).__name__}"
            )

    @property
    def effective_precision(self) -> int:
        """Decimals the display actually uses.

        kg, days and CO2e default to one decimal even when ``precision`` is left at zero.
        :meth:`numeric_forms` has to agree with that, or a fact of 0.7 days would make the
        string "1" look traceable and the Verifier would wave through a rounded number.
        """
        if self.unit in (UNIT_KG, UNIT_CO2E, UNIT_DAYS):
            return self.precision or 1
        return self.precision

    @property
    def display(self) -> str:
        v = self.value
        if self.unit == UNIT_TEXT:
            return str(v)
        if self.unit == UNIT_INR:
            return f"₹{format_indian(float(v), self.precision)}"
        if self.unit == UNIT_PCT:
            return f"{format_indian(float(v), self.precision)}%"
        if self.unit == UNIT_KG:
            return f"{format_indian(float(v), self.precision or 1)} kg"
        if self.unit == UNIT_CO2E:
            return f"{format_indian(float(v), self.precision or 1)} kg CO₂e"
        if self.unit == UNIT_DAYS:
            return f"{format_indian(float(v), self.precision or 1)} days"
        if self.unit == UNIT_HOURS:
            return f"{format_indian(float(v), self.precision)} hours"
        if self.unit == UNIT_PORTIONS:
            return f"{format_indian(float(v), self.precision)} portions"
        return str(v)

    @property
    def is_numeric(self) -> bool:
        return self.unit != UNIT_TEXT

    def numeric_forms(self) -> set[str]:
        """Every spelling of this fact's number a verifier should accept as traceable.

        Deliberately narrow. Rounded and re-scaled variants are NOT included: if a fact is
        0.7 days, the string "1" is not this fact, and an output containing it should be
        blocked rather than charitably matched.
        """
        if not self.is_numeric:
            return set()
        value = float(self.value)
        precision = self.effective_precision
        forms = {
            self.display,
            format_indian(value, precision),
            f"{value:.{precision}f}",
            f"{value:g}",
        }
        return {f for f in forms if f}


class FactSet:
    """An immutable, ordered collection of facts keyed by name.

    Agents receive one of these and nothing else. If a number is not in here, it cannot
    reach the operator — there is no code path from an agent to the screen that does not
    go through a fact key.
    """

    def __init__(self, facts: Iterable[Fact] = ()) -> None:
        self._facts: dict[str, Fact] = {}
        for fact in facts:
            self.add(fact)

    def add(self, fact: Fact) -> "FactSet":
        if fact.key in self._facts:
            raise ValueError(f"duplicate fact key {fact.key!r}")
        self._facts[fact.key] = fact
        return self

    def __contains__(self, key: object) -> bool:
        return key in self._facts

    def __getitem__(self, key: str) -> Fact:
        try:
            return self._facts[key]
        except KeyError:
            raise KeyError(
                f"no computed fact named {key!r}. Available: {', '.join(sorted(self._facts))}"
            ) from None

    def __iter__(self) -> Iterator[Fact]:
        return iter(self._facts.values())

    def __len__(self) -> int:
        return len(self._facts)

    def keys(self) -> list[str]:
        return list(self._facts)

    def get(self, key: str, default: Fact | None = None) -> Fact | None:
        return self._facts.get(key, default)

    def missing(self, required: Iterable[str]) -> list[str]:
        return [k for k in required if k not in self._facts]

    def catalogue(self) -> str:
        """The block of text an agent actually sees. Keys, labels, units — never a value.

        This is deliberate. An agent that never sees 18400 cannot decide to write 18,400,
        and cannot decide to write 21,000 either.
        """
        lines = []
        for f in self._facts.values():
            kind = "text" if f.unit == UNIT_TEXT else f"number, {f.unit}"
            label = f.label or f.key.replace("_", " ")
            hint = f" [trend: {f.direction}]" if f.direction else ""
            lines.append(f"  {{{{{f.key}}}}}  -  {label} ({kind}){hint}")
        return "\n".join(lines)

    def text_values(self) -> set[str]:
        """Every string a fact resolves to. Used by the hallucinated-entity check."""
        return {str(f.value) for f in self._facts.values() if not f.is_numeric}

    def numeric_forms(self) -> set[str]:
        forms: set[str] = set()
        for f in self._facts.values():
            forms |= f.numeric_forms()
        return forms

    def snapshot(self) -> dict[str, Any]:
        return {
            f.key: {"value": f.value, "unit": f.unit, "display": f.display, "source": f.source}
            for f in self._facts.values()
        }


def facts(*items: Fact) -> FactSet:
    """Small convenience constructor: ``facts(Fact(...), Fact(...))``."""
    return FactSet(items)
