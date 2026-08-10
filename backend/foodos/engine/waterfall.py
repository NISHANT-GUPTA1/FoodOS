"""Cascading diversion tiers — a label on the ranking, never the ranking itself.

The Production Execution Blueprint proposes a six-tier waterfall that assigns a
batch to an exit from remaining life alone: over 48 h fresh retail, 24–48 h B2B
kitchens, 12–24 h processing, and down through donation, feed and compost.

FoodOS adopts the vocabulary and refuses the ladder. The vocabulary is useful —
"Tier 2" is a faster thing to say to a category manager than "processing at a
34% price factor". The ladder is not, because a band drawn on remaining life
alone cannot see that the puree unit is 8 km away with a 10 kg minimum, that the
NGO needs a full day of life for its handover window, or that a transfer 400 m
away recovers twice the money at the same remaining life. `optimiser.score()`
sees all of that, so the ranking stays exactly where it is.

Both are therefore reported on every rescue item: `ladder_tier` is what the
blueprint's RSL bands would have picked, `engine_tier` is what V(a) actually
chose. Where they differ the difference is worth showing — it is the clearest
one-line argument for why an optimiser beats a lookup table.

Thresholds are the blueprint's own, in hours, converted to the days the rest of
the engine works in.
"""

from __future__ import annotations

from dataclasses import dataclass

from foodos.schema.enums import ActionType

HOURS_PER_DAY = 24.0


@dataclass(frozen=True)
class Tier:
    rank: int
    code: str
    name: str
    #: Lower bound of the blueprint's remaining-life band, in hours. The upper
    #: bound is the next tier up's `min_hours`; Tier 0 is unbounded above.
    min_hours: float

    @property
    def min_days(self) -> float:
        return self.min_hours / HOURS_PER_DAY


#: Ordered best-value-first, which is also the blueprint's own order.
TIERS: tuple[Tier, ...] = (
    Tier(0, "TIER_0_PRIMARY_FRESH", "Primary fresh use", 48.0),
    Tier(1, "TIER_1_B2B_KITCHENS", "B2B kitchens and markdown", 24.0),
    Tier(2, "TIER_2_PROCESSING", "Industrial processing", 12.0),
    Tier(3, "TIER_3_HUMANITARIAN", "Humanitarian redistribution", 6.0),
    Tier(4, "TIER_4_ANIMAL_FEED", "Animal feed", 2.0),
    Tier(5, "TIER_5_BIOREFINERY", "Biorefinery and compost", 0.0),
)

_BY_RANK = {t.rank: t for t in TIERS}

# One exit belongs to exactly one tier. Keyed on ActionType rather than
# ChannelType so PRESERVE actions (use_first, relocate) label the same way as
# the RECOVER channel that leads to the same destination.
_TIER_OF_ACTION: dict[ActionType, int] = {
    ActionType.USE_FIRST: 0,
    ActionType.RELOCATE: 0,
    ActionType.REPLAN_MENU: 0,
    ActionType.STAFF_MEAL: 0,
    ActionType.MARKDOWN: 1,
    ActionType.DEEP_MARKDOWN: 1,
    ActionType.TRANSFER: 1,
    ActionType.B2B_TRANSFER: 1,
    ActionType.PROCESS: 2,
    ActionType.DONATE: 3,
    ActionType.ANIMAL_FEED: 4,
    ActionType.COMPOST: 5,
}


def tier_of_action(action_type: ActionType | str) -> Tier | None:
    """Which waterfall tier this exit belongs to.

    `None` for the do-nothing baseline and for PREVENT quantities, neither of
    which is a diversion at all.
    """
    try:
        rank = _TIER_OF_ACTION[ActionType(action_type)]
    except (KeyError, ValueError):
        return None
    return _BY_RANK[rank]


def tier_of_rsl(rsl_days: float) -> Tier:
    """The tier the blueprint's fixed ladder assigns from remaining life alone.

    Reported for comparison, never used to gate or to rank.
    """
    hours = max(float(rsl_days), 0.0) * HOURS_PER_DAY
    for tier in TIERS:
        if hours >= tier.min_hours:
            return tier
    return TIERS[-1]
