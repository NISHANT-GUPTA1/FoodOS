"""The objective function. There is exactly one, and this is it.

Every recommendation FoodOS makes — how much to cook, whether to move a tray, where to
send stock that cannot be saved, when to mark down a retail shelf, how big a production
batch should be — is the same expression evaluated over a different action.

    V(a) = recovery(a) − cost(a) − disposal(a) − λ · sustainability(a)

    sustainability(a) = co2e_price · co2e_wasted(a) + waste_externality · kg_wasted(a)

An action is described by what it brings in, what it costs to take, how much food still
ends up wasted after taking it, and what that residue is worth environmentally. Every
horizon fills those fields differently. None of them gets its own formula.

If you ever find yourself writing a second value function, stop. The platform claim — one
optimiser, three action spaces — is either true in this file or it is marketing.

## The newsvendor is not a separate model

For a production decision the action is "make Q portions" and demand D is random:

    E[V(Q)] = p·E[min(Q,D)] − c·Q − d·E[(Q−D)⁺] − λ·s·E[(Q−D)⁺]

Differentiating and setting to zero gives the critical ratio:

    dE/dQ = p·P(D>Q) − c − (d + λ·s)·P(D≤Q) = 0
          ⇒ F(Q*) = (p − c) / (p + d + λ·s)
          ⇒ q*    = Cu / (Cu + Co + λ·s)     where Cu = p − c,  Co = c + d

So :meth:`Objective.critical_ratio` is not an alternative model to :meth:`Objective.value`
— it is the closed-form argmax of it. ``tests/test_engine/test_optimiser.py`` maximises
``value`` numerically over Q and asserts the two agree, which is what keeps this docstring
honest.

Owner: Person B.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable

import numpy as np


@dataclass(frozen=True)
class Prices:
    """The shadow prices λ scales. Loaded from content/costs.yaml at seed time."""

    co2e_price_per_kg: float = 4.50
    waste_externality_per_kg_food: float = 45.00


@dataclass(frozen=True)
class Action:
    """A candidate decision, in the only vocabulary the objective understands.

    All quantities are totals for the whole action, not per unit.

    recovery_inr      money that comes back if this action is taken, net of the channel's
                      own commission, transport and packing
    cost_inr          money spent to take it — ingredients, labour, blanching, freight
    disposal_units    units that still go in a bin afterwards
    wasted_units      units whose embodied impact is NOT avoided; a channel that recovers
                      the food entirely contributes zero here, compost contributes most of it
    """

    kind: str
    ref: str
    label: str
    units: float
    recovery_inr: float = 0.0
    cost_inr: float = 0.0
    disposal_units: float = 0.0
    unit_disposal_cost: float = 0.0
    wasted_units: float = 0.0
    unit_co2e_kg: float = 0.0
    unit_food_kg: float = 0.0
    meta: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Economics:
    """Per-unit economics of a produce-or-not decision. Read straight off the dish."""

    unit_price: float  # p — revenue per unit sold
    unit_cost: float  # c — variable cost per unit made
    unit_disposal: float  # d — cost of binning one unmade-good unit
    unit_co2e_kg: float
    unit_food_kg: float

    @property
    def cu(self) -> float:
        """Cost of under-producing: the contribution margin we fail to earn."""
        return max(0.0, self.unit_price - self.unit_cost)

    @property
    def co(self) -> float:
        """Cost of over-producing: what we spent, plus what it costs to throw away."""
        return max(0.0, self.unit_cost + self.unit_disposal)


class Objective:
    """V(a), and the closed-form optimum of it for a production decision."""

    def __init__(self, lambda_: float, prices: Prices | None = None) -> None:
        self.lambda_ = float(lambda_)
        self.prices = prices or Prices()

    # --- the sustainability term -------------------------------------------

    def sustainability_cost(self, co2e_kg: float, food_kg: float) -> float:
        """Priced damage from food that is wasted, before λ is applied.

        Two terms, because carbon alone at any defensible price is rounding error next to
        an Indian restaurant's contribution margin. The externality term carries land,
        water, nutrient loss and landfill methane. Both constants and the reasoning behind
        them are in content/costs.yaml.
        """
        return (
            self.prices.co2e_price_per_kg * co2e_kg
            + self.prices.waste_externality_per_kg_food * food_kg
        )

    def unit_sustainability(self, econ: Economics) -> float:
        return self.sustainability_cost(econ.unit_co2e_kg, econ.unit_food_kg)

    # --- THE objective ------------------------------------------------------

    def value(self, action: Action) -> float:
        """V(a). Every horizon, every track, every recommendation goes through here."""
        disposal = action.disposal_units * action.unit_disposal_cost
        sustainability = self.sustainability_cost(
            co2e_kg=action.wasted_units * action.unit_co2e_kg,
            food_kg=action.wasted_units * action.unit_food_kg,
        )
        return (
            action.recovery_inr
            - action.cost_inr
            - disposal
            - self.lambda_ * sustainability
        )

    def best(self, actions: Iterable[Action]) -> tuple[Action, float] | None:
        scored = [(a, self.value(a)) for a in actions]
        if not scored:
            return None
        return max(scored, key=lambda pair: pair[1])

    def rank(self, actions: Iterable[Action]) -> list[tuple[Action, float]]:
        return sorted(((a, self.value(a)) for a in actions), key=lambda p: p[1], reverse=True)

    # --- the production decision --------------------------------------------

    def critical_ratio(self, econ: Economics) -> float:
        """q* — the service level that maximises :meth:`value` for a production action.

        Closed form, derived in the module docstring. Not a second model.
        """
        denominator = econ.cu + econ.co + self.lambda_ * self.unit_sustainability(econ)
        if denominator <= 0:
            return 0.0
        return min(1.0, max(0.0, econ.cu / denominator))

    def produce_action(
        self, ref: str, label: str, qty: float, econ: Economics, demand
    ) -> Action:
        """Build the Action for 'make ``qty`` units', given a demand distribution.

        ``demand`` is anything with a ``.quantile(level)`` method — in practice the
        LightGBM :class:`~foodos.models.forecaster.QuantileCurve`.
        """
        sold = expected_sales(demand, qty)
        overage = max(0.0, qty - sold)
        return Action(
            kind="produce",
            ref=ref,
            label=label,
            units=qty,
            recovery_inr=sold * econ.unit_price,
            cost_inr=qty * econ.unit_cost,
            disposal_units=overage,
            unit_disposal_cost=econ.unit_disposal,
            wasted_units=overage,
            unit_co2e_kg=econ.unit_co2e_kg,
            unit_food_kg=econ.unit_food_kg,
            meta={"expected_sold": sold, "expected_overage": overage},
        )


# --- demand helpers ----------------------------------------------------------

_GRID = np.linspace(0.005, 0.995, 199)


def expected_sales(demand, qty: float) -> float:
    """E[min(Q, D)] by integrating the quantile function.

    Numerical rather than closed-form on purpose: the forecast is an interpolated
    empirical quantile curve, not a named distribution, and pretending otherwise would
    make the optimiser's answer depend on a normality assumption nobody checked.
    """
    draws = np.array([demand.quantile(level) for level in _GRID])
    return float(np.mean(np.minimum(draws, qty)))


def expected_overage(demand, qty: float) -> float:
    return max(0.0, qty - expected_sales(demand, qty))


def optimal_quantity(objective: Objective, econ: Economics, demand) -> float:
    """The recommended production quantity: the forecast, read at the critical ratio."""
    return float(demand.quantile(objective.critical_ratio(econ)))


def maximise_numerically(
    objective: Objective, econ: Economics, demand, *, lo: float = 0.0, hi: float | None = None
) -> float:
    """Brute-force argmax of :meth:`Objective.value`. Used by tests to police the closed form.

    Deliberately dumb. A clever optimiser here could share a bug with the thing it checks.
    """
    hi = hi if hi is not None else max(1.0, demand.quantile(0.999) * 1.5)
    grid = np.linspace(lo, hi, 1200)
    values = [
        objective.value(objective.produce_action("test", "test", float(q), econ, demand))
        for q in grid
    ]
    return float(grid[int(np.argmax(values))])
