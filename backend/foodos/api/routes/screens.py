"""Screen endpoints: today, attribution, plan, frontier, ledger, rescue, impact."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import select

from foodos.api.deps import ContextDep, SessionDep, resolve_site
from foodos.api.schemas import (
    ActionOut,
    AttributionOut,
    FrontierOut,
    ImpactOut,
    KpiOut,
    LedgerOut,
    LedgerRowOut,
    Money,
    PlanLineOut,
    PlanOut,
    RecommendationOut,
    RescueItemOut,
    RescueOut,
    TodayOut,
)
from foodos.engine import queries, recommendation, simulator, waterfall
from foodos.external import agmarknet
from foodos.engine.optimiser import ScoredAction
from foodos.engine.planner import (
    build_batch_decisions,
    build_ledger,
    build_prevent_plans,
    ingredient_requirement,
)
from foodos.schema.enums import RecommendationStatus
from foodos.schema.tables import Recommendation

router = APIRouter(prefix="/api", tags=["screens"])

WINDOW_DAYS = 30


def _rec_out(rec: Recommendation) -> RecommendationOut:
    return RecommendationOut(
        id=rec.id,
        horizon=str(rec.horizon),
        subject_type=rec.subject_type,
        subject_id=rec.subject_id,
        subject_label=rec.subject_label,
        action_type=rec.action_type,
        action_params=rec.action_params or {},
        baseline_value=rec.baseline_value,
        recommended_value=rec.recommended_value,
        saves=Money(
            kg=rec.expected_saving_kg,
            money=rec.expected_saving_money,
            co2e=rec.expected_co2e,
        ),
        confidence=str(rec.confidence),
        rationale_text=rec.rationale_text,
        rationale_facts=rec.rationale_facts or {},
        status=str(rec.status),
        override_reason=rec.override_reason,
        override_value=rec.override_value,
        expires_at=rec.expires_at.isoformat() if rec.expires_at else None,
    )


def _action_out(scored: ScoredAction) -> ActionOut:
    a = scored.action
    tier = waterfall.tier_of_action(a.action_type)
    return ActionOut(
        label=a.label,
        action_type=str(a.action_type),
        horizon=str(a.horizon),
        qty=a.qty,
        qty_kg=a.qty_kg,
        recovered_value=round(a.recovered_value, 2),
        cost=round(a.cost, 2),
        net_recovery=round(scored.net_recovery, 2),
        kg_food_saved=a.kg_food_saved,
        co2e_saved_kg=a.co2e_saved_kg,
        score=round(scored.value, 2) if scored.feasible else 0.0,
        feasible=scored.feasible,
        exclusion_reason=scored.exclusion_reason,
        terms={k: round(v, 2) for k, v in scored.terms.items()},
        channel_id=a.channel_id,
        waterfall_tier=tier.code if tier else None,
        waterfall_tier_rank=tier.rank if tier else None,
    )


# 1 ------------------------------------------------------------------ TODAY
@router.get("/today", response_model=TodayOut, summary="Today — what to do now")
def today(session: SessionDep, ctx: ContextDep) -> TodayOut:
    site = resolve_site(session, ctx.site_id)
    start = ctx.today - timedelta(days=WINDOW_DAYS)

    ledger = build_ledger(session, ctx)
    decisions = build_batch_decisions(session, ctx)
    share = queries.produce_share(session, ctx.site_id, start, ctx.today)
    by_reason = queries.waste_by_reason(session, ctx.site_id, start, ctx.today)

    total_value = sum(r["value"] for r in by_reason) or 1.0
    drivers = sorted(
        (
            {
                "reason": r["reason"],
                "kg": r["kg"],
                "value": r["value"],
                "share": round(r["value"] / total_value, 4),
            }
            for r in by_reason
        ),
        key=lambda r: r["share"],
        reverse=True,
    )
    preventable = sum(
        d["share"] for d in drivers if d["reason"] in ("overproduction", "prep_trim")
    )

    recs = list(
        session.scalars(
            select(Recommendation)
            .where(
                Recommendation.site_id == ctx.site_id,
                Recommendation.status == RecommendationStatus.PENDING,
            )
            .order_by(Recommendation.expected_saving_money.desc())
        )
    )

    return TodayOut(
        site_id=ctx.site_id,
        site_name=site.name,
        business_date=ctx.today,
        lam=ctx.lam,
        kpis=KpiOut(
            kg_at_risk=round(sum(r.qty_at_risk_kg for r in ledger), 2),
            value_at_risk=round(sum(r.value_at_risk for r in ledger), 2),
            # Money actually recovered by taking the best open action, not the
            # objective-function uplift — a manager reads this as rupees.
            recoverable_today=round(
                sum(
                    d.ranked.best.net_recovery
                    for d in decisions
                    if d.ranked.best is not None
                ),
                2,
            ),
            preventable_share=round(preventable, 4),
            produce_share_of_weight=share["produce_share_of_weight"],
        ),
        waste_drivers=drivers,
        recommendations=[_rec_out(r) for r in recs],
    )


# 2 ------------------------------------------------------------ ATTRIBUTION
@router.get("/attribution", response_model=AttributionOut, summary="Why — root cause")
def attribution(
    session: SessionDep,
    ctx: ContextDep,
    days: Annotated[int, Query(ge=1, le=365)] = WINDOW_DAYS,
) -> AttributionOut:
    start = ctx.today - timedelta(days=days)
    share = queries.produce_share(session, ctx.site_id, start, ctx.today)
    by_reason = queries.waste_by_reason(session, ctx.site_id, start, ctx.today)
    total_value = sum(r["value"] for r in by_reason) or 1.0
    for row in by_reason:
        row["share"] = round(row["value"] / total_value, 4)
    by_reason.sort(key=lambda r: r["share"], reverse=True)

    # Avoidable trim: actual yield against the recipe's standard yield.
    recipes = queries.recipe_map(session, ctx.site_id)
    standards = {
        ing_id: std for lines in recipes.values() for ing_id, _, _, std in lines
    }
    trim = [
        {
            **row,
            "standard_yield_pct": standards.get(row["product_id"]),
        }
        for row in queries.waste_by_product(session, ctx.site_id, start, ctx.today, 20)
        if row["product_id"] in standards
    ]
    trim.sort(key=lambda r: r["value"], reverse=True)

    top = by_reason[0] if by_reason else None
    headline = (
        f"{share['total_kg']:.0f} kg and Rs {share['total_value']:,.0f} lost in "
        f"{days} days. {share['produce_share_of_weight']:.0%} of that weight is "
        f"fruit and vegetables."
        + (
            f" The largest driver is {top['reason'].replace('_', ' ')} at "
            f"{top['share']:.0%}."
            if top
            else ""
        )
    )

    return AttributionOut(
        site_id=ctx.site_id,
        window_start=start,
        window_end=ctx.today,
        total_kg=share["total_kg"],
        total_value=share["total_value"],
        produce_kg=share["produce_kg"],
        produce_value=share["produce_value"],
        produce_share_of_weight=share["produce_share_of_weight"],
        by_reason=by_reason,
        by_product=queries.waste_by_product(session, ctx.site_id, start, ctx.today),
        daily=queries.waste_daily(session, ctx.site_id, start, ctx.today),
        avoidable_trim=trim[:8],
        headline=headline,
    )


# 3 ------------------------------------------------------------------- PLAN
@router.get("/plan", response_model=PlanOut, summary="Plan — how much tomorrow")
def plan(
    session: SessionDep,
    ctx: ContextDep,
    target: Annotated[date | None, Query()] = None,
) -> PlanOut:
    target = target or (ctx.today + timedelta(days=1))
    plans = build_prevent_plans(session, ctx, target)

    lines = [
        PlanLineOut(
            product_id=p.product_id,
            label=p.label,
            uom=p.uom,
            baseline_qty=p.baseline_qty,
            recommended_qty=p.recommended_qty,
            delta=round(p.recommended_qty - p.baseline_qty, 1),
            q_star=round(p.q_star, 4),
            forecast_median=p.forecast_median,
            forecast_low=p.forecast_low,
            forecast_high=p.forecast_high,
            expected_waste_baseline_kg=p.expected_waste_baseline_kg,
            expected_waste_recommended_kg=p.expected_waste_recommended_kg,
            saving_kg=p.saving_kg,
            saving_money=p.saving_money,
            saving_co2e=p.saving_co2e,
            confidence=str(p.confidence),
            economics=p.economics,
        )
        for p in plans
    ]

    return PlanOut(
        site_id=ctx.site_id,
        target_date=target,
        lam=ctx.lam,
        lines=lines,
        totals=Money(
            kg=round(sum(p.saving_kg for p in plans), 2),
            money=round(sum(p.saving_money for p in plans), 2),
            co2e=round(sum(p.saving_co2e for p in plans), 2),
        ),
        ingredient_requirement=ingredient_requirement(session, ctx, plans),
    )


# 4 --------------------------------------------------------------- FRONTIER
@router.get("/frontier", response_model=FrontierOut, summary="The lambda slider")
def frontier(
    session: SessionDep,
    ctx: ContextDep,
    target: Annotated[date | None, Query()] = None,
) -> FrontierOut:
    target = target or (ctx.today + timedelta(days=1))
    return FrontierOut(
        site_id=ctx.site_id,
        target_date=target,
        points=simulator.frontier(session, ctx, target),
        note=(
            "Lambda moves C_o, which moves q*, which moves every quantity in "
            "the plan. The slider is the objective function made visible."
        ),
    )


# 5 ----------------------------------------------------------------- LEDGER
@router.get("/ledger", response_model=LedgerOut, summary="Food Life Ledger")
def ledger(session: SessionDep, ctx: ContextDep) -> LedgerOut:
    rows = build_ledger(session, ctx)
    return LedgerOut(
        site_id=ctx.site_id,
        as_of=ctx.today,
        rows=[
            LedgerRowOut(
                batch_id=r.batch_id,
                product_id=r.product_id,
                product=r.label,
                category=r.category,
                uom=r.uom,
                qty_on_hand=r.qty_on_hand,
                qty_kg=r.qty_kg,
                rsl_days=r.rsl_days,
                rsl_explanation=r.rsl_explanation,
                expected_consumption=r.expected_consumption,
                qty_at_risk=r.qty_at_risk,
                waste_probability=r.waste_probability,
                value_at_risk=r.value_at_risk,
                severity=r.severity,
                storage_zone=r.storage_zone,
                batch_code=r.batch_code,
                origin=r.origin,
            )
            for r in rows
        ],
        total_value_at_risk=round(sum(r.value_at_risk for r in rows), 2),
    )


# 6 ----------------------------------------------------------------- RESCUE
@router.get("/rescue", response_model=RescueOut, summary="Ranked exits, with exclusions")
def rescue(session: SessionDep, ctx: ContextDep) -> RescueOut:
    decisions = build_batch_decisions(session, ctx)
    items = []
    for d in decisions:
        best = d.ranked.best
        # The blueprint's fixed remaining-life ladder, alongside the exit the
        # objective function actually chose. Reported, never enforced.
        ladder = waterfall.tier_of_rsl(d.risk.rsl_days)
        engine = waterfall.tier_of_action(best.action.action_type) if best else None
        items.append(
            RescueItemOut(
                batch_id=d.risk.batch_id,
                product=d.risk.label,
                qty_at_risk=d.risk.qty_at_risk,
                uom=d.risk.uom,
                rsl_days=d.risk.rsl_days,
                value_at_risk=d.risk.value_at_risk,
                severity=d.risk.severity,
                ranked=[_action_out(s) for s in d.ranked.ranked],
                excluded=[_action_out(s) for s in d.ranked.excluded],
                best_recovery=round(best.net_recovery, 2) if best else 0.0,
                uplift_vs_doing_nothing=round(d.ranked.uplift(), 2),
                ladder_tier=ladder.code,
                engine_tier=engine.code if engine else None,
                tier_agrees=engine is not None and engine.rank == ladder.rank,
                market_reference=agmarknet.latest_for(session, d.risk.label, ctx.today),
            )
        )
    return RescueOut(
        site_id=ctx.site_id,
        as_of=ctx.today,
        lam=ctx.lam,
        items=items,
        total_recoverable=round(sum(i.best_recovery for i in items), 2),
    )


# 7 ----------------------------------------------------------------- IMPACT
@router.get("/impact", response_model=ImpactOut, summary="Is this actually working?")
def impact(
    session: SessionDep,
    ctx: ContextDep,
    train_days: Annotated[int, Query(ge=5, le=180)] = 45,
    eval_days: Annotated[int, Query(ge=3, le=90)] = 14,
) -> ImpactOut:
    bt = simulator.backtest(session, ctx, train_days=train_days, eval_days=eval_days)
    per_day = bt.saving_money / max(bt.days_evaluated, 1)
    per_day_kg = bt.saving_kg / max(bt.days_evaluated, 1)
    return ImpactOut(
        site_id=ctx.site_id,
        acceptance=recommendation.acceptance_rate(session, ctx.site_id),
        realised_vs_projected=recommendation.realised_vs_projected(session, ctx.site_id),
        backtest=bt.__dict__,
        monthly_projection=Money(
            kg=round(per_day_kg * 30, 2),
            money=round(per_day * 30, 2),
            co2e=round(per_day_kg * 30 * ctx.co2e_kg_per_kg_food, 2),
        ),
    )
