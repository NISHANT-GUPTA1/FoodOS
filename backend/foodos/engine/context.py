"""DecisionContext — everything the objective function needs that is not
attached to a single action.

Carrying this explicitly (rather than reading globals) is what makes the
lambda slider work end to end: the API puts a lambda on the context, and every
downstream number moves.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date

from foodos.config import settings


@dataclass(frozen=True)
class DecisionContext:
    today: date
    site_id: int

    # objective weights
    lam: float = settings.lam
    mu: float = settings.mu

    # prices and default costs
    waste_aversion_per_kg: float = settings.waste_aversion_per_kg
    co2e_price_per_kg: float = settings.co2e_price_per_kg
    co2e_kg_per_kg_food: float = settings.co2e_kg_per_kg_food
    disposal_cost_per_kg: float = settings.disposal_cost_per_kg
    social_value_per_kg_donated: float = settings.social_value_per_kg_donated

    # feasibility
    handling_margin_hours: float = settings.handling_margin_hours
    min_recommendation_value: float = settings.min_recommendation_value

    def with_lambda(self, lam: float | None) -> "DecisionContext":
        return self if lam is None else replace(self, lam=float(lam))

    def sustainability_value_per_kg(self) -> float:
        """Rupee value of keeping one kilogram of food out of the bin."""
        return self.lam * self.waste_aversion_per_kg


def default_context(site_id: int, today: date | None = None) -> DecisionContext:
    return DecisionContext(today=today or settings.demo_today, site_id=site_id)


def co2e_per_unit(product, ctx: DecisionContext) -> float:
    """CO2e in kg for one unit of this product.

    A supplies `co2e_kg_per_uom` per product and that always wins. The global
    intensity is a fallback for products A has not scored, and is applied to
    the portion weight rather than the unit count so the arithmetic stays
    dimensionally honest.
    """
    per_uom = getattr(product, "co2e_kg_per_uom", None)
    if per_uom:
        return float(per_uom)
    weight = max(getattr(product, "unit_weight_kg", 1.0) or 1.0, 1e-6)
    return ctx.co2e_kg_per_kg_food * weight
