"""Orchestration: turn a site and a date into decisions.

Reads through `queries`, computes through the pure modules, scores through the
one objective function. Holds no business rules of its own.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy.orm import Session

from foodos.engine import preserve, prevent, queries, rescue
from foodos.engine.context import DecisionContext
from foodos.engine.optimiser import RankedActions, rank
from foodos.engine.risk import BatchRisk, assess
from foodos.schema.tables import Batch

# Life an ethylene emitter costs a sensitive neighbour sharing its zone.
ETHYLENE_LIFE_COST_DAYS = 0.8


# --------------------------------------------------------------- PREVENT


def build_prevent_plans(
    session: Session, ctx: DecisionContext, target: date | None = None
) -> list[prevent.PreventPlan]:
    """Tomorrow's quantity for every dish at this site."""
    target = target or (ctx.today + timedelta(days=1))
    plans: list[prevent.PreventPlan] = []

    for product in queries.dishes(session, ctx.site_id):
        dist = queries.demand_distribution(session, ctx.site_id, product.id, target)
        if dist is None:
            continue
        baseline = queries.recent_baseline_qty(session, ctx.site_id, product.id, target)
        plans.append(prevent.plan_quantity(product, dist, ctx, baseline_qty=baseline))

    plans.sort(key=lambda p: p.saving_money, reverse=True)
    return plans


def ingredient_requirement(
    session: Session, ctx: DecisionContext, plans: list[prevent.PreventPlan]
) -> list[dict]:
    recipes = queries.recipe_map(session, ctx.site_id)
    exploded = prevent.explode_to_ingredients(plans, recipes)
    return sorted(exploded.values(), key=lambda r: r["saved_kg"], reverse=True)


# --------------------------------------------------------------- PRESERVE


def _ethylene_conflicts(session: Session, ctx: DecisionContext) -> dict[int, tuple[str, float]]:
    """batch_id -> (emitter name, days of life it is costing).

    Cheap to compute, unglamorous, and real.
    """
    batches = queries.open_batches(session, ctx.site_id)
    emitters_by_zone: dict[int, str] = {}
    for b in batches:
        profile = b.product.shelf_life_profile
        if profile and profile.ethylene_emitter and b.storage_zone_id:
            emitters_by_zone.setdefault(b.storage_zone_id, b.product.name)

    conflicts: dict[int, tuple[str, float]] = {}
    for b in batches:
        profile = b.product.shelf_life_profile
        if not profile or not profile.ethylene_sensitive or not b.storage_zone_id:
            continue
        emitter = emitters_by_zone.get(b.storage_zone_id)
        if emitter and emitter != b.product.name:
            conflicts[b.id] = (emitter, ETHYLENE_LIFE_COST_DAYS)
    return conflicts


def _batch_risk(session: Session, ctx: DecisionContext, batch: Batch) -> BatchRisk:
    product = batch.product
    zones = queries.zone_map(session, ctx.site_id)
    zone = zones.get(batch.storage_zone_id) if batch.storage_zone_id else None
    daily = queries.daily_usage_distribution(session, ctx.site_id, product.id, ctx.today)

    rsl = batch.rsl_days
    if rsl is None:
        # Fallback only. A overwrites `Batch.rsl_days` with the calibrated model.
        rsl = (
            (batch.printed_expiry - ctx.today).days
            if batch.printed_expiry
            else 3.0
        )

    return assess(
        batch_id=batch.id,
        product_id=product.id,
        label=product.name,
        category=product.category,
        uom=batch.uom,
        qty_on_hand=batch.qty_remaining,
        unit_weight_kg=product.unit_weight_kg,
        rsl_days=float(rsl),
        rsl_explanation=batch.rsl_explanation or "",
        daily_demand=daily,
        unit_cost=batch.unit_cost or product.unit_cost,
        unit_price=product.unit_price,
        intake_grade=batch.intake_grade,
        storage_zone=zone.name if zone else None,
        # Provenance, when the lot has any. Read off the denormalised column
        # and the stored `inherited` block rather than through the
        # consignment relationship: the Ledger scores every open batch on the
        # site, and a join per row for a chip is a join per row too many.
        batch_code=batch.batch_code,
        origin=(batch.inherited or {}).get("origin"),
    )


def build_ledger(session: Session, ctx: DecisionContext) -> list[BatchRisk]:
    """The Food Life Ledger — every open batch, scored."""
    risks = [
        _batch_risk(session, ctx, b) for b in queries.open_batches(session, ctx.site_id)
    ]
    risks.sort(key=lambda r: (-r.value_at_risk, r.rsl_days))
    return risks


# ------------------------------------------------------- PRESERVE + RECOVER


@dataclass
class BatchDecision:
    risk: BatchRisk
    ranked: RankedActions


def build_batch_decisions(
    session: Session, ctx: DecisionContext, min_value_at_risk: float = 1.0
) -> list[BatchDecision]:
    """For every at-risk batch: all PRESERVE and RECOVER actions, ranked.

    Both horizons go into one ranking on purpose. The question is not "should
    I preserve or recover this?" — it is "what is the highest-value thing to
    do with this food right now?", and the answer should be allowed to be
    either.
    """
    channels = queries.channels(session, ctx.site_id)
    conflicts = _ethylene_conflicts(session, ctx)
    decisions: list[BatchDecision] = []

    for risk in build_ledger(session, ctx):
        if risk.value_at_risk < min_value_at_risk or risk.qty_at_risk <= 0:
            continue
        actions = preserve.build_actions(risk, ctx, conflicts.get(risk.batch_id))
        actions += rescue.build_actions(risk, channels, ctx)
        decisions.append(BatchDecision(risk=risk, ranked=rank(actions, ctx)))

    decisions.sort(key=lambda d: d.ranked.uplift(), reverse=True)
    return decisions
