"""Savings simulator — the plan swept across the full range of λ.

Answers the question a judge and a finance director both ask: *what does this actually
cost me, and what do I get for it?* Sweeping λ turns an abstract weight into a curve with
rupees on one axis and kilograms on the other.

Owner: Person B.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from sqlalchemy.orm import Session

from ..models.forecaster import QuantileCurve
from .optimiser import Objective, Prices
from .prevent import build_plan


@dataclass(frozen=True)
class SimulationPoint:
    lambda_value: float
    saving_inr: float
    saving_kg: float
    saving_co2e_kg: float
    portions_delta: float


def sweep(
    session: Session,
    *,
    date: dt.date,
    curves: dict[str, QuantileCurve],
    prices: Prices,
    labour_cost: float,
    steps: int = 11,
) -> list[SimulationPoint]:
    """Rebuild the whole plan at each λ. No shortcuts, no interpolation.

    Eleven full re-optimisations is cheap enough at this scale, and the alternative —
    computing the curve analytically — would be a second implementation of the objective,
    which is the one thing this codebase is not allowed to have.
    """
    points: list[SimulationPoint] = []
    for step in range(steps):
        lambda_ = step / (steps - 1)
        plan = build_plan(
            session,
            date=date,
            curves=curves,
            objective=Objective(lambda_, prices),
            labour_cost=labour_cost,
        )
        points.append(
            SimulationPoint(
                lambda_value=round(lambda_, 2),
                saving_inr=plan.saving_inr,
                saving_kg=plan.saving_kg,
                saving_co2e_kg=plan.saving_co2e_kg,
                portions_delta=plan.portions_delta,
            )
        )
    return points


def recommend_lambda(points: list[SimulationPoint]) -> float:
    """The knee: the last λ before rupees start falling away faster than carbon improves.

    Deliberately simple and deliberately explainable. An operator asked to trust a number
    they cannot reconstruct will pick zero and leave the slider alone forever.
    """
    if not points:
        return 0.0

    best_lambda, best_score = points[0].lambda_value, float("-inf")
    top_inr = max(p.saving_inr for p in points) or 1.0
    top_co2e = max(p.saving_co2e_kg for p in points) or 1.0

    for point in points:
        score = (point.saving_inr / top_inr) + (point.saving_co2e_kg / top_co2e)
        if score > best_score:
            best_lambda, best_score = point.lambda_value, score
    return best_lambda
