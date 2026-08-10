"""The composition layer: everything the API serves, assembled in one place.

Routers are thin on purpose. They parse a query parameter, call a method here, and
serialise a DTO. All the decisions live in this module and the ones it calls, so the same
answers are available to the seed, to tests, and to anyone at a Python prompt — not only
over HTTP.

λ flows in one direction and is never defaulted twice: the router clamps it, hands it to
:class:`FoodosService`, and every response echoes back the value that was actually used.

Owner: Person B.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from functools import cached_property

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Config, get_config
from ..models import rsl
from ..models.attribution import attribute_window
from ..models.forecaster import QuantileCurve
from ..schema import (
    Batch,
    DemandContext,
    Forecast,
    Product,
    ProductionRecord,
    Recipe,
    SalesRecord,
    StorageZone,
    WasteEvent,
    ZoneTemperature,
)
from . import recommendation as rec
from .optimiser import Objective, Prices
from .prevent import build_plan, economics_for
from .rescue import RescueResult, best_special, rank_channels, rezone_options
from .simulator import recommend_lambda, sweep


@dataclass
class ServiceContext:
    """Everything read once per request that would otherwise be read five times."""

    prices: Prices
    labour_cost: float
    exclusion_reasons: dict[str, str]
    outlet_name: str = "Koramangala"


class FoodosService:
    def __init__(
        self,
        session: Session,
        context: ServiceContext,
        config: Config | None = None,
        *,
        now: dt.datetime | None = None,
    ) -> None:
        self.session = session
        self.context = context
        self.config = config or get_config()
        self.now = now or self.config.demo_datetime

    @property
    def date(self) -> dt.date:
        return self.now.date()

    def objective(self, lambda_: float | None = None) -> Objective:
        return Objective(self.config.clamp_lambda(lambda_), self.context.prices)

    # --- cached reads -------------------------------------------------------

    @cached_property
    def curves(self) -> dict[str, QuantileCurve]:
        """Forecast distributions for the demo date, as persisted by the seed."""
        rows = self.session.scalars(
            select(Forecast).where(Forecast.date == self.date, Forecast.is_backtest == False)  # noqa: E712
        ).all()
        grouped: dict[str, list[tuple[float, float]]] = {}
        for row in rows:
            grouped.setdefault(row.dish_id, []).append((row.quantile, row.value))
        return {
            dish_id: QuantileCurve([q for q, _ in pairs], [v for _, v in pairs])
            for dish_id, pairs in grouped.items()
        }

    @cached_property
    def dishes(self) -> list[Product]:
        return list(self.session.scalars(select(Product).where(Product.kind == "dish")).all())

    @cached_property
    def open_batches(self) -> list[Batch]:
        return list(
            self.session.scalars(select(Batch).where(Batch.is_open == True)).all()  # noqa: E712
        )

    @cached_property
    def zone_service_temps(self) -> dict[str, float]:
        """Recent service-hours temperature per zone — what the stock actually experienced."""
        start = self.date - dt.timedelta(days=14)
        rows = self.session.scalars(
            select(ZoneTemperature).where(ZoneTemperature.date > start)
        ).all()
        by_zone: dict[str, list[float]] = {}
        for row in rows:
            by_zone.setdefault(row.zone_id, []).append(row.service_temp_c)
        temps = {zone: float(np.mean(values)) for zone, values in by_zone.items()}
        for zone in self.session.scalars(select(StorageZone)).all():
            temps.setdefault(zone.id, zone.typical_temp_c)
        return temps

    @cached_property
    def daily_usage_kg(self) -> dict[str, float]:
        """How fast the kitchen gets through each ingredient, from the last month's production.

        This is what turns "old" into "at risk". A batch is only in trouble if the kitchen
        cannot consume it before its life runs out.
        """
        start = self.date - dt.timedelta(days=28)
        production = self.session.execute(
            select(ProductionRecord.dish_id, ProductionRecord.produced_portions)
            .where(ProductionRecord.date > start)
        ).all()

        per_day: dict[str, float] = {}
        for dish_id, portions in production:
            per_day[dish_id] = per_day.get(dish_id, 0.0) + float(portions) / 28.0

        usage: dict[str, float] = {}
        for recipe in self.session.scalars(select(Recipe)).all():
            portions = per_day.get(recipe.dish_id, 0.0)
            if portions <= 0:
                continue
            for line in recipe.lines:
                ingredient = line.ingredient
                purchased = line.qty_kg / float(ingredient.prep_yield or 1.0)
                usage[line.ingredient_id] = usage.get(line.ingredient_id, 0.0) + purchased * portions
        return usage

    # --- risk ---------------------------------------------------------------

    def batch_rsl(self, batch: Batch) -> float:
        profile = batch.product.shelf_life
        if profile is None:
            return 30.0
        return rsl.remaining_shelf_life(
            profile,
            self.zone_service_temps.get(batch.zone_id, batch.zone.typical_temp_c),
            batch.age_days(self.now),
            is_cut=batch.is_cut,
            ethylene_exposed=batch.ethylene_exposed,
        )

    def batch_risk(self, batch: Batch) -> rsl.RiskAssessment:
        return rsl.assess_risk(
            rsl_days=self.batch_rsl(batch),
            qty_kg=batch.qty_kg,
            daily_usage_kg=self.daily_usage_kg.get(batch.product_id, 0.5),
            unit_cost_per_kg=float(batch.unit_cost_per_kg),
            co2e_per_kg=float(batch.product.co2e_kg_per_kg or 0.0),
        )

    # --- screens ------------------------------------------------------------

    def ledger(self) -> list[dict]:
        rows = []
        for batch in self.open_batches:
            assessment = self.batch_risk(batch)
            severity = rsl.severity(
                assessment.rsl_days,
                critical=self.config.critical_rsl_days,
                warning=self.config.warning_rsl_days,
            )
            rows.append(
                {
                    "batch_id": batch.id,
                    "product_id": batch.product_id,
                    "product_name": batch.product.name,
                    "zone_id": batch.zone_id,
                    "zone_name": batch.zone.name,
                    "zone_running_warm": batch.zone.is_running_warm,
                    "qty_kg": round(batch.qty_kg, 2),
                    "state": batch.state,
                    "rsl_days": round(assessment.rsl_days, 2),
                    "risk_pct": round(assessment.risk_pct, 1),
                    "value_at_risk_inr": round(assessment.value_at_risk_inr, 2),
                    "recommended_action": self._ledger_action(batch, assessment, severity),
                    "severity": severity,
                }
            )
        rows.sort(key=lambda row: (row["rsl_days"], -row["value_at_risk_inr"]))
        return rows

    def _ledger_action(self, batch: Batch, assessment, severity: str) -> str:
        if assessment.risk_pct < 5:
            return "No action"
        colder = rezone_options(self.session, batch, now=self.now, objective=self.objective())
        if colder and colder[0].life_gain_days >= 0.4:
            return colder[0].name
        if severity == "critical":
            return "Rescue today"
        return "Use first"

    def attribution(self, window_days: int = 14):
        waste = pd.read_sql(
            select(WasteEvent.date, WasteEvent.product_id, WasteEvent.qty_kg,
                   WasteEvent.reason, WasteEvent.value_inr, WasteEvent.zone_id),
            self.session.connection(),
        )
        production = pd.read_sql(
            select(ProductionRecord.date, ProductionRecord.dish_id,
                   ProductionRecord.planned_portions, ProductionRecord.produced_portions),
            self.session.connection(),
        )
        sales = pd.read_sql(
            select(SalesRecord.date, SalesRecord.dish_id, SalesRecord.qty_portions),
            self.session.connection(),
        )
        zone_temps = pd.read_sql(
            select(ZoneTemperature.date, ZoneTemperature.zone_id, ZoneTemperature.service_temp_c),
            self.session.connection(),
        )
        medians = pd.read_sql(
            select(Forecast.date, Forecast.dish_id, Forecast.value.label("forecast_median"))
            .where(Forecast.is_backtest == True, Forecast.quantile == 0.5),  # noqa: E712
            self.session.connection(),
        )

        for frame in (waste, production, sales, zone_temps, medians):
            if not frame.empty:
                frame["date"] = pd.to_datetime(frame["date"])

        zones = {
            zone.id: {"set_temp_c": zone.set_temp_c, "typical_temp_c": zone.typical_temp_c}
            for zone in self.session.scalars(select(StorageZone)).all()
        }
        ingredient_yields = {
            product.id: float(product.prep_yield or 1.0)
            for product in self.session.scalars(
                select(Product).where(Product.kind == "ingredient")
            ).all()
            if float(product.prep_yield or 1.0) < 1.0
        }

        return attribute_window(
            date=self.date,
            waste=waste,
            production=production,
            sales=sales,
            forecast_median=medians if not medians.empty else pd.DataFrame(
                columns=["date", "dish_id", "forecast_median"]
            ),
            zone_temps=zone_temps,
            zones=zones,
            dish_names={d.id: d.name for d in self.dishes},
            ingredient_yields=ingredient_yields,
            window_days=window_days,
        )

    def plan(self, lambda_: float | None = None):
        return build_plan(
            self.session,
            date=self.date,
            curves=self.curves,
            objective=self.objective(lambda_),
            labour_cost=self.context.labour_cost,
        )

    def rescue(self, batch_id: str | None = None, lambda_: float | None = None) -> RescueResult:
        batch = self._pick_batch(batch_id)
        objective = self.objective(lambda_)

        # The special is chosen first, because how much of this batch tonight's covers can
        # absorb is what bounds every channel valued at menu price.
        special = best_special(self.session, batch, self.curves)

        result = rank_channels(
            self.session,
            batch,
            objective=objective,
            now=self.now,
            rsl_days=self.batch_rsl(batch),
            exclusion_reasons=self.context.exclusion_reasons,
            menu_demand_cap_kg=special["kg_used"] if special else None,
        )
        result.special = special
        return result

    def _pick_batch(self, batch_id: str | None) -> Batch:
        if batch_id:
            batch = self.session.get(Batch, batch_id)
            if batch is None:
                raise KeyError(batch_id)
            return batch
        ranked = sorted(
            self.open_batches,
            key=lambda b: self.batch_risk(b).value_at_risk_inr,
            reverse=True,
        )
        if not ranked:
            raise KeyError("no open batches")
        return ranked[0]

    def simulate(self, steps: int = 11):
        points = sweep(
            self.session,
            date=self.date,
            curves=self.curves,
            prices=self.context.prices,
            labour_cost=self.context.labour_cost,
            steps=steps,
        )
        return points, recommend_lambda(points)

    # --- recommendations ----------------------------------------------------

    def build_recommendations(self, lambda_: float | None = None) -> list:
        """Every horizon, ranked by what each action is worth. One card shape throughout."""
        objective = self.objective(lambda_)
        lam = objective.lambda_
        out = []

        # PREVENT — production cuts worth acting on.
        plan = self.plan(lam)
        for line in plan.lines:
            if line.saving_inr < self.config.min_saving_inr or line.delta >= 0:
                continue
            curve = self.curves.get(line.dish_id)
            out.append(
                rec.build(
                    date=self.date,
                    horizon=rec.HORIZON_PREVENT,
                    action_kind="reduce_production",
                    title=f"Cut {line.dish_name} to {line.recommended_qty:g}",
                    subject_id=line.dish_id,
                    subject_name=line.dish_name,
                    current_qty=line.current_qty,
                    recommended_qty=line.recommended_qty,
                    qty_unit="portions",
                    saving_inr=line.saving_inr,
                    saving_kg=line.saving_kg,
                    saving_co2e_kg=line.saving_co2e_kg,
                    lambda_used=lam,
                    confidence=rec.confidence_from_spread(curve.median, curve.spread) if curve else 0.7,
                    why=[
                        {"label": "Prep sheet", "value": f"{line.current_qty:g} portions", "kind": "fact"},
                        {"label": "Forecast", "value": f"{curve.median:.0f} portions" if curve else "n/a", "kind": "fact"},
                        {"label": "Service level", "value": f"{line.service_level * 100:.0f}%", "kind": "evidence"},
                        {"label": "Expected to sell", "value": f"{line.expected_sold:g} portions", "kind": "evidence"},
                        {"label": "Sustainability weight", "value": f"λ = {lam:g}", "kind": "tradeoff"},
                    ],
                )
            )

        # PRESERVE — free life, first.
        for batch in self.open_batches:
            assessment = self.batch_risk(batch)
            if assessment.value_at_risk_inr < self.config.min_saving_inr:
                continue
            options = rezone_options(self.session, batch, now=self.now, objective=objective)
            if not options or options[0].life_gain_days < 0.4:
                continue
            best = options[0]
            out.append(
                rec.build(
                    date=self.date,
                    horizon=rec.HORIZON_PRESERVE,
                    action_kind="rezone",
                    title=f"{best.name} — {batch.product.name}",
                    subject_id=batch.id,
                    subject_name=batch.product.name,
                    current_qty=round(assessment.rsl_days, 1),
                    recommended_qty=round(assessment.rsl_days + best.life_gain_days, 1),
                    qty_unit="days of life",
                    saving_inr=min(best.net_value_inr, assessment.value_at_risk_inr),
                    saving_kg=assessment.qty_at_risk_kg,
                    saving_co2e_kg=assessment.co2e_at_risk_kg,
                    lambda_used=lam,
                    confidence=0.9,
                    why=[
                        {"label": "Currently in", "value": batch.zone.name, "kind": "fact"},
                        {"label": "Zone running at", "value": f"{self.zone_service_temps.get(batch.zone_id, 0):.1f} °C", "kind": "evidence"},
                        {"label": "Set point", "value": f"{batch.zone.set_temp_c:.1f} °C", "kind": "evidence"},
                        {"label": "Life gained", "value": f"{best.life_gain_days:.1f} days", "kind": "fact"},
                        {"label": "Cost to do it", "value": "nothing", "kind": "tradeoff"},
                    ],
                )
            )

        # RECOVER — for stock the first two horizons could not save.
        for batch in self.open_batches:
            assessment = self.batch_risk(batch)
            if assessment.rsl_days > self.config.warning_rsl_days or assessment.risk_pct < 20:
                continue
            result = self.rescue(batch.id, lam)
            best = result.best
            if best is None or best.vs_baseline_inr < self.config.min_saving_inr:
                continue
            out.append(
                rec.build(
                    date=self.date,
                    horizon=rec.HORIZON_RECOVER,
                    action_kind="rescue",
                    title=f"{best.name} — {batch.qty_kg:g} kg {batch.product.name.lower()}",
                    subject_id=batch.id,
                    subject_name=batch.product.name,
                    current_qty=round(batch.qty_kg, 2),
                    recommended_qty=round(batch.qty_kg, 2),
                    qty_unit="kg",
                    saving_inr=best.vs_baseline_inr,
                    saving_kg=round(batch.qty_kg, 3),
                    saving_co2e_kg=best.co2e_avoided_kg,
                    lambda_used=lam,
                    confidence=0.85,
                    channel_id=best.channel_id,
                    why=[
                        {"label": "Life left", "value": f"{assessment.rsl_days:.1f} days", "kind": "fact"},
                        {"label": "Best channel", "value": best.name, "kind": "fact"},
                        {"label": "Against disposal", "value": f"₹{best.vs_baseline_inr:,.0f}", "kind": "evidence"},
                        {"label": "Ruled out", "value": f"{len(result.excluded)} channels, reasons shown", "kind": "tradeoff"},
                    ],
                )
            )

        out.sort(key=lambda r: r.saving_inr, reverse=True)
        return out[: self.config.max_recommendations]

    def today(self, lambda_: float | None = None) -> dict:
        result = self.attribution()
        recommendations = self.build_recommendations(lambda_)
        return {
            "date": self.date,
            "outlet_name": self.context.outlet_name,
            "lambda_used": self.objective(lambda_).lambda_,
            "kpis": {
                "kg_at_risk": result.kg_at_risk,
                "value_at_risk_inr": result.value_at_risk_inr,
                "preventable_pct": result.preventable_pct,
            },
            "recommendations": recommendations,
        }

    def impact(self) -> dict:
        backtest = self.session.scalars(
            select(Forecast).where(Forecast.is_backtest == True, Forecast.quantile == 0.5)  # noqa: E712
        ).all()
        actuals = {
            (row.date, row.dish_id): row.qty_portions
            for row in self.session.scalars(select(SalesRecord)).all()
        }
        baseline_lookup = {
            (row.date, row.dish_id): row.qty_portions
            for row in self.session.scalars(select(SalesRecord)).all()
        }

        per_day: dict[dt.date, dict[str, float]] = {}
        errors, baseline_errors = [], []
        for row in backtest:
            actual = actuals.get((row.date, row.dish_id))
            baseline = baseline_lookup.get((row.date - dt.timedelta(days=7), row.dish_id))
            if actual is None or baseline is None:
                continue
            bucket = per_day.setdefault(row.date, {"actual": 0.0, "forecast": 0.0, "baseline": 0.0})
            bucket["actual"] += actual
            bucket["forecast"] += row.value
            bucket["baseline"] += baseline
            errors.append(abs(actual - row.value))
            baseline_errors.append(abs(actual - baseline))

        mae = round(float(np.mean(errors)), 2) if errors else 0.0
        baseline_mae = round(float(np.mean(baseline_errors)), 2) if baseline_errors else 0.0
        shown, accepted = rec.counts(self.session)

        return {
            "date": self.date,
            "series": [
                {
                    "date": day,
                    "actual": round(values["actual"], 1),
                    "forecast": round(values["forecast"], 1),
                    "baseline": round(values["baseline"], 1),
                    "held_out": True,
                }
                for day, values in sorted(per_day.items())
            ],
            "mae": mae,
            "baseline_mae": baseline_mae,
            "improvement_pct": round(100 * (baseline_mae - mae) / baseline_mae, 1) if baseline_mae else 0.0,
            "acceptance_rate": rec.acceptance_rate(self.session),
            "recommendations_shown": shown,
            "recommendations_accepted": accepted,
            "saving_to_date_inr": rec.realised_saving(self.session),
        }
