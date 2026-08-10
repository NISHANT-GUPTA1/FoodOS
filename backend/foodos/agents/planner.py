"""Planner — low-RSL stock in, a menu special the kitchen can actually run out.

Owner: Person D.
"""

from __future__ import annotations

from .base import Agent
from .facts import FactSet


class Planner(Agent):
    name = "planner"

    required_facts = (
        "special_dish_name",
        "batch_ingredient_name",
        "batch_zone_name",
        "batch_qty_kg",
        "batch_rsl_days",
        "special_portions",
        "special_value_inr",
        "station_name",
    )

    fallback_text = (
        "The suggested special could not be verified and was withheld. "
        "The at-risk batch and its recommended action are still on the Ledger screen."
    )

    def user_message(self, facts: FactSet) -> str:
        return (
            "The optimiser has already selected the dish for tonight's special by running "
            "the same objective function as every other recommendation in the system. The "
            "dish is fixed. Your job is the brief the kitchen works from.\n\n"
            "FACTS you may cite. Use the token exactly as written; you are never shown the "
            "values behind them.\n"
            f"{facts.catalogue()}\n\n"
            "Write two or three sentences: the call and the batch it clears, the quantities "
            "as tokens, and one execution note about the station. No dish other than the one "
            "in the facts. No number that is not a token."
        )
