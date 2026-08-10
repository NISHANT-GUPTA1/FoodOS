"""Track 2 (retail) and Track 3 (production) — the same engine, different
action spaces.

This module is deliberately short. If it ever grows into a second engine, the
platform claim in the pitch has become fiction. Retail reuses the batch
decision path unchanged; production reuses the newsvendor and adds two
manufacturing constraints.
"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy.orm import Session

from foodos.engine import prevent, queries
from foodos.engine.context import DecisionContext
from foodos.engine.planner import build_batch_decisions

# Track 3 constraints. Real plants read these from an item master; the demo
# derives them so the arithmetic stays inspectable.
#
# A fixed lot size across every SKU is wrong — 400 units is a sensible batch
# for bread and an absurd one for celebration cakes. Lots scale with demand.
DEFAULT_LOT_FRACTION = 0.20
DEFAULT_CHANGEOVER_COST = 1800.0


def lot_size_for(mean_demand: float, fraction: float = DEFAULT_LOT_FRACTION) -> float:
    """A plausible minimum batch: a fifth of a day's demand, rounded."""
    raw = max(mean_demand * fraction, 1.0)
    step = 100.0 if raw >= 200 else 50.0 if raw >= 100 else 10.0 if raw >= 20 else 5.0
    return max(round(raw / step) * step, step)


def retail_view(session: Session, ctx: DecisionContext, limit: int = 12) -> list[dict]:
    """Track 2. Batch ledger with the best open action per lot.

    Not one line of new decision logic — the identical `build_batch_decisions`
    that serves the kitchen, pointed at a store site.
    """
    out = []
    for decision in build_batch_decisions(session, ctx)[:limit]:
        best = decision.ranked.best
        risk = decision.risk
        out.append(
            {
                "batch_id": risk.batch_id,
                # Additive. A store's queue names the crate the same way the
                # farm gate did, so "the same engine, a different node" is
                # something a judge can verify against a code on a box rather
                # than a claim on a slide.
                "batch_code": risk.batch_code,
                "origin": risk.origin,
                "product": risk.label,
                "qty_on_hand": risk.qty_on_hand,
                "uom": risk.uom,
                "rsl_days": risk.rsl_days,
                "qty_at_risk": risk.qty_at_risk,
                "waste_probability": risk.waste_probability,
                "value_at_risk": risk.value_at_risk,
                "severity": risk.severity,
                "best_action": best.action.label if best else None,
                "action_type": str(best.action.action_type) if best else None,
                "expected_recovery": round(best.net_recovery, 2) if best else 0.0,
                "uplift_vs_doing_nothing": round(decision.ranked.uplift(), 2),
            }
        )
    return out


def production_view(
    session: Session,
    ctx: DecisionContext,
    target: date | None = None,
    min_lot: float | None = None,
    changeover_cost: float = DEFAULT_CHANGEOVER_COST,
) -> list[dict]:
    """Track 3. Newsvendor quantity, then rounded to a feasible lot.

    The lot choice is scored with the same `V(Q)` the kitchen uses — the only
    addition is that candidate quantities are restricted to multiples of the
    minimum lot, and each extra lot carries a changeover cost.
    """
    target = target or (ctx.today + timedelta(days=1))
    out = []

    for product in queries.plannable_products(session, ctx.site_id):
        dist = queries.demand_distribution(session, ctx.site_id, product.id, target)
        if dist is None or dist.mean <= 0:
            continue

        baseline = queries.recent_baseline_qty(session, ctx.site_id, product.id, target)
        plan = prevent.plan_quantity(product, dist, ctx, baseline_qty=baseline)
        baseline = plan.baseline_qty
        lot = min_lot if min_lot is not None else lot_size_for(dist.mean)

        # Candidate lots either side of the unconstrained optimum.
        n_opt = max(plan.recommended_qty / lot, 0.0)
        candidates = sorted({max(int(n_opt), 1) * lot, (int(n_opt) + 1) * lot})

        best_qty, best_value = candidates[0], float("-inf")
        for qty in candidates:
            value = prevent.value_of_quantity(product, dist, qty, baseline, ctx)
            value -= changeover_cost * (qty / lot)  # one changeover per lot
            if value > best_value:
                best_qty, best_value = qty, value

        # Savings must be scored against the lot actually recommended, not the
        # unconstrained optimum — rounding up to a feasible lot can wipe the
        # gain out entirely, and the plan has to say so.
        saving_kg, saving_money, saving_co2e = prevent.saving_between(
            product, dist, baseline, best_qty, ctx
        )

        out.append(
            {
                "product_id": product.id,
                "product": product.name,
                "uom": product.uom,
                "expected_demand": round(dist.mean, 1),
                "demand_low": plan.forecast_low,
                "demand_high": plan.forecast_high,
                "habitual_qty": baseline,
                "unconstrained_optimum": plan.recommended_qty,
                "recommended_qty": best_qty,
                "min_lot": lot,
                "lots": round(best_qty / lot, 2),
                "changeover_cost": changeover_cost,
                "q_star": round(plan.q_star, 4),
                "confidence": str(plan.confidence),
                "saving_money": saving_money,
                "saving_kg": saving_kg,
                "saving_co2e": saving_co2e,
            }
        )

    out.sort(key=lambda r: r["saving_money"], reverse=True)
    return out
