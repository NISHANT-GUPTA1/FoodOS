"""One command that proves Person A's half of FoodOS works.

    python -m foodos.verify

Rebuilds the dataset from scratch, runs every model over it, and checks that
each of the three planted faults is rediscovered. Prints PASS or FAIL per check
and exits non-zero if anything is wrong, so it can be wired to a git hook or
just run before handing anything to Person B.
"""

from __future__ import annotations

import os
import sys

from .data import catalog as C
from .data.generate import generate_dataset
from .models import attribution, backtest, forecast, loader, rsl

CHECKS: list[tuple[str, bool, str]] = []


def check(name: str, passed: bool, detail: str = "") -> None:
    CHECKS.append((name, bool(passed), detail))


def rule(title: str) -> None:
    print(f"\n\033[1m{title}\033[0m\n" + "-" * 76)


def main() -> int:
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_dir = os.path.join(here, "data", "sample")

    rule("STEP 1  Build the dataset  (90 days of a kitchen that wastes food)")
    generate_dataset(out_dir)
    loader.load_all.cache_clear()
    tables = loader.load_all(out_dir)
    check("dataset written", all(not tables[t].empty for t in loader.TABLES),
          f"{len(loader.TABLES)} tables in data/sample/")

    rule("STEP 2  Attribution  (where is the waste, and why)")
    rep = attribution.attribute(tables=tables)
    print(f"  Rs {rep['monthly_value']:,.0f} and {rep['monthly_kg']:,.0f} kg wasted "
          f"per month, {rep['produce_share_kg_pct']}% of it fruit & veg\n")
    for cause, pct in sorted(rep["by_cause"].items(), key=lambda kv: -kv[1]):
        print(f"    {cause:<19}{pct:5.1f}%  {'#' * int(round(pct / 2))}")
    check("all five waste causes present",
          all(rep["by_cause"][c] > 0 for c in attribution.CAUSES))
    check("fruit & veg dominate wasted weight", rep["produce_share_kg_pct"] > 55,
          f"{rep['produce_share_kg_pct']}%")

    rule("STEP 3  Did the engine find the three planted faults?")

    biryani = {d["product_id"]: d for d in
               rep["detectors"]["overproduction"]["by_dish"]}["DSH_CHBIRYANI"]
    print(f"  1. Chicken Biryani over-produced {biryani['worst_dow_over_pct']}% on "
          f"{biryani['worst_dow_name']} vs {biryani['over_pct']}% overall")
    check("fault 1 — Friday biryani over-prep",
          biryani["worst_dow_name"] == "Fri" and biryani["worst_dow_over_pct"] > 25)

    trim = rep["detectors"]["trim_yield"][0]
    print(f"  2. {trim['name']} yield {trim['actual_yield']} against a "
          f"{trim['standard_yield']} standard — {trim['avoidable_kg']} kg "
          f"(Rs {trim['avoidable_value']:,.0f}) avoidable")
    check("fault 2 — cauliflower yield gap",
          trim["product_id"] == "ING_CAULI" and trim["avoidable_kg"] > 150)

    led = rsl.ledger(tables)
    spinach = led[led["product_id"] == "ING_SPINACH"]
    worst = spinach.loc[spinach["life_overstated_days"].idxmax()]
    print(f"  3. Batch {worst['batch_id']}: {worst['qty_remaining']:.1f} kg spinach, "
          f"label says {worst['days_to_printed_expiry']:.0f} days left, "
          f"really has {worst['rsl_days_computed']:.2f} "
          f"— overstated by {worst['life_overstated_days']:.1f} days")
    check("fault 3 — dock excursion shortens true life",
          worst["life_overstated_days"] > 2.0)

    check("RSL engine agrees with the simulation",
          (led["rsl_days_computed"] - led["rsl_days"]).abs().max() < 0.05)

    rule("STEP 4  Forecast tomorrow's demand as a distribution")
    forecast.train()
    products = tables["products"]
    plannable = products[(products["is_dish"] == 1) & (products["plannable"] == 1)]
    print(f"  {C.PLAN_DATE} is a Friday.  {'dish':<24}{'q10':>6}{'q50':>6}{'q90':>6}")
    for pid in plannable["product_id"].head(4):
        d = forecast.predict_quantiles(product_id=pid)
        print(f"  {'':<27}{str(products.loc[pid, 'name']):<24}"
              f"{d['q10']:>6.0f}{d['q50']:>6.0f}{d['q90']:>6.0f}")

    rule("STEP 5  Backtest  (train on days 1-60, score days 61-90 unseen)")
    bt = backtest.run_backtest(tables=tables)
    a = bt["accuracy"]
    print(f"  forecast   pinball {a['pinball_loss']:.3f} vs seasonal-naive "
          f"{a['baseline_pinball_loss']:.3f}  ({a['pinball_improvement_pct']:+.1f}%)"
          f"   10-90 coverage {a['interval_coverage_pct']:.0f}%")
    print(f"  decision   over-production {bt['overproduction_baseline_units']} -> "
          f"{bt['overproduction_recommended_units']} portions "
          f"({bt['overproduction_cut_pct']:.0f}% cut)")
    print(f"  measured   Rs {bt['saving_money_monthly']:,.0f} and "
          f"{bt['saving_kg_monthly']:,.0f} kg saved per month")

    check("forecaster beats seasonal naive", a["beats_baseline"]
          and a["pinball_improvement_pct"] > 15,
          f"{a['pinball_improvement_pct']:+.1f}%")
    check("confidence band is honest (72-95% coverage)",
          72 <= a["interval_coverage_pct"] <= 95,
          f"{a['interval_coverage_pct']:.0f}%")
    check("backtest saves money on unseen days", bt["saving_money"] > 0,
          f"Rs {bt['saving_money']:,.0f}")
    check("backtest saves food on unseen days", bt["saving_kg"] > 0,
          f"{bt['saving_kg']:,.0f} kg")
    check("model never saw the days it was scored on",
          bt["train_end"] < bt["test_start"])

    rule("STEP 6  The lambda dial  (margin traded for food saved)")
    frontier = backtest.lambda_frontier(values=(0.0, 50.0, 150.0), tables=tables)
    print(f"    {'lambda':>8}{'Rs / month':>14}{'kg / month':>13}")
    for f in frontier:
        print(f"    {f['lambda']:>8.0f}{f['saving_money_monthly']:>14,.0f}"
              f"{f['saving_kg_monthly']:>13,.0f}")
    check("more lambda saves more food",
          [f["saving_kg_monthly"] for f in frontier]
          == sorted(f["saving_kg_monthly"] for f in frontier))
    check("more lambda eventually costs margin",
          frontier[-1]["saving_money_monthly"] < frontier[0]["saving_money_monthly"])

    rule("RESULT")
    failed = [c for c in CHECKS if not c[1]]
    for name, passed, detail in CHECKS:
        mark = "\033[32mPASS\033[0m" if passed else "\033[31mFAIL\033[0m"
        print(f"  {mark}  {name}" + (f"   ({detail})" if detail else ""))
    print(f"\n  {len(CHECKS) - len(failed)}/{len(CHECKS)} checks passed\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
