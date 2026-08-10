"""The Recommendation lifecycle.

A recommendation nobody follows has zero impact regardless of its accuracy, so
acceptance rate is a first-class metric here rather than an afterthought.

`baseline_value` is persisted alongside `recommended_value` because that is the
only way the saving can be honestly computed — and later verified against what
actually happened.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from foodos.engine.context import DecisionContext
from foodos.engine.optimiser import ScoredAction
from foodos.engine.planner import BatchDecision, build_batch_decisions, build_prevent_plans
from foodos.engine.prevent import PreventPlan
from foodos.schema.base import utcnow
from foodos.schema.enums import Confidence, Horizon, RecommendationStatus
from foodos.schema.tables import Recommendation, RecommendationOutcome


# --------------------------------------------------------------- generation


def _prevent_row(
    plan: PreventPlan, ctx: DecisionContext, target: date
) -> Recommendation:
    delta = plan.baseline_qty - plan.recommended_qty
    direction = "Reduce" if delta > 0 else "Increase"
    return Recommendation(
        site_id=ctx.site_id,
        business_date=target,
        horizon=Horizon.PREVENT,
        subject_type="dish",
        subject_id=plan.product_id,
        subject_label=plan.label,
        action_type="set_prep_qty",
        action_params={"qty": plan.recommended_qty, "uom": plan.uom},
        baseline_value=plan.baseline_qty,
        recommended_value=plan.recommended_qty,
        expected_saving_kg=plan.saving_kg,
        expected_saving_money=plan.saving_money,
        expected_co2e=plan.saving_co2e,
        confidence=plan.confidence,
        rationale_facts={**plan.economics, **plan.facts},
        rationale_text=(
            f"{direction} tomorrow's {plan.label} from {plan.baseline_qty:.0f} to "
            f"{plan.recommended_qty:.0f} {plan.uom}. Forecast median "
            f"{plan.forecast_median:.0f} (10-90 band {plan.forecast_low:.0f}-"
            f"{plan.forecast_high:.0f}). Optimal service level "
            f"{plan.q_star:.2f} given a Rs {plan.economics['cu']:.0f} margin "
            f"and Rs {plan.economics['co_effective']:.0f} cost per unsold unit."
        ),
        expires_at=datetime.combine(target, datetime.min.time()) + timedelta(hours=6),
    )


def _batch_row(
    decision: BatchDecision, best: ScoredAction, ctx: DecisionContext
) -> Recommendation:
    action = best.action
    risk = decision.risk
    baseline = decision.ranked.baseline

    # baseline/recommended are *quantities*, because that is what the UI shows
    # next to a unit. Doing nothing actions zero; the recommendation actions
    # `action.qty`. The objective-function values live in the facts below,
    # where they belong.
    return Recommendation(
        site_id=ctx.site_id,
        business_date=ctx.today,
        horizon=action.horizon,
        subject_type="batch",
        subject_id=risk.batch_id,
        subject_label=risk.label,
        action_type=str(action.action_type),
        action_params=action.params,
        baseline_value=0.0,
        recommended_value=round(action.qty, 3),
        expected_saving_kg=action.kg_food_saved,
        expected_saving_money=round(best.net_recovery, 2),
        expected_co2e=action.co2e_saved_kg,
        confidence=(
            Confidence.HIGH
            if risk.waste_probability >= 0.6
            else Confidence.MEDIUM
            if risk.waste_probability >= 0.3
            else Confidence.LOW
        ),
        rationale_facts={
            "rsl_days": risk.rsl_days,
            "qty_at_risk": risk.qty_at_risk,
            "waste_probability": risk.waste_probability,
            "value_at_risk": risk.value_at_risk,
            "uom": risk.uom,
            "terms": {k: round(v, 2) for k, v in best.terms.items()},
            "objective_value": round(best.value, 2),
            "objective_value_of_doing_nothing": (
                round(baseline.value, 2) if baseline else 0.0
            ),
            **action.facts,
        },
        rationale_text=(
            f"{risk.qty_at_risk:.1f} {risk.uom} of {risk.label} is at risk "
            f"(remaining life {risk.rsl_days:.1f} days, "
            f"P(waste) {risk.waste_probability:.0%}, Rs {risk.value_at_risk:.0f} "
            f"exposed). Best open action: {action.label} — "
            f"Rs {best.net_recovery:.0f} recovered against Rs 0 for doing nothing."
        ),
        expires_at=datetime.combine(ctx.today, datetime.min.time())
        + timedelta(days=1),
    )


def generate(
    session: Session,
    ctx: DecisionContext,
    target: date | None = None,
    replace_existing: bool = True,
) -> list[Recommendation]:
    """Rebuild today's recommendation set from the current data."""
    target = target or (ctx.today + timedelta(days=1))

    if replace_existing:
        session.query(Recommendation).filter(
            Recommendation.site_id == ctx.site_id,
            Recommendation.status == RecommendationStatus.PENDING,
        ).delete(synchronize_session=False)

    rows: list[Recommendation] = []

    for plan in build_prevent_plans(session, ctx, target):
        if abs(plan.saving_money) < ctx.min_recommendation_value:
            continue
        rows.append(_prevent_row(plan, ctx, target))

    for decision in build_batch_decisions(session, ctx):
        best = decision.ranked.best
        if best is None or best.action.is_baseline:
            continue
        if decision.ranked.uplift() < ctx.min_recommendation_value:
            continue
        rows.append(_batch_row(decision, best, ctx))

    session.add_all(rows)
    session.flush()
    return rows


