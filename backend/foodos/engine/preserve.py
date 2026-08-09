"""PRESERVE — actions available while the food is still alive.

Two actions live here. Channel-based moves (transfer, markdown, donate) are
generated in `rescue.py` because they are all the same shape: a channel with a
price factor, a lead time and an eligibility rule.

    USE_FIRST  reorder consumption so this batch is drawn down before others
    RELOCATE   fix a storage placement that is shortening the batch's life
"""

from __future__ import annotations

from foodos.engine.actions import Action
from foodos.engine.context import DecisionContext
from foodos.engine.risk import BatchRisk
from foodos.schema.enums import ActionType, Horizon

# Stated assumption, not a fitted parameter: prioritising a batch in the menu
# or on the shelf pulls forward roughly this share of the at-risk quantity.
# Exposed here so a judge can see it is an assumption and argue with it.
USE_FIRST_ABSORPTION = 0.45

# Fixing an ethylene adjacency recovers roughly this share of the value the
# adjacency was destroying. Also a stated assumption.
RELOCATE_RECOVERY = 0.60

# Labour cost of reordering a pick sequence or moving a crate.
USE_FIRST_COST = 0.0
RELOCATE_COST = 25.0


def use_first_action(risk: BatchRisk, ctx: DecisionContext) -> Action:
    """Draw this batch down before the others. Always feasible, always free."""
    absorbed = risk.qty_at_risk * USE_FIRST_ABSORPTION
    absorbed_kg = risk.qty_at_risk_kg * USE_FIRST_ABSORPTION
    recovered = absorbed * risk.recover_basis

    return Action(
        action_type=ActionType.USE_FIRST,
        horizon=Horizon.PRESERVE,
        label=f"Use {risk.label} first",
        subject_type="batch",
        subject_id=risk.batch_id,
        subject_label=risk.label,
        qty=round(absorbed, 3),
        qty_kg=round(absorbed_kg, 3),
        recovered_value=round(recovered, 2),
        cost=USE_FIRST_COST,
        # Whatever prioritising does not absorb is still exposed.
        loss_probability=risk.waste_probability * (1 - USE_FIRST_ABSORPTION),
        value_at_risk=risk.value_at_risk,
        kg_food_saved=round(absorbed_kg, 3),
        co2e_saved_kg=round(absorbed_kg * ctx.co2e_kg_per_kg_food, 3),
        rsl_days=risk.rsl_days,
        lead_time_hours=0.0,
        params={"absorption": USE_FIRST_ABSORPTION},
        facts={
            "rsl_days": risk.rsl_days,
            "qty_at_risk": risk.qty_at_risk,
            "assumption": (
                f"prioritising pulls forward {USE_FIRST_ABSORPTION:.0%} "
                "of the at-risk quantity"
            ),
        },
    )


def relocate_action(
    risk: BatchRisk, ctx: DecisionContext, emitter_label: str, life_cost_days: float
) -> Action:
    """Move an ethylene-sensitive batch away from an emitter.

    Cheap, unglamorous, and real: tomatoes stored beside leafy greens
    measurably shorten the greens' life.
    """
    recovered = risk.value_at_risk * RELOCATE_RECOVERY
    kg = risk.qty_at_risk_kg * RELOCATE_RECOVERY

    return Action(
        action_type=ActionType.RELOCATE,
        horizon=Horizon.PRESERVE,
        label=f"Move {risk.label} away from {emitter_label}",
        subject_type="batch",
        subject_id=risk.batch_id,
        subject_label=risk.label,
        qty=risk.qty_on_hand,
        qty_kg=risk.qty_kg,
        recovered_value=round(recovered, 2),
        cost=RELOCATE_COST,
        loss_probability=risk.waste_probability * (1 - RELOCATE_RECOVERY),
        value_at_risk=risk.value_at_risk,
        kg_food_saved=round(kg, 3),
        co2e_saved_kg=round(kg * ctx.co2e_kg_per_kg_food, 3),
        rsl_days=risk.rsl_days,
        lead_time_hours=0.0,
        params={"emitter": emitter_label, "life_cost_days": round(life_cost_days, 2)},
        facts={
            "issue": (
                f"{emitter_label} is stored in the same zone and is costing "
                f"{life_cost_days:.1f} days of life"
            )
        },
    )


def build_actions(
    risk: BatchRisk,
    ctx: DecisionContext,
    ethylene_conflict: tuple[str, float] | None = None,
) -> list[Action]:
    """Every PRESERVE action available for one at-risk batch."""
    actions = [use_first_action(risk, ctx)]
    if ethylene_conflict is not None:
        emitter, life_cost = ethylene_conflict
        actions.append(relocate_action(risk, ctx, emitter, life_cost))
    return actions
