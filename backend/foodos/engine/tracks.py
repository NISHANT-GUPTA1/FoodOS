"""Track 2 (retail) and Track 3 (production) — same optimiser, different action set.

This module is the proof that the platform claim is real, and the whole point is that it
is short. It imports :class:`~foodos.engine.optimiser.Objective` and builds
:class:`~foodos.engine.optimiser.Action` objects with different fields in them. There is no
second value function here, no third, and no "retail engine".

A retail shelf and a kitchen have the same problem stated in different nouns: a perishable
asset, a decision window, and a cost of being wrong in both directions. Markdown timing is
a newsvendor. Batch sizing is a newsvendor. The arithmetic does not care that one of them
involves a wok.

Owner: Person B.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from .optimiser import Action, Economics, Objective

# --- Track 2: retail markdown ------------------------------------------------

#: Discount ladder a store can apply, and the sell-through each buys. Real supermarkets
#: run exactly this shape of table; the numbers here are illustrative.
MARKDOWN_LADDER = ((0.00, 0.55), (0.15, 0.72), (0.30, 0.86), (0.50, 0.96))


@dataclass(frozen=True)
class ShelfUnit:
    sku: str
    name: str
    units: int
    unit_price: float
    unit_cost: float
    hours_to_expiry: float
    unit_co2e_kg: float
    unit_food_kg: float


def markdown_actions(unit: ShelfUnit) -> list[Action]:
    """One action per rung of the discount ladder. Unsold stock is written off."""
    actions = []
    for discount, sell_through in MARKDOWN_LADDER:
        sold = unit.units * sell_through
        unsold = unit.units - sold
        actions.append(
            Action(
                kind="markdown",
                ref=f"{unit.sku}:{discount:.2f}",
                label=f"{int(discount * 100)}% off" if discount else "No markdown",
                units=float(unit.units),
                recovery_inr=sold * unit.unit_price * (1 - discount),
                cost_inr=unit.units * unit.unit_cost,
                disposal_units=unsold,
                unit_disposal_cost=8.0,
                wasted_units=unsold,
                unit_co2e_kg=unit.unit_co2e_kg,
                unit_food_kg=unit.unit_food_kg,
                meta={"discount": discount, "sell_through": sell_through},
            )
        )
    return actions


def best_markdown(objective: Objective, unit: ShelfUnit) -> tuple[Action, float]:
    """The same ``objective.best`` the kitchen uses. Note the absence of new maths."""
    ranked = objective.rank(markdown_actions(unit))
    return ranked[0]


# --- Track 3: production batch sizing ----------------------------------------

@dataclass(frozen=True)
class ProductionLine:
    sku: str
    name: str
    unit_price: float
    unit_cost: float
    unit_disposal: float
    unit_co2e_kg: float
    unit_food_kg: float
    changeover_cost: float
    min_batch: int
    batch_multiple: int


def batch_actions(line: ProductionLine, demand, max_batches: int = 8) -> list[Action]:
    """Candidate batch sizes. Changeover cost is what stops the answer being 'one big run'."""
    from .optimiser import expected_sales

    actions = []
    for n in range(1, max_batches + 1):
        qty = line.min_batch + (n - 1) * line.batch_multiple
        sold = expected_sales(demand, qty)
        overage = max(0.0, qty - sold)
        actions.append(
            Action(
                kind="batch",
                ref=f"{line.sku}:{qty}",
                label=f"Run {qty} units",
                units=float(qty),
                recovery_inr=sold * line.unit_price,
                cost_inr=qty * line.unit_cost + line.changeover_cost,
                disposal_units=overage,
                unit_disposal_cost=line.unit_disposal,
                wasted_units=overage,
                unit_co2e_kg=line.unit_co2e_kg,
                unit_food_kg=line.unit_food_kg,
                meta={"qty": qty, "expected_sold": round(sold, 1)},
            )
        )
    return actions


def best_batch(objective: Objective, line: ProductionLine, demand) -> tuple[Action, float]:
    return objective.rank(batch_actions(line, demand))[0]


# --- demo fixtures for the stub screens --------------------------------------

class _FixedCurve:
    """A tiny stand-in demand distribution for the track stubs, which have no history."""

    def __init__(self, median: float, spread: float) -> None:
        self.median = median
        self.spread = spread

    def quantile(self, level: float) -> float:
        import math

        # Normal inverse CDF via the error function — no scipy on the approved stack.
        level = min(max(level, 1e-4), 1 - 1e-4)
        z = math.sqrt(2) * _erfinv(2 * level - 1)
        return max(0.0, self.median + z * self.spread)


def _erfinv(x: float) -> float:
    """Winitzki's approximation. Accurate to about 2e-3, which is far inside our tolerance."""
    import math

    a = 0.147
    ln = math.log(1 - x * x)
    term = 2 / (math.pi * a) + ln / 2
    return math.copysign(math.sqrt(math.sqrt(term * term - ln / a) - term), x)


