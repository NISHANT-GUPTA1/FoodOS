"""Diagnostician — attribution facts in, one sentence of root cause out.

Owner: Person D.
"""

from __future__ import annotations

from .base import Agent
from .facts import FactSet


class Diagnostician(Agent):
    name = "diagnostician"

    required_facts = (
        "top_contributor_name",
        "top_contributor_share",
    )

    fallback_text = (
        "Root cause could not be verified against the computed attribution. "
        "The contributor breakdown on the Why screen is unaffected."
    )

    def user_message(self, facts: FactSet) -> str:
        return (
            "The engine has decomposed today's at-risk value into contributors and ranked "
            "them. The ranking is settled — do not reorder it, do not second-guess it.\n\n"
            "FACTS you may cite. Use the token exactly as written; you are never shown the "
            "values behind them.\n"
            f"{facts.catalogue()}\n\n"
            "Write one sentence naming the largest contributor, its share, and the "
            "mechanism in the kitchen that produced it. No recommendation. No second "
            "sentence. No number that is not a token."
        )
