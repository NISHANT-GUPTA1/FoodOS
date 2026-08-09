"""The Action — a candidate thing the business could do.

Every action, in every track, in every horizon, is this one shape. That is
what lets a single objective function score all of them.

Builders (prevent / preserve / rescue / tracks) know domain eligibility and
set `blocked_reason`. The universal gates — remaining life against lead time,
and minimum quantity — live in the optimiser so they are applied identically
everywhere.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from foodos.schema.enums import ActionType, Horizon


@dataclass(frozen=True)
class Action:
    action_type: ActionType
    horizon: Horizon
    label: str

    subject_type: str  # dish | batch | sku | run
    subject_id: int
    subject_label: str = ""

    # --- quantities --------------------------------------------------------
    qty: float = 0.0  # in the subject's own unit of measure
    qty_kg: float = 0.0  # the same quantity in kilograms
    baseline_qty: float = 0.0

    # --- terms consumed by the objective function --------------------------
    recovered_value: float = 0.0  # E[value recovered | a]
    cost: float = 0.0  # discount, logistics, labour, disposal
    loss_probability: float = 0.0  # P(it is still lost | a)
    value_at_risk: float = 0.0
    kg_food_saved: float = 0.0  # food a human eats that otherwise would not be
    co2e_saved_kg: float = 0.0
    social_value: float = 0.0  # rupee-equivalent, donation channels only

    # --- feasibility inputs -----------------------------------------------
    rsl_days: float | None = None
    lead_time_hours: float = 0.0
    min_qty_required: float = 0.0
    blocked_reason: str | None = None  # set by the builder for domain rules

    # --- provenance --------------------------------------------------------
    params: dict = field(default_factory=dict)
    facts: dict = field(default_factory=dict)
    channel_id: int | None = None

    @property
    def is_baseline(self) -> bool:
        return self.action_type == ActionType.DO_NOTHING


def do_nothing(
    subject_type: str,
    subject_id: int,
    subject_label: str,
    value_at_risk: float,
    qty: float = 0.0,
    qty_kg: float = 0.0,
    horizon: Horizon = Horizon.RECOVER,
) -> Action:
    """The always-available baseline: take no action and lose the value.

    Included in every ranking on purpose. "Rs 1,650 recovered against Rs 0 for
    doing nothing" is only meaningful if doing nothing was actually scored.
    """
    return Action(
        action_type=ActionType.DO_NOTHING,
        horizon=horizon,
        label="Do nothing",
        subject_type=subject_type,
        subject_id=subject_id,
        subject_label=subject_label,
        qty=qty,
        qty_kg=qty_kg,
        recovered_value=0.0,
        cost=0.0,
        loss_probability=1.0,
        value_at_risk=value_at_risk,
        facts={"note": "baseline — the food is lost"},
    )
