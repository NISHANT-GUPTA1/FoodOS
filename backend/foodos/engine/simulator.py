"""Savings simulator and the backtest counterfactual.

The backtest is the credibility firewall. It trains on one window, evaluates on
a window the model has never seen, and reports what *would have happened* —
measured against what actually did. Nothing here is a projection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from foodos.engine import prevent, queries
from foodos.engine.context import DecisionContext
from foodos.engine.distribution import DemandDistribution
from foodos.engine.planner import build_prevent_plans
from foodos.schema.tables import ProductionRecord, SalesRecord


# ------------------------------------------------------------ plan simulator


@dataclass
class PlanSimulation:
    lam: float
    total_baseline_qty: float
    total_recommended_qty: float
    expected_waste_baseline_kg: float
    expected_waste_recommended_kg: float
    saving_kg: float
    saving_money: float
    saving_co2e: float
    lines: list[dict] = field(default_factory=list)


def simulate(plans: list[prevent.PreventPlan], lam: float) -> PlanSimulation:
    return PlanSimulation(
        lam=lam,
        total_baseline_qty=round(sum(p.baseline_qty for p in plans), 1),
        total_recommended_qty=round(sum(p.recommended_qty for p in plans), 1),
        expected_waste_baseline_kg=round(
            sum(p.expected_waste_baseline_kg for p in plans), 2
        ),
        expected_waste_recommended_kg=round(
            sum(p.expected_waste_recommended_kg for p in plans), 2
        ),
        saving_kg=round(sum(p.saving_kg for p in plans), 2),
        saving_money=round(sum(p.saving_money for p in plans), 2),
        saving_co2e=round(sum(p.saving_co2e for p in plans), 2),
        lines=[
            {
                "product_id": p.product_id,
                "label": p.label,
                "uom": p.uom,
                "baseline_qty": p.baseline_qty,
                "recommended_qty": p.recommended_qty,
                "saving_kg": p.saving_kg,
                "saving_money": p.saving_money,
            }
            for p in plans
        ],
    )


def frontier(
    session: Session,
    ctx: DecisionContext,
    target: date | None = None,
    lambdas: tuple[float, ...] = (0.0, 0.25, 0.5, 1.0, 1.5, 2.0, 3.0),
) -> list[dict]:
    """The waste/margin frontier behind the lambda slider.

    Sweeping lambda is not a visual trick — it moves C_o, which moves q*, which
    moves every quantity in the plan. The slider is the objective function made
    visible.
    """
    out = []
    for lam in lambdas:
        plans = build_prevent_plans(session, ctx.with_lambda(lam), target)
        sim = simulate(plans, lam)
        out.append(
            {
                "lambda": lam,
                "total_recommended_qty": sim.total_recommended_qty,
                "expected_waste_kg": sim.expected_waste_recommended_kg,
                "saving_kg": sim.saving_kg,
                "saving_money": sim.saving_money,
                "saving_co2e": sim.saving_co2e,
            }
        )
    return out


# ----------------------------------------------------------------- backtest


@dataclass
class BacktestResult:
    train_start: date
    train_end: date
    eval_start: date
    eval_end: date
    days_evaluated: int
    products_evaluated: int

    actual_waste_kg: float
    modelled_waste_kg: float
    saving_kg: float
    saving_money: float

    median_abs_error: float
    naive_abs_error: float
    improvement_vs_naive: float | None
    interval_coverage: float

    daily: list[dict] = field(default_factory=list)
    note: str = ""


def backtest(
    session: Session,
    ctx: DecisionContext,
    train_days: int = 20,
    eval_days: int = 10,
) -> BacktestResult:
    """Replay held-out history through the engine.

    Train window: the only data the forecast may see.
    Eval window:  days the forecast has never seen.

    For each dish and day we compare what the kitchen actually produced with
    what the newsvendor would have recommended, and score both against the
    demand that actually occurred.
    """
    end = ctx.today
    eval_start = end - timedelta(days=eval_days)
    train_start = eval_start - timedelta(days=train_days)

    dishes = queries.dishes(session, ctx.site_id)
    daily: dict[date, dict] = {}
    errors: list[float] = []
    naive_errors: list[float] = []
    inside_interval: list[int] = []
    actual_waste_kg = modelled_waste_kg = saving_money = 0.0
    products_seen = 0

    for product in dishes:
        econ = prevent.economics(product, ctx)
        weight = max(product.unit_weight_kg, 1e-6)

        history = session.execute(
            select(SalesRecord.business_date, SalesRecord.qty).where(
                SalesRecord.site_id == ctx.site_id,
                SalesRecord.product_id == product.id,
                SalesRecord.business_date >= train_start,
                SalesRecord.business_date < eval_start,
            )
        ).all()
        if len(history) < 8:
            continue
        products_seen += 1

        by_dow: dict[int, list[float]] = {}
        for d, q in history:
            by_dow.setdefault(d.weekday(), []).append(float(q))
        all_qty = [float(q) for _, q in history]

        actuals = session.execute(
            select(SalesRecord.business_date, SalesRecord.qty).where(
                SalesRecord.site_id == ctx.site_id,
                SalesRecord.product_id == product.id,
                SalesRecord.business_date >= eval_start,
                SalesRecord.business_date <= end,
            )
        ).all()
        produced = {
            d: float(q)
            for d, q in session.execute(
                select(
                    ProductionRecord.business_date, ProductionRecord.actual_qty
                ).where(
                    ProductionRecord.site_id == ctx.site_id,
                    ProductionRecord.product_id == product.id,
                    ProductionRecord.business_date >= eval_start,
                    ProductionRecord.business_date <= end,
                )
            ).all()
        }

        for day, actual_qty in actuals:
            actual_qty = float(actual_qty)
            same_dow = by_dow.get(day.weekday(), [])
            pool = same_dow if len(same_dow) >= 5 else all_qty
            if len(pool) < 5:
                continue
            dist = DemandDistribution.from_samples(pool)

            _, q_model = prevent.optimal_quantity(dist, econ)
            q_model = max(round(q_model), 0)
            q_actual = produced.get(day)
            if q_actual is None:
                continue

            waste_actual = max(q_actual - actual_qty, 0.0)
            waste_model = max(q_model - actual_qty, 0.0)
            units_saved = waste_actual - waste_model

            lost_margin = econ.cu * max(
                min(q_actual, actual_qty) - min(q_model, actual_qty), 0.0
            )
            money = units_saved * (econ.unit_cost + econ.disposal_per_unit) - lost_margin

            actual_waste_kg += waste_actual * weight
            modelled_waste_kg += waste_model * weight
            saving_money += money

            # Forecast quality: median vs a same-weekday-last-week naive.
            errors.append(abs(dist.quantile(0.50) - actual_qty))
            naive_errors.append(abs(pool[-1] - actual_qty))
            lo, hi = dist.interval()
            inside_interval.append(1 if lo <= actual_qty <= hi else 0)

            row = daily.setdefault(
                day,
                {"date": day.isoformat(), "actual_waste_kg": 0.0, "modelled_waste_kg": 0.0, "saving_money": 0.0},
            )
            row["actual_waste_kg"] += waste_actual * weight
            row["modelled_waste_kg"] += waste_model * weight
            row["saving_money"] += money

    mae = float(np.mean(errors)) if errors else 0.0
    naive_mae = float(np.mean(naive_errors)) if naive_errors else 0.0
    improvement = (naive_mae - mae) / naive_mae if naive_mae > 1e-9 else None
    coverage = float(np.mean(inside_interval)) if inside_interval else 0.0

    return BacktestResult(
        train_start=train_start,
        train_end=eval_start - timedelta(days=1),
        eval_start=eval_start,
        eval_end=end,
        days_evaluated=len(daily),
        products_evaluated=products_seen,
        actual_waste_kg=round(actual_waste_kg, 2),
        modelled_waste_kg=round(modelled_waste_kg, 2),
        saving_kg=round(actual_waste_kg - modelled_waste_kg, 2),
        saving_money=round(saving_money, 2),
        median_abs_error=round(mae, 2),
        naive_abs_error=round(naive_mae, 2),
        improvement_vs_naive=round(improvement, 4) if improvement is not None else None,
        interval_coverage=round(coverage, 4),
        daily=[
            {k: (round(v, 2) if isinstance(v, float) else v) for k, v in row.items()}
            for row in sorted(daily.values(), key=lambda r: r["date"])
        ],
        note=(
            "Trained on the train window only; evaluated on days the forecast "
            "never saw. Savings are measured against what the kitchen actually "
            "produced, not projected."
        ),
    )
