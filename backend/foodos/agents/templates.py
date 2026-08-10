"""Token rendering — where numbers enter the sentence, after the model has stopped writing.

An agent returns a template::

    "Cut {{dish_name}} from {{current_qty}} to {{recommended_qty}} and you keep {{saving_inr}}."

Python resolves each token against the :class:`~foodos.agents.facts.FactSet` the engine
computed. An unknown token is not a typo to paper over — it means the model invented a
quantity that does not exist, so it raises and the output is blocked.

Owner: Person D.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .facts import FactSet

#: Deliberately restrictive: lowercase, digits, underscore, dot. No expressions, no
#: arithmetic, no formatting directives. There is nothing to inject here.
TOKEN_RE = re.compile(r"\{\{\s*([a-z][a-z0-9_.]*)\s*\}\}")

#: A brace that survived tokenising — a half-written token, which we treat as an error
#: rather than letting "{{ recommended qty }}" reach an operator's screen.
_STRAY_BRACE_RE = re.compile(r"\{\{|\}\}")


class UnknownTokenError(Exception):
    """The model referenced a fact that the engine never computed."""

    def __init__(self, unknown: list[str], available: list[str]) -> None:
        self.unknown = unknown
        self.available = available
        super().__init__(
            f"template references unknown fact(s): {', '.join(unknown)}. "
            f"Computed facts are: {', '.join(available)}"
        )


class MalformedTemplateError(Exception):
    """A stray or malformed brace pair survived rendering."""


def tokens_in(template: str) -> list[str]:
    """Fact keys referenced by a template, in order, without duplicates."""
    seen: dict[str, None] = {}
    for match in TOKEN_RE.finditer(template):
        seen.setdefault(match.group(1), None)
    return list(seen)


def unknown_tokens(template: str, facts: "FactSet") -> list[str]:
    return [t for t in tokens_in(template) if t not in facts]


def render(template: str, facts: "FactSet", *, strict: bool = True) -> str:
    """Substitute every token with its computed display value.

    ``strict=True`` (always, in production) raises on an unknown token or a stray brace.
    """
    unknown = unknown_tokens(template, facts)
    if unknown and strict:
        raise UnknownTokenError(unknown, facts.keys())

    def _sub(match: re.Match[str]) -> str:
        key = match.group(1)
        fact = facts.get(key)
        return fact.display if fact is not None else match.group(0)

    rendered = TOKEN_RE.sub(_sub, template)

    if strict:
        stray = _STRAY_BRACE_RE.search(rendered)
        if stray:
            raise MalformedTemplateError(
                f"unresolved brace at position {stray.start()} in rendered output: {rendered!r}"
            )
    return rendered
