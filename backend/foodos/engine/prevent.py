"""PREVENT — how much to make, and the purchase list that follows from it.

Two jobs:

1. Run the newsvendor for every dish at the requested λ and produce the plan.
2. Explode that plan through the recipe bill of materials into a purchase list, because a
   plan expressed in portions is not something anyone can order against.

The BOM explosion is the only place ``qty_kg / prep_yield`` appears. That division is what
makes 63 portions of Gobi Manchurian into 11 kg of whole cauliflower rather than 6.4 kg of
florets, and getting it backwards would understate every purchase in the system.

Owner: Person B.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.forecaster import QuantileCurve
from ..schema import Product, ProductionRecord, Recipe
from .optimiser import Economics, Objective, expected_sales


@dataclass
class PlanLine:
    dish_id: str
    dish_name: str
    station: str | None
    current_qty: float
    recommended_qty: float
    service_level: float
    saving_inr: float
    saving_kg: float
    saving_co2e_kg: float
    expected_sold: float

    @property
    def delta(self) -> float:
        return round(self.recommended_qty - self.current_qty, 1)


@dataclass
class Plan:
    date: dt.date
    lambda_used: float
    lines: list[PlanLine] = field(default_factory=list)

    @property
    def portions_delta(self) -> float:
        return round(sum(line.delta for line in self.lines), 1)

    @property
    def saving_inr(self) -> float:
        return round(sum(line.saving_inr for line in self.lines), 2)

    @property
    def saving_kg(self) -> float:
        return round(sum(line.saving_kg for line in self.lines), 2)

    @property
    def saving_co2e_kg(self) -> float:
        return round(sum(line.saving_co2e_kg for line in self.lines), 2)


def economics_for(dish: Product, labour_cost: float) -> Economics:
    """Per-unit economics straight off the dish. No figure is invented here."""
    return Economics(
        unit_price=float(dish.price or 0.0),
        unit_cost=float(dish.food_cost_per_portion or 0.0) + labour_cost,
        unit_disposal=float(dish.disposal_cost_per_portion or 0.0),
        unit_co2e_kg=float(dish.co2e_kg_per_portion or 0.0),
        unit_food_kg=float(dish.input_kg_per_portion or 0.0),
    )


def current_plan_qty(session: Session, dish_id: str, date: dt.date) -> float:
    """What the prep sheet says today. Falls back to the most recent sheet we have."""
    row = session.scalar(
        select(ProductionRecord)
        .where(ProductionRecord.dish_id == dish_id, ProductionRecord.date < date)
        .order_by(ProductionRecord.date.desc())
        .limit(1)
    )
    return float(row.planned_portions) if row else 0.0


def build_plan(
    session: Session,
    *,
    date: dt.date,
    curves: dict[str, QuantileCurve],
    objective: Objective,
    labour_cost: float,
) -> Plan:
    """The production plan for ``date`` at the objective's λ.

    The saving claimed for each line is the honest one: V(recommended) − V(current), both
    evaluated by the same objective on the same demand curve. It is not "the cost of the
    portions we cut", which would count a saving on portions that would have sold.
    """
    plan = Plan(date=date, lambda_used=objective.lambda_)

    dishes = session.scalars(select(Product).where(Product.kind == "dish")).all()
    for dish in sorted(dishes, key=lambda d: d.name):
        curve = curves.get(dish.id)
        if curve is None:
            continue

        econ = economics_for(dish, labour_cost)
        service_level = objective.critical_ratio(econ)
        recommended = round(curve.quantile(service_level))
        current = current_plan_qty(session, dish.id, date)

        action_now = objective.produce_action(dish.id, dish.name, current, econ, curve)
        action_rec = objective.produce_action(dish.id, dish.name, recommended, econ, curve)

        saving_inr = objective.value(action_rec) - objective.value(action_now)
        overage_now = action_now.meta["expected_overage"]
        overage_rec = action_rec.meta["expected_overage"]
        waste_avoided = max(0.0, overage_now - overage_rec)

        plan.lines.append(
            PlanLine(
                dish_id=dish.id,
                dish_name=dish.name,
                station=dish.station,
                current_qty=round(current, 1),
                recommended_qty=float(recommended),
                service_level=round(service_level, 3),
                saving_inr=round(saving_inr, 2),
                saving_kg=round(waste_avoided * econ.unit_food_kg, 3),
                saving_co2e_kg=round(waste_avoided * econ.unit_co2e_kg, 3),
                expected_sold=round(expected_sales(curve, recommended), 1),
            )
        )

    plan.lines.sort(key=lambda line: line.saving_inr, reverse=True)
    return plan


# --- bill of materials -------------------------------------------------------

@dataclass
class PurchaseLine:
    ingredient_id: str
    ingredient_name: str
    prepped_kg: float
    purchase_kg: float
    prep_yield: float
    cost_inr: float
    co2e_kg: float

    @property
    def trim_kg(self) -> float:
        """What the bin gets before anything is even cooked."""
        return round(self.purchase_kg - self.prepped_kg, 3)


def explode_bom(session: Session, quantities: dict[str, float]) -> list[PurchaseLine]:
    """Turn a plan in portions into a purchase list in kilograms.

        purchase_kg = Σ (portions × recipe_qty_kg) / prep_yield

    Recipe lines are stated in prepped weight. The division by yield is the whole point of
    this function and the reason ``yield_table.yaml`` exists.
    """
    totals: dict[str, float] = {}

    for dish_id, portions in quantities.items():
        if portions <= 0:
            continue
        recipe = session.scalar(select(Recipe).where(Recipe.dish_id == dish_id))
        if recipe is None:
            continue
        for line in recipe.lines:
            totals[line.ingredient_id] = totals.get(line.ingredient_id, 0.0) + line.qty_kg * portions

    out: list[PurchaseLine] = []
    for ingredient_id, prepped_kg in totals.items():
        ingredient = session.get(Product, ingredient_id)
        if ingredient is None:
            continue
        prep_yield = float(ingredient.prep_yield or 1.0)
        purchase_kg = prepped_kg / prep_yield
        out.append(
            PurchaseLine(
                ingredient_id=ingredient_id,
                ingredient_name=ingredient.name,
                prepped_kg=round(prepped_kg, 3),
                purchase_kg=round(purchase_kg, 3),
                prep_yield=prep_yield,
                cost_inr=round(purchase_kg * float(ingredient.unit_cost_per_kg or 0.0), 2),
                co2e_kg=round(purchase_kg * float(ingredient.co2e_kg_per_kg or 0.0), 3),
            )
        )

    out.sort(key=lambda line: line.cost_inr, reverse=True)
    return out
