"""Waste risk — derived, not modelled.

There is no risk model to train or explain. Risk falls straight out of two
things the system already has: the demand distribution, and the remaining
shelf life. That is a deliberate design choice — one fewer black box to defend.

    window          = the RSL window, in days
    consumption     = demand accumulated over that window
    qty_at_risk     = qty_on_hand - E[min(consumption, qty_on_hand)]
    P(waste)        = P(consumption < qty_on_hand)
    value_at_risk   = qty_at_risk * unit_cost
"""

from __future__ import annotations

from dataclasses import dataclass

from foodos.engine.distribution import DemandDistribution, convolve_days


@dataclass(frozen=True)
class BatchRisk:
    batch_id: int
    product_id: int
    label: str
    category: str
    uom: str

    qty_on_hand: float
    qty_kg: float
    rsl_days: float
    rsl_explanation: str

    expected_consumption: float
    qty_at_risk: float
    qty_at_risk_kg: float
    waste_probability: float
    value_at_risk: float

    unit_cost: float
    unit_price: float
    intake_grade: float
    storage_zone: str | None = None

    #: The upstream batch code this lot came in on, when it came in on one.
    #: Carried through the risk row rather than looked up per screen so that
    #: every surface built on `BatchRisk` — the Ledger, the retail track, the
    #: rescue waterfall — names the same identity without any of them joining
    #: back to the agri side. `None` for stock with no passport, which is most
    #: of what a kitchen buys.
    batch_code: str | None = None
    #: Where it was grown or aggregated. One line, for the provenance chip.
    origin: str | None = None

    @property
    def severity(self) -> str:
        """Traffic light for the Ledger screen.

        Severity is *urgency*, so it needs both dimensions. A slow-moving sack
        of potatoes with three weeks of life left has a high waste probability
        and no urgency whatsoever; flagging it red would train the chef to
        ignore the colour.
        """
        p, days = self.waste_probability, self.rsl_days
        if p >= 0.5 and days <= 2.0:
            return "critical"
        if p >= 0.4 and days <= 4.0:
            return "high"
        if p >= 0.25 and days <= 8.0:
            return "medium"
        return "low"

    @property
    def recover_basis(self) -> float:
        """Rupee value of one unit if it is used rather than binned.

        Ingredients carry no sale price of their own, so their recoverable
        value is the cost that would otherwise be written off.
        """
        return self.unit_price if self.unit_price > 0 else self.unit_cost


def assess(
    *,
    batch_id: int,
    product_id: int,
    label: str,
    category: str,
    uom: str,
    qty_on_hand: float,
    unit_weight_kg: float,
    rsl_days: float,
    rsl_explanation: str,
    daily_demand: DemandDistribution,
    unit_cost: float,
    unit_price: float,
    intake_grade: float = 1.0,
    storage_zone: str | None = None,
    batch_code: str | None = None,
    origin: str | None = None,
) -> BatchRisk:
    """Score one batch. Pure function — no database, no side effects."""
    rsl_days = max(float(rsl_days), 0.0)
    window = convolve_days(daily_demand, rsl_days)

    expected_consumption = window.expected_sales(qty_on_hand)
    qty_at_risk = max(qty_on_hand - expected_consumption, 0.0)
    waste_probability = window.cdf(qty_on_hand)

    return BatchRisk(
        batch_id=batch_id,
        product_id=product_id,
        label=label,
        category=category,
        uom=uom,
        qty_on_hand=round(qty_on_hand, 3),
        qty_kg=round(qty_on_hand * unit_weight_kg, 3),
        rsl_days=round(rsl_days, 2),
        rsl_explanation=rsl_explanation,
        expected_consumption=round(expected_consumption, 3),
        qty_at_risk=round(qty_at_risk, 3),
        qty_at_risk_kg=round(qty_at_risk * unit_weight_kg, 3),
        waste_probability=round(waste_probability, 4),
        value_at_risk=round(qty_at_risk * unit_cost, 2),
        unit_cost=unit_cost,
        unit_price=unit_price,
        intake_grade=intake_grade,
        storage_zone=storage_zone,
        batch_code=batch_code,
        origin=origin,
    )
