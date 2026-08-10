"""RECOVER — channel ranking, with the feasibility gate applied before ranking.

Excluded options are returned with their exclusion reason attached. They are
never silently dropped: a chef who cannot see that donation was ruled out on a
handover window will assume the system forgot about it.

Only channels where a human eats the food count toward `kg_food_saved`. Animal
feed and compost earn a partial CO2e credit and nothing else. Counting compost
as "food saved" would be the easiest number to inflate and the fastest way to
lose a judge.
"""

from __future__ import annotations

from foodos.engine.actions import Action, do_nothing
from foodos.engine.context import DecisionContext
from foodos.engine.risk import BatchRisk
from foodos.schema.enums import ActionType, ChannelType, Horizon
from foodos.schema.tables import Channel

_CHANNEL_ACTION: dict[str, ActionType] = {
    ChannelType.INTERNAL_USE: ActionType.USE_FIRST,
    ChannelType.STAFF_MEAL: ActionType.STAFF_MEAL,
    ChannelType.MARKDOWN: ActionType.MARKDOWN,
    ChannelType.B2B_TRANSFER: ActionType.B2B_TRANSFER,
    ChannelType.DONATION: ActionType.DONATE,
    ChannelType.PROCESSING: ActionType.PROCESS,
    ChannelType.ANIMAL_FEED: ActionType.ANIMAL_FEED,
    ChannelType.COMPOST: ActionType.COMPOST,
}

# Does a human eat it? Drives kg_food_saved.
_FEEDS_A_HUMAN = {
    ChannelType.INTERNAL_USE,
    ChannelType.STAFF_MEAL,
    ChannelType.MARKDOWN,
    ChannelType.B2B_TRANSFER,
    ChannelType.DONATION,
    ChannelType.PROCESSING,
}

# CO2e credit for diverting from landfill without feeding anyone.
_DIVERSION_CO2E_FACTOR = {
    ChannelType.ANIMAL_FEED: 0.55,
    ChannelType.COMPOST: 0.30,
}

# Residual chance the food is still lost after routing (missed pickup,
# buyer declines, quality falls further in transit).
_RESIDUAL_LOSS = {
    ChannelType.INTERNAL_USE: 0.05,
    ChannelType.STAFF_MEAL: 0.02,
    ChannelType.MARKDOWN: 0.25,
    ChannelType.B2B_TRANSFER: 0.12,
    ChannelType.DONATION: 0.10,
    ChannelType.PROCESSING: 0.05,
    ChannelType.ANIMAL_FEED: 0.02,
    ChannelType.COMPOST: 0.0,
}


def _eligibility_block(channel: Channel, risk: BatchRisk) -> str | None:
    """Domain rules the builder knows about. The universal gates (remaining
    life, minimum quantity) are applied by the optimiser, not here."""
    accepted = channel.accepted_categories or []
    if accepted and risk.category not in accepted:
        return f"does not accept {risk.category}"

    rules = channel.eligibility_rules or {}

    min_grade = rules.get("min_intake_grade")
    if min_grade is not None and risk.intake_grade < float(min_grade):
        return (
            f"requires intake grade {float(min_grade):.2f}; "
            f"this batch graded {risk.intake_grade:.2f}"
        )

    min_rsl = rules.get("min_rsl_days")
    if min_rsl is not None and risk.rsl_days < float(min_rsl):
        return (
            f"requires {float(min_rsl):g} days of remaining life for safe "
            f"handover; this batch has {risk.rsl_days:.1f}"
        )

    if rules.get("requires_unopened") and risk.intake_grade < 0.999:
        return "requires an unopened batch"

    return None


def channel_action(
    channel: Channel, risk: BatchRisk, ctx: DecisionContext
) -> Action:
    """One channel, one at-risk batch, one scorable action."""
    qty = risk.qty_at_risk
    if channel.max_qty is not None:
        qty = min(qty, channel.max_qty)
    qty_kg = qty * (risk.qty_kg / risk.qty_on_hand) if risk.qty_on_hand > 0 else 0.0

    ctype = ChannelType(channel.type)
    recovered = qty * risk.recover_basis * channel.price_factor
    cost = channel.fixed_cost + channel.cost_per_km * channel.distance_km
    residual = _RESIDUAL_LOSS.get(ctype, 0.10)

    feeds_human = ctype in _FEEDS_A_HUMAN
    kg_food_saved = qty_kg * (1 - residual) if feeds_human else 0.0
    co2e_factor = 1.0 if feeds_human else _DIVERSION_CO2E_FACTOR.get(ctype, 0.0)
    co2e_saved = qty_kg * (1 - residual) * ctx.co2e_kg_per_kg_food * co2e_factor

    social = 0.0
    if ctype == ChannelType.DONATION:
        per_kg = channel.social_value_per_kg or ctx.social_value_per_kg_donated
        social = qty_kg * per_kg

    return Action(
        action_type=_CHANNEL_ACTION.get(ctype, ActionType.B2B_TRANSFER),
        horizon=Horizon.RECOVER,
        label=channel.name,
        subject_type="batch",
        subject_id=risk.batch_id,
        subject_label=risk.label,
        qty=round(qty, 3),
        qty_kg=round(qty_kg, 3),
        recovered_value=round(recovered, 2),
        cost=round(cost, 2),
        loss_probability=residual,
        value_at_risk=risk.value_at_risk,
        kg_food_saved=round(kg_food_saved, 3),
        co2e_saved_kg=round(co2e_saved, 3),
        social_value=round(social, 2),
        rsl_days=risk.rsl_days,
        lead_time_hours=channel.lead_time_hours,
        min_qty_required=channel.min_qty,
        blocked_reason=_eligibility_block(channel, risk),
        channel_id=channel.id,
        params={
            "channel_id": channel.id,
            "channel_type": str(channel.type),
            "qty": round(qty, 3),
            "distance_km": channel.distance_km,
        },
        facts={
            "price_factor": channel.price_factor,
            "logistics_cost": round(cost, 2),
            "residual_loss_probability": residual,
            "feeds_a_human": feeds_human,
        },
    )


def build_actions(
    risk: BatchRisk, channels: list[Channel], ctx: DecisionContext
) -> list[Action]:
    """Every RECOVER action for one at-risk batch, plus the do-nothing baseline."""
    actions = [
        channel_action(c, risk, ctx) for c in channels if c.active and risk.qty_at_risk > 0
    ]
    actions.append(
        do_nothing(
            subject_type="batch",
            subject_id=risk.batch_id,
            subject_label=risk.label,
            value_at_risk=risk.value_at_risk,
            qty=risk.qty_at_risk,
            qty_kg=risk.qty_at_risk_kg,
        )
    )
    return actions
