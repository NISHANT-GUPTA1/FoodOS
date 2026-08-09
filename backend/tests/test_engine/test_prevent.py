"""PREVENT — and the test that keeps the architecture claim honest.

`test_closed_form_is_the_argmax_of_the_objective` is the important one. It
grid-searches V(Q) through `optimiser.score()` and asserts the newsvendor
fractile lands on the same quantity. That is what lets the pitch say "one
objective function, three action spaces" without it being marketing.
"""

from __future__ import annotations

import numpy as np
import pytest

from foodos.engine import prevent
from foodos.engine.distribution import DemandDistribution
from foodos.engine.optimiser import score
from foodos.schema.tables import Product


def _product(**overrides) -> Product:
    defaults = dict(
        id=1,
        org_id=1,
        sku="D-BIR",
        name="Chicken Biryani",
        category="prepared_dish",
        uom="portion",
        unit_cost=92.0,
        unit_price=278.0,
        unit_weight_kg=0.45,
        is_dish=True,
    )
    defaults.update(overrides)
    return Product(**defaults)


def _dist(mean=60.0, sd=9.0) -> DemandDistribution:
    ps = [0.10, 0.25, 0.50, 0.66, 0.75, 0.90]
    from math import erf, sqrt

    def ppf(p: float) -> float:
        lo, hi = -6.0, 6.0
        for _ in range(200):
            mid = (lo + hi) / 2
            if 0.5 * (1 + erf(mid / sqrt(2))) < p:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2

    return DemandDistribution.from_quantiles(*[mean + sd * ppf(p) for p in ps])


def test_critical_fractile_matches_the_cost_pair(ctx):
    econ = prevent.economics(_product(), ctx)
    assert econ.cu == pytest.approx(186.0)
    expected = econ.cu / (econ.cu + econ.co_effective)
    assert econ.q_star == pytest.approx(expected, rel=1e-9)
    # The documented worked example: roughly a 0.66 service level.
    assert 0.63 < econ.q_star < 0.69


def test_closed_form_is_the_argmax_of_the_objective(ctx):
    """The one test the architecture rests on.

    If someone adds a second objective function, or changes the cost pair
    without changing the scorer, this fails.
    """
    product = _product()
    dist = _dist()
    econ = prevent.economics(product, ctx)
    _, closed_form = prevent.optimal_quantity(dist, econ)

    grid = np.arange(20.0, 121.0, 0.25)
    values = [
        prevent.value_of_quantity(product, dist, float(q), 80.0, ctx) for q in grid
    ]
    grid_best = float(grid[int(np.argmax(values))])

    assert closed_form == pytest.approx(grid_best, abs=0.75)


def test_argmax_holds_across_lambdas_and_margins(ctx):
    for lam in (0.0, 1.0, 3.0):
        for price, cost in ((278.0, 92.0), (150.0, 38.0), (45.0, 12.0)):
            product = _product(unit_price=price, unit_cost=cost)
            dist = _dist(mean=80.0, sd=14.0)
            c = ctx.with_lambda(lam)
            econ = prevent.economics(product, c)
            _, closed_form = prevent.optimal_quantity(dist, econ)

            grid = np.arange(20.0, 161.0, 0.25)
            values = [
                prevent.value_of_quantity(product, dist, float(q), 100.0, c)
                for q in grid
            ]
            grid_best = float(grid[int(np.argmax(values))])
            assert closed_form == pytest.approx(grid_best, abs=1.0), (lam, price)


def test_lambda_pushes_the_quantity_down(ctx):
    product = _product()
    dist = _dist()
    quantities = [
        prevent.plan_quantity(product, dist, ctx.with_lambda(lam)).recommended_qty
        for lam in (0.0, 1.0, 3.0, 5.0)
    ]
    assert quantities == sorted(quantities, reverse=True)
    assert quantities[0] > quantities[-1], "lambda must actually move the plan"


def test_habitual_service_level_wastes_more_than_the_optimum(ctx):
    product = _product()
    dist = _dist()
    plan = prevent.plan_quantity(product, dist, ctx)
    assert plan.baseline_qty > plan.recommended_qty
    assert plan.expected_waste_baseline_kg > plan.expected_waste_recommended_kg
    assert plan.saving_money > 0


def test_plan_action_scores_through_the_one_objective(ctx):
    product = _product()
    dist = _dist()
    action = prevent.build_quantity_action(product, dist, 63.0, 80.0, ctx)
    scored = score(action, ctx)
    assert scored.feasible
    assert scored.terms["total"] == pytest.approx(scored.value)
    assert scored.terms["recovered_value"] > 0


def test_ingredient_explosion_grosses_up_by_standard_yield(ctx):
    plan = prevent.PreventPlan(
        product_id=1, label="Veg Pulao", uom="portion",
        baseline_qty=100.0, recommended_qty=80.0, q_star=0.66,
        forecast_median=78, forecast_low=60, forecast_high=95,
        expected_waste_baseline_kg=0, expected_waste_recommended_kg=0,
        saving_kg=0, saving_money=0, saving_co2e=0, confidence="HIGH",
    )
    # cauliflower: 0.05 kg per portion at a 0.58 standard yield
    recipes = {1: [(9, "Cauliflower", 0.05, 0.58)]}
    out = prevent.explode_to_ingredients([plan], recipes)
    assert out[9]["required_kg"] == pytest.approx(80 * 0.05 / 0.58, abs=1e-3)
    assert out[9]["saved_kg"] > 0