RETAIL_SHELF = [
    ShelfUnit("SKU-2201", "Fresh paneer 200 g", 34, 96.0, 68.0, 26.0, 2.20, 0.20),
    ShelfUnit("SKU-2208", "Cut fruit bowl 250 g", 22, 129.0, 74.0, 9.0, 0.42, 0.25),
    ShelfUnit("SKU-2214", "Curd 400 g", 51, 62.0, 40.0, 62.0, 1.40, 0.40),
    ShelfUnit("SKU-2231", "Chicken mince 500 g", 18, 245.0, 168.0, 20.0, 3.45, 0.50),
]

PRODUCTION_LINES = [
    (ProductionLine("PL-14", "Paneer butter masala, 300 g retort", 149.0, 82.0, 6.0, 2.07, 0.30, 4200.0, 400, 200), 980.0, 220.0),
    (ProductionLine("PL-22", "Dal makhani, 300 g retort", 119.0, 51.0, 5.0, 0.68, 0.28, 3800.0, 400, 200), 1450.0, 260.0),
    (ProductionLine("PL-31", "Chicken curry, 300 g retort", 169.0, 104.0, 7.0, 2.09, 0.32, 4600.0, 300, 150), 720.0, 210.0),
]


def retail_recommendations(objective: Objective, date: dt.date) -> list[dict]:
    """Track 2, end to end, in a dozen lines. That is the argument."""
    out = []
    for unit in RETAIL_SHELF:
        best, value = best_markdown(objective, unit)
        do_nothing = next(a for a in markdown_actions(unit) if a.meta["discount"] == 0.0)
        saving = value - objective.value(do_nothing)
        unsold = unit.units * (1 - best.meta["sell_through"])
        out.append(
            {
                "subject_id": unit.sku,
                "subject_name": unit.name,
                "title": f"{best.label} on {unit.name}",
                "current_qty": 0.0,
                "recommended_qty": round(best.meta["discount"] * 100),
                "qty_unit": "% off",
                "saving_inr": round(saving, 2),
                "saving_kg": round((unit.units - unsold) * unit.unit_food_kg, 2),
                "saving_co2e_kg": round((unit.units - unsold) * unit.unit_co2e_kg, 2),
                "why": [
                    {"label": "Hours to expiry", "value": f"{unit.hours_to_expiry:g} h", "kind": "fact"},
                    {"label": "Expected sell-through", "value": f"{best.meta['sell_through'] * 100:.0f}%", "kind": "fact"},
                    {"label": "Units on shelf", "value": str(unit.units), "kind": "fact"},
                    {"label": "Same objective", "value": "V(a) with the kitchen's λ", "kind": "tradeoff"},
                ],
            }
        )
    out.sort(key=lambda r: r["saving_inr"], reverse=True)
    return out


def production_recommendations(objective: Objective, date: dt.date) -> list[dict]:
    """Track 3, end to end. Also a dozen lines."""
    out = []
    for line, median, spread in PRODUCTION_LINES:
        demand = _FixedCurve(median, spread)
        best, value = best_batch(objective, line, demand)
        largest = batch_actions(line, demand)[-1]
        saving = value - objective.value(largest)
        out.append(
            {
                "subject_id": line.sku,
                "subject_name": line.name,
                "title": f"Run {best.meta['qty']} units of {line.name}",
                "current_qty": float(largest.meta["qty"]),
                "recommended_qty": float(best.meta["qty"]),
                "qty_unit": "units",
                "saving_inr": round(saving, 2),
                "saving_kg": round((largest.wasted_units - best.wasted_units) * line.unit_food_kg, 2),
                "saving_co2e_kg": round((largest.wasted_units - best.wasted_units) * line.unit_co2e_kg, 2),
                "why": [
                    {"label": "Forecast demand", "value": f"{median:.0f} units", "kind": "fact"},
                    {"label": "Expected sold", "value": f"{best.meta['expected_sold']:g} units", "kind": "fact"},
                    {"label": "Changeover cost", "value": f"₹{line.changeover_cost:,.0f}", "kind": "tradeoff"},
                    {"label": "Same objective", "value": "V(a) with the kitchen's λ", "kind": "tradeoff"},
                ],
            }
        )
    out.sort(key=lambda r: r["saving_inr"], reverse=True)
    return out
