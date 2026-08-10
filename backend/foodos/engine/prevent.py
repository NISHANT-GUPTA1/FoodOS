"""PREVENT — the quantity decision, before the food exists.

The newsvendor fractile is not a separate objective function. It is the
closed-form maximiser of `optimiser.score()` over the quantity action space,
and `test_prevent.py` asserts that numerically against a grid search.

    V(Q) = p*E[min(D,Q)] - c*Q - d*E[(Q-D)+] + lambda*a*w*(L_base - L(Q))

    dV/dQ = 0  =>  (p - c) = F(Q) * (p + d + lambda*a*w)

    C_u = p - c                          margin lost on a stockout
    C_o = c + d + lambda*a*w             cost of one unsold unit
    q*  = C_u / (C_u + C_o)
    Q*  = F^-1(q*)

    where a = waste_aversion_per_kg and w = the portion weight in kilograms.

A kitchen habitually preps at roughly q = 0.92 because running out is loud and
waste is silent. The gap between 0.92 and q* is the waste, and it is a pricing
error rather than carelessness.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from foodos.engine.actions import Action
from foodos.engine.context import DecisionContext, co2e_per_unit
from foodos.engine.distribution import DemandDistribution
from foodos.schema.enums import ActionType, Confidence, Horizon
from foodos.schema.tables import Product

# The service level a kitchen or store implicitly runs at today. Used only to
# derive the baseline when no historical production figure is available.
HABITUAL_SERVICE_LEVEL = 0.92


@dataclass(frozen=True)
class Economics:
    """The cost pair, spelled out so every rupee is traceable."""

    unit_price: float
    unit_cost: float
    disposal_per_unit: float
    waste_penalty_per_unit: float
    cu: float
    co_base: float
    lam: float

    @property
    def co_effective(self) -> float:
        return self.co_base + self.lam * self.waste_penalty_per_unit

    @property
    def q_star(self) -> float:
        denom = self.cu + self.co_effective
        return float(np.clip(self.cu / denom, 1e-6, 1 - 1e-6)) if denom > 0 else 0.5

    def as_facts(self) -> dict:
        return {
            "unit_price": round(self.unit_price, 2),
            "unit_cost": round(self.unit_cost, 2),
            "disposal_per_unit": round(self.disposal_per_unit, 2),
            "waste_penalty_per_unit": round(self.waste_penalty_per_unit, 2),
            "cu": round(self.cu, 2),
            "co": round(self.co_base, 2),
            "co_effective": round(self.co_effective, 2),
            "lambda": round(self.lam, 3),
            "q_star": round(self.q_star, 4),
            "habitual_service_level": HABITUAL_SERVICE_LEVEL,
        }


def economics(product: Product, ctx: DecisionContext) -> Economics:
    weight = max(product.unit_weight_kg, 1e-6)
    disposal = ctx.disposal_cost_per_kg * weight
    waste_penalty = ctx.waste_aversion_per_kg * weight
    return Economics(
        unit_price=product.unit_price,
        unit_cost=product.unit_cost,
        disposal_per_unit=disposal,
        waste_penalty_per_unit=waste_penalty,
        cu=max(product.unit_price - product.unit_cost, 0.0),
        co_base=product.unit_cost + disposal,
        lam=ctx.lam,
    )


def optimal_quantity(dist: DemandDistribution, econ: Economics) -> tuple[float, float]:
    """Closed-form newsvendor. Returns (q*, Q*)."""
    q_star = econ.q_star
    return q_star, float(dist.quantile(q_star))


def build_quantity_action(
    product: Product,
    dist: DemandDistribution,
    qty: float,
    baseline_qty: float,
    ctx: DecisionContext,
    action_type: ActionType = ActionType.SET_PREP_QTY,
) -> Action:
    """Wrap a candidate quantity as a scorable Action.

    Used by the planner for the recommended quantity, and by the test suite to
    grid-search V(Q) and confirm the closed form really is its argmax.

    `kg_food_saved` is deliberately *signed* here: preparing more than the
    baseline destroys food, and the objective function must charge for it.
    Clamping at zero would make the lambda term one-directional and the slider
    would stop moving the plan.
    """
    econ = economics(product, ctx)
    weight = max(product.unit_weight_kg, 1e-6)
    sold = dist.expected_sales(qty)
    leftover = dist.expected_leftover(qty)
    baseline_leftover = dist.expected_leftover(baseline_qty)
    kg_saved = (baseline_leftover - leftover) * weight

    return Action(
        action_type=action_type,
        horizon=Horizon.PREVENT,
        label=f"Prepare {qty:.0f} {product.uom}",
        subject_type="dish" if product.is_dish else "sku",
        subject_id=product.id,
        subject_label=product.name,
        qty=qty,
        qty_kg=qty * weight,
        baseline_qty=baseline_qty,
        recovered_value=econ.unit_price * sold,
        cost=econ.unit_cost * qty + econ.disposal_per_unit * leftover,
        loss_probability=0.0,
        value_at_risk=0.0,
        kg_food_saved=kg_saved,
        co2e_saved_kg=(baseline_leftover - leftover) * co2e_per_unit(product, ctx),
        params={"qty": qty},
        facts={
            "expected_sales": round(sold, 2),
            "expected_leftover": round(leftover, 2),
            "baseline_leftover": round(baseline_leftover, 2),
        },
    )


@dataclass
class PreventPlan:
    product_id: int
    label: str
    uom: str
    baseline_qty: float
    recommended_qty: float
    q_star: float
    forecast_median: float
    forecast_low: float
    forecast_high: float
    expected_waste_baseline_kg: float
    expected_waste_recommended_kg: float
    saving_kg: float
    saving_money: float
    saving_co2e: float
    confidence: Confidence
    economics: dict = field(default_factory=dict)
    facts: dict = field(default_factory=dict)


def saving_between(
    product: Product,
    dist: DemandDistribution,
    from_qty: float,
    to_qty: float,
    ctx: DecisionContext,
) -> tuple[float, float, float]:
    """Expected (kg, money, co2e) saved by moving from one quantity to another.

    The money term is not simply "cost of the units you no longer make". It
    nets off the margin on sales you give up by making fewer, which is what
    stops the recommendation from degenerating into "always prepare less".

    Lives here, and only here, so the production track cannot drift from the
    kitchen's arithmetic.
    """
    econ = economics(product, ctx)
    weight = max(product.unit_weight_kg, 1e-6)

    leftover_from = dist.expected_leftover(from_qty)
    leftover_to = dist.expected_leftover(to_qty)
    units_saved = leftover_from - leftover_to

    lost_margin = econ.cu * max(
        dist.expected_sales(from_qty) - dist.expected_sales(to_qty), 0.0
    )
    money = units_saved * (econ.unit_cost + econ.disposal_per_unit) - lost_margin
    kg = units_saved * weight
    co2e = units_saved * co2e_per_unit(product, ctx)
    return round(kg, 2), round(money, 2), round(co2e, 2)


def _confidence(dist: DemandDistribution) -> Confidence:
    width = dist.relative_width
    if width <= 0.45:
        return Confidence.HIGH
    if width <= 0.85:
        return Confidence.MEDIUM
    return Confidence.LOW


def plan_quantity(
    product: Product,
    dist: DemandDistribution,
    ctx: DecisionContext,
    baseline_qty: float | None = None,
) -> PreventPlan:
    """The PREVENT recommendation for one product on one day."""
    econ = economics(product, ctx)
    q_star, recommended = optimal_quantity(dist, econ)
    recommended = float(max(0.0, round(recommended)))

    if baseline_qty is None:
        baseline_qty = float(round(dist.quantile(HABITUAL_SERVICE_LEVEL)))
    baseline_qty = float(max(baseline_qty, 0.0))

    weight = max(product.unit_weight_kg, 1e-6)
    leftover_base = dist.expected_leftover(baseline_qty)
    leftover_rec = dist.expected_leftover(recommended)

    saving_kg, saving_money, saving_co2e = saving_between(
        product, dist, baseline_qty, recommended, ctx
    )
    lost_margin = econ.cu * max(
        dist.expected_sales(baseline_qty) - dist.expected_sales(recommended), 0.0
    )

    lo, hi = dist.interval()
    return PreventPlan(
        product_id=product.id,
        label=product.name,
        uom=product.uom,
        baseline_qty=baseline_qty,
        recommended_qty=recommended,
        q_star=q_star,
        forecast_median=round(dist.quantile(0.50), 1),
        forecast_low=round(lo, 1),
        forecast_high=round(hi, 1),
        expected_waste_baseline_kg=round(leftover_base * weight, 2),
        expected_waste_recommended_kg=round(leftover_rec * weight, 2),
        saving_kg=saving_kg,
        saving_money=saving_money,
        saving_co2e=saving_co2e,
        confidence=_confidence(dist),
        economics=econ.as_facts(),
        facts={
            "expected_leftover_baseline": round(leftover_base, 2),
            "expected_leftover_recommended": round(leftover_rec, 2),
            "lost_margin_on_extra_sales": round(lost_margin, 2),
            "interval_relative_width": round(dist.relative_width, 3),
        },
    )


def value_of_quantity(
    product: Product,
    dist: DemandDistribution,
    qty: float,
    baseline_qty: float,
    ctx: DecisionContext,
) -> float:
    """V(Q) evaluated through the one objective function.

    Exists so the test suite can grid-search the objective and confirm the
    closed-form fractile really is its argmax.
    """
    from foodos.engine.optimiser import score  # local import: avoids a cycle

    action = build_quantity_action(product, dist, qty, baseline_qty, ctx)
    return score(action, ctx).value


def explode_to_ingredients(
    plans: list[PreventPlan], recipes: dict[int, list[tuple[int, str, float, float]]]
) -> dict[int, dict]:
    """Dish plan -> ingredient requirement, through the recipe BOM.

    `recipes` maps product_id -> [(ingredient_id, ingredient_name, qty_per_unit,
    standard_yield_pct)]. Requirement is grossed up by the standard yield, so a
    58%-yield cauliflower needs 1/0.58 kg purchased per kg served.
    """
    out: dict[int, dict] = {}
    for plan in plans:
        for ing_id, ing_name, qty_per_unit, std_yield in recipes.get(
            plan.product_id, []
        ):
            yld = std_yield if std_yield > 1e-6 else 1.0
            need_rec = plan.recommended_qty * qty_per_unit / yld
            need_base = plan.baseline_qty * qty_per_unit / yld
            row = out.setdefault(
                ing_id,
                {
                    "ingredient_id": ing_id,
                    "ingredient": ing_name,
                    "required_kg": 0.0,
                    "baseline_kg": 0.0,
                    "standard_yield_pct": round(yld, 3),
                    "driven_by": [],
                },
            )
            row["required_kg"] += need_rec
            row["baseline_kg"] += need_base
            row["driven_by"].append(plan.label)

    for row in out.values():
        row["required_kg"] = round(row["required_kg"], 3)
        row["baseline_kg"] = round(row["baseline_kg"], 3)
        row["saved_kg"] = round(row["baseline_kg"] - row["required_kg"], 3)
    return out