# ---------------------------------------------------------------- lifecycle


def accept(session: Session, recommendation_id: int) -> Recommendation:
    rec = session.get(Recommendation, recommendation_id)
    if rec is None:
        raise LookupError(f"recommendation {recommendation_id} not found")
    rec.status = RecommendationStatus.ACCEPTED
    session.flush()
    return rec


def override(
    session: Session,
    recommendation_id: int,
    reason: str,
    value: float | None = None,
) -> Recommendation:
    """An override is a signal, not a failure.

    A chef who always preps 10% above us on Fridays is telling us something our
    features missed, so the reason is stored and handed back to A.
    """
    rec = session.get(Recommendation, recommendation_id)
    if rec is None:
        raise LookupError(f"recommendation {recommendation_id} not found")
    rec.status = RecommendationStatus.OVERRIDDEN
    rec.override_reason = reason
    rec.override_value = value
    session.flush()
    return rec


def expire_stale(session: Session, now: datetime | None = None) -> int:
    now = now or utcnow()
    q = session.query(Recommendation).filter(
        Recommendation.status == RecommendationStatus.PENDING,
        Recommendation.expires_at.is_not(None),
        Recommendation.expires_at < now.replace(tzinfo=None),
    )
    n = q.count()
    q.update({"status": RecommendationStatus.EXPIRED}, synchronize_session=False)
    return n


# ------------------------------------------------------------------ metrics


def acceptance_rate(session: Session, site_id: int) -> dict:
    rows = session.execute(
        select(Recommendation.status, func.count(Recommendation.id))
        .where(Recommendation.site_id == site_id)
        .group_by(Recommendation.status)
    ).all()
    counts = {str(status): int(n) for status, n in rows}
    accepted = counts.get(RecommendationStatus.ACCEPTED, 0)
    overridden = counts.get(RecommendationStatus.OVERRIDDEN, 0)
    decided = accepted + overridden
    return {
        "counts": counts,
        "decided": decided,
        "accepted": accepted,
        "overridden": overridden,
        "acceptance_rate": round(accepted / decided, 4) if decided else None,
    }


def record_outcome(
    session: Session,
    recommendation_id: int,
    actual_value: float,
    actual_saving_kg: float,
    actual_saving_money: float,
) -> RecommendationOutcome:
    outcome = RecommendationOutcome(
        recommendation_id=recommendation_id,
        measured_at=utcnow().replace(tzinfo=None),
        actual_value=actual_value,
        actual_saving_kg=actual_saving_kg,
        actual_saving_money=actual_saving_money,
    )
    session.add(outcome)
    session.flush()
    return outcome


def realised_vs_projected(session: Session, site_id: int) -> dict:
    rows = session.execute(
        select(
            func.sum(Recommendation.expected_saving_money),
            func.sum(Recommendation.expected_saving_kg),
            func.sum(RecommendationOutcome.actual_saving_money),
            func.sum(RecommendationOutcome.actual_saving_kg),
        )
        .select_from(Recommendation)
        .join(
            RecommendationOutcome,
            RecommendationOutcome.recommendation_id == Recommendation.id,
        )
        .where(Recommendation.site_id == site_id)
    ).one()
    proj_money, proj_kg, act_money, act_kg = (float(v or 0) for v in rows)
    return {
        "projected_money": round(proj_money, 2),
        "projected_kg": round(proj_kg, 2),
        "actual_money": round(act_money, 2),
        "actual_kg": round(act_kg, 2),
        "realisation_rate": round(act_money / proj_money, 4) if proj_money else None,
    }
