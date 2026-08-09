"""Communicator — a B2B transfer decision in, a WhatsApp message a manager answers out.

Owner: Person D.
"""

from __future__ import annotations

from .base import Agent
from .facts import FactSet

#: Words that turn a transfer into a favour we are asking for. The Communicator's prompt
#: bans them; this list lets the caller check cheaply without a model round trip.
BANNED_FRAMING = (
    "surplus", "excess", "leftover", "left over", "waste", "wastage",
    "expiring", "expired", "unsold", "dump", "get rid of",
)


class Communicator(Agent):
    name = "communicator"

    required_facts = (
        "outlet_name",
        "batch_ingredient_name",
        "batch_qty_kg",
        "batch_rsl_days",
        "transfer_value_inr",
        "pickup_by",
    )

    fallback_text = (
        "The transfer message could not be verified and was not drafted. "
        "The transfer itself is still the recommended action — send it manually."
    )

    def user_message(self, facts: FactSet) -> str:
        return (
            "The optimiser ranked a transfer to a sister outlet above every other channel "
            "for this batch, and the feasibility gate has already cleared lead time, cold "
            "chain and minimum quantity. Write the message that gets a yes.\n\n"
            "FACTS you may cite. Use the token exactly as written; you are never shown the "
            "values behind them.\n"
            f"{facts.catalogue()}\n\n"
            "Three or four short WhatsApp lines: what we have and its remaining life, what "
            "it saves them, the collection deadline and why it exists, and a one-word ask. "
            f"Never use any of these words: {', '.join(BANNED_FRAMING)}. "
            "No number that is not a token."
        )

    def framing_violations(self, text: str) -> list[str]:
        """Banned framing words found in a rendered message. Cheap, no model call."""
        low = text.lower()
        return [w for w in BANNED_FRAMING if w in low]
