"""Backtest — measured savings, not projected savings.

Owner: Person A (Data & Models).

`run_backtest()` is the frozen H3 contract (FoodOS-Team-Split.md §4): loads its
own tables, replays the last N days through the newsvendor optimiser, reports
rupees and kilos. Callers: verify.py and tests/test_models/.

Train on the first part of the history, then replay the last 30 days the model has
never seen and ask a single question: if the kitchen had prepped what the optimiser
said instead of what it actually prepped, what would the difference have been in
rupees and kilos? That makes the headline number an *output* rather than an
assumption, which answers the question every serious judge is holding: "how do I
know these savings aren't made up?"

    C_u = unit_price - food_cost           margin lost if you run out
    C_o = food_cost + lambda * co2e_price  cost of one portion binned
    q*  = C_u / (C_u + C_o)                economically optimal service level
    Q*  = Forecast.quantile(q*)            read off the distribution

NOTE FOR PERSON B: this module carries its own copy of the newsvendor so the
forecaster can be evaluated before the engine exists. `engine/prevent.py` is the
production optimiser and the single source of truth. At integration, delete
`_newsvendor_qty` here and import yours — two objective functions is exactly the
failure mode the plan warns about.

One honest caveat: true demand is unobservable. We only ever see
sold = min(demand, produced), so on days the kitchen sold out the real demand was
higher than the number scored here. The censoring rate is reported.

"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..data import catalog as C
from . import forecast, loader

def _dish_economics(products: pd.DataFrame, pid: str, lam: float) -> dict:
    price = float(products.loc[pid, "unit_price"] or 0.0)
    cost = float(products.loc[pid, "unit_cost"])
    co2e = float(products.loc[pid, "co2e_kg_per_uom"] or 0.0)
    portion_kg = float(products.loc[pid, "portion_kg"] or 0.0)

    # felt keenly, but only partly real: most guests order something else
    cu = max(price - cost, 0.0) * (1.0 - C.SUBSTITUTION_RATE)

    # felt by nobody: the ingredients, the labour already spent on them, the
    # disposal fee, and whatever value the operator puts on not wasting food
    co = (cost
          + C.LABOUR_COST_PER_PORTION
          + C.DISPOSAL_COST_PER_KG * portion_kg
          + co2e * C.CO2E_PRICE_PER_KG
          + lam * portion_kg)

    return {"price": price, "cost": cost, "co2e": co2e, "portion_kg": portion_kg,
            "cu": cu, "co": co,
            "q_star": cu / (cu + co) if (cu + co) > 0 else 0.5}


def _newsvendor_qty(dist: dict, q_star: float) -> float:
    """Read the critical fractile off the forecast distribution."""
    grid = [(0.10, dist["q10"]), (0.25, dist["q25"]), (0.50, dist["q50"]),
            (0.66, dist["q66"]), (0.75, dist["q75"]), (0.90, dist["q90"])]
    qs = [g[0] for g in grid]
    vs = [g[1] for g in grid]
    return float(np.interp(q_star, qs, vs))


def run_backtest(site_id: str = C.SITE["site_id"], test_days: int = 30,
                 lam: float = 0.0, tables=None) -> dict:
    tables = tables or loader.load_all()
    products = tables["products"]
    sales = tables["sales"]
    production = tables["production"]

    all_dates = sorted(sales["business_date"].astype(str).unique())
    test_dates = all_dates[-test_days:]
    train_end = all_dates[-test_days - 1]

    run_id = forecast.train(train_end=train_end)

    dishes = products[(products["is_dish"] == 1)
                      & (products["plannable"] == 1)]["product_id"].tolist()
    sold = sales.set_index(["product_id", "business_date"])["qty"]
    made = production.set_index(["product_id", "business_date"])["actual_qty"]

    rows = []
    for pid in dishes:
        # Quantity is CHOSEN under lambda; the result is always COSTED in real
        # rupees at lambda = 0. Scoring the plan with lambda still in the cost
        # function would let a judge drag the slider and watch money appear out
        # of nowhere, which is the opposite of the point. Raising lambda must
        # show more kilos saved and, past the optimum, less cash.
        econ = _dish_economics(products, pid, lam)
        cash = _dish_economics(products, pid, 0.0)
        portion_kg = float(products.loc[pid, "portion_kg"] or 0.0)
        for day in test_dates:
            try:
                demand = float(sold.loc[(pid, day)])
                baseline = float(made.loc[(pid, day)])
            except KeyError:
                continue
            dist = forecast.predict_quantiles(site_id, pid, day)
            recommended = round(_newsvendor_qty(dist, econ["q_star"]))

            over_b, short_b = max(0.0, baseline - demand), max(0.0, demand - baseline)
            over_r, short_r = max(0.0, recommended - demand), max(0.0, demand - recommended)
            cost_b = over_b * cash["co"] + short_b * cash["cu"]
            cost_r = over_r * cash["co"] + short_r * cash["cu"]

            rows.append({
                "product_id": pid, "name": str(products.loc[pid, "name"]),
                "business_date": day, "demand": demand,
                "baseline_qty": baseline, "recommended_qty": recommended,
                "q_star": round(econ["q_star"], 3),
                "over_baseline": over_b, "over_recommended": over_r,
                "cost_baseline": cost_b, "cost_recommended": cost_r,
                "saving": cost_b - cost_r,
                "saving_kg": (over_b - over_r) * portion_kg,
                "saving_co2e": (over_b - over_r) * econ["co2e"],
                "censored": bool(demand >= baseline),
            })

    df = pd.DataFrame(rows)
    accuracy = forecast.evaluate(test_dates[0], test_dates[-1])

    by_dish = (df.groupby(["product_id", "name"])
                 .agg(saving=("saving", "sum"), saving_kg=("saving_kg", "sum"),
                      over_baseline=("over_baseline", "sum"),
                      over_recommended=("over_recommended", "sum"))
                 .reset_index().sort_values("saving", ascending=False))

    n_days = len(test_dates)
    total_saving = float(df["saving"].sum())
    total_kg = float(df["saving_kg"].sum())

    n_train = len(all_dates) - n_days

    return {
        # --- Contract 1 (A -> B), frozen at H3 in FoodOS-Team-Split.md §4 ------
        # These seven keys are the frozen surface. Everything below them is this
        # module's own richer output, kept because verify.py and the engine read
        # it. Aliases, not duplicates of the work: same numbers, contract names.
        #
        # One deliberate deviation: the contract shows `test_days` as the pair
        # [21, 30], but it is also this function's input parameter and
        # tests/test_models/test_planted_faults.py asserts `== 30`. It stays an
        # int; `test_day_range` carries the pair the contract meant.
        "train_days": [1, n_train],
        "test_day_range": [n_train + 1, len(all_dates)],
        "pinball_loss": accuracy["pinball_loss"],
        "mape": accuracy["mape"],
        "coverage": accuracy["interval_coverage_pct"],
        "baseline_mape": accuracy["baseline_mape"],
        "counterfactual_saving_kg": round(total_kg, 1),
        "counterfactual_saving_money": round(total_saving, 2),
        # ----------------------------------------------------------------------
        "site_id": site_id,
        "model_run_id": run_id,
        "train_start": all_dates[0], "train_end": train_end,
        "test_start": test_dates[0], "test_end": test_dates[-1],
        "test_days": n_days,
        "lambda": lam,
        "baseline_name": "what the kitchen actually prepped",
        "cost_baseline": round(float(df["cost_baseline"].sum()), 2),
        "cost_recommended": round(float(df["cost_recommended"].sum()), 2),
        "saving_money": round(total_saving, 2),
        "saving_kg": round(total_kg, 1),
        "saving_co2e": round(float(df["saving_co2e"].sum()), 1),
        "saving_money_monthly": round(total_saving / n_days * 30, 2),
        "saving_kg_monthly": round(total_kg / n_days * 30, 1),
        "overproduction_baseline_units": int(df["over_baseline"].sum()),
        "overproduction_recommended_units": int(df["over_recommended"].sum()),
        "overproduction_cut_pct": round(
            (1 - df["over_recommended"].sum() / max(df["over_baseline"].sum(), 1)) * 100, 1),
        "censoring_rate_pct": round(float(df["censored"].mean()) * 100, 1),
        "accuracy": accuracy,
        "by_dish": by_dish.to_dict("records"),
        "series": df[["business_date", "product_id", "demand", "baseline_qty",
                      "recommended_qty"]].to_dict("records"),
    }


def lambda_frontier(values=(0.0, 25.0, 50.0, 100.0, 150.0), tables=None) -> list[dict]:
    """The sustainability dial, as a frontier a judge can drag along.

    Raising lambda prices the carbon in a binned portion, which pushes C_o up,
    q* down, and the whole plan toward less waste at a small cost in margin.
    """
    tables = tables or loader.load_all()
    out = []
    for lam in values:
        r = run_backtest(lam=lam, tables=tables)
        out.append({
            "lambda": lam,
            "saving_money_monthly": r["saving_money_monthly"],
            "saving_kg_monthly": r["saving_kg_monthly"],
            "overproduction_cut_pct": r["overproduction_cut_pct"],
        })
    return out


if __name__ == "__main__":
    t = loader.load_all()
    r = run_backtest(tables=t)

    print(f"\nBacktest — trained {r['train_start']} to {r['train_end']}, "
          f"evaluated on {r['test_days']} days the model never saw "
          f"({r['test_start']} to {r['test_end']})")

    a = r["accuracy"]
    print(f"\n  forecast accuracy")
    print(f"    pinball loss     {a['pinball_loss']:>7.3f}  vs seasonal naive "
          f"{a['baseline_pinball_loss']:>7.3f}   ({a['pinball_improvement_pct']:+.1f}%)")
    print(f"    MAPE at median   {a['mape']:>6.1f}%  vs seasonal naive "
          f"{a['baseline_mape']:>6.1f}%   ({a['mape_improvement_pct']:+.1f}%)")
    print(f"    10-90 coverage   {a['interval_coverage_pct']:>6.1f}%")

    print(f"\n  measured counterfactual, over {r['test_days']} days")
    print(f"    over-production   {r['overproduction_baseline_units']:>6} portions"
          f"  ->  {r['overproduction_recommended_units']:>5} portions"
          f"   ({r['overproduction_cut_pct']:.0f}% cut)")
    print(f"    total cost        Rs {r['cost_baseline']:>10,.0f}"
          f"  ->  Rs {r['cost_recommended']:>9,.0f}")
    print(f"    saving            Rs {r['saving_money']:>10,.0f}"
          f"   {r['saving_kg']:,.0f} kg   {r['saving_co2e']:,.0f} kg CO2e")
    print(f"    per month         Rs {r['saving_money_monthly']:>10,.0f}"
          f"   {r['saving_kg_monthly']:,.0f} kg")
    print(f"    days the kitchen sold out (demand censored): "
          f"{r['censoring_rate_pct']}%")

    print(f"\n  biggest wins")
    for d in r["by_dish"][:5]:
        print(f"    {d['name']:<24} Rs {d['saving']:>8,.0f}"
              f"   {d['saving_kg']:>6.1f} kg"
              f"   over-prep {d['over_baseline']:>5.0f} -> {d['over_recommended']:.0f}")

    print(f"\n  the lambda dial")
    print(f"    {'lambda':>7}{'Rs / month':>14}{'kg / month':>13}{'over-prep cut':>16}")
    for f in lambda_frontier(tables=t):
        print(f"    {f['lambda']:>7.1f}{f['saving_money_monthly']:>14,.0f}"
              f"{f['saving_kg_monthly']:>13,.0f}{f['overproduction_cut_pct']:>15.0f}%")
    print()

