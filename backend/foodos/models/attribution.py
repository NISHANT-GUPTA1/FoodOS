"""Waste attribution — five causes, each with its own detector.

OWNER: Person A (Data & Models).
CONTRACT (frozen at H3):  attribute(site_id, start, end) -> dict

Deliberately rules and benchmarks, not ML. Every number here is arithmetic a
chef can check on the back of a docket, which is the whole point: the engine
has to survive being argued with by the person whose kitchen it is.

The five detectors:

  overproduction     produced vs sold, per dish, with the weekday pattern
  prep_trim          actual yield vs the standard culinary yield table
  spoilage           batches that died on the shelf, and how old they were
  plate_waste        served vs returned, per dish
  quality_rejection  share of intake refused at the gate

One subtlety worth defending in review: the trim detector does NOT read the
waste log. Kitchens weigh only part of their peel, so the log understates trim
and would make a bad yield look good. Instead it compares gross kilos actually
drawn from stock (inventory events) against the net kilos the recipe needed for
what was produced. That needs no extra discipline from the kitchen at all.
"""

from __future__ import annotations

import pandas as pd

from ..data import catalog as C
from . import loader

CAUSES = ["overproduction", "prep_trim", "spoilage", "plate_waste", "quality_rejection"]

# Don't raise a yield finding a chef would be right to dismiss. Anything under
# this is inside the noise of how a standard table is written, and a product
# that nags about half a percentage point stops being read at all.
MIN_YIELD_GAP_PTS = 1.5


def _window(df: pd.DataFrame, start: str, end: str, col: str = "business_date"):
    return df[(df[col] >= start) & (df[col] <= end)]


# --------------------------------------------------------------------------
# Detector 1 — overproduction
# --------------------------------------------------------------------------

def detect_overproduction(tables, start, end) -> dict:
    prod = _window(tables["production"], start, end)
    sales = _window(tables["sales"], start, end)
    products = tables["products"]

    df = prod.merge(sales[["product_id", "business_date", "qty"]],
                    on=["product_id", "business_date"], how="left")
    df["qty"] = df["qty"].fillna(0)
    df["over_units"] = (df["actual_qty"] - df["qty"]).clip(lower=0)
    df["dow"] = pd.to_datetime(df["business_date"]).dt.weekday

    by_dish = []
    for pid, g in df.groupby("product_id"):
        sold, over = g["qty"].sum(), g["over_units"].sum()
        if sold <= 0:
            continue
        food_cost = float(products.loc[pid, "unit_cost"])
        # worst weekday, measured as a ratio of totals so one quiet day cannot
        # dominate the average
        worst_dow, worst_pct = None, 0.0
        for dow, gd in g.groupby("dow"):
            if gd["qty"].sum() <= 0:
                continue
            pct = gd["over_units"].sum() / gd["qty"].sum() * 100
            if pct > worst_pct:
                worst_dow, worst_pct = int(dow), float(pct)
        by_dish.append({
            "product_id": pid,
            "name": str(products.loc[pid, "name"]),
            "produced": int(g["actual_qty"].sum()),
            "sold": int(sold),
            "over_units": int(over),
            "over_pct": round(over / sold * 100, 1),
            "value": round(over * food_cost, 2),
            "worst_dow": worst_dow,
            "worst_dow_name": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][worst_dow]
            if worst_dow is not None else None,
            "worst_dow_over_pct": round(worst_pct, 1),
        })

    by_dish.sort(key=lambda r: -r["value"])
    return {"by_dish": by_dish, "total_value": round(sum(r["value"] for r in by_dish), 2)}


# --------------------------------------------------------------------------
# Detector 2 — prep trim against the standard yield table
# --------------------------------------------------------------------------

def detect_trim_yield(tables, start, end) -> list[dict]:
    prod = _window(tables["production"], start, end)
    recipes = tables["recipes"]
    products = tables["products"]

    events = tables["inventory_events"].copy()
    events["business_date"] = events["ts"].str[:10]
    consumed = _window(events[events["type"] == "consume"], start, end)
    gross = consumed.groupby("product_id")["qty"].sum()

    # net kilos the BOM required for what was actually produced
    plan = prod.merge(recipes, left_on="product_id", right_on="product_id", how="inner")
    plan["net_qty"] = plan["qty"] * plan["actual_qty"]
    net = plan.groupby("ingredient_product_id")["net_qty"].sum()
    standard = recipes.groupby("ingredient_product_id")["standard_yield_pct"].first()

    out = []
    for ing_id, net_kg in net.items():
        gross_kg = float(gross.get(ing_id, 0.0))
        std = float(standard.get(ing_id, 1.0))
        if gross_kg <= 0 or net_kg <= 0 or std >= 0.999:
            continue
        actual_yield = net_kg / gross_kg
        if (std - actual_yield) * 100 < MIN_YIELD_GAP_PTS:
            continue                      # at, above, or within noise of standard
        gross_at_standard = net_kg / std
        avoidable_kg = gross_kg - gross_at_standard
        unit_cost = float(products.loc[ing_id, "unit_cost"])
        out.append({
            "product_id": ing_id,
            "name": str(products.loc[ing_id, "name"]),
            "actual_yield": round(actual_yield, 3),
            "standard_yield": round(std, 3),
            "gap_pts": round((std - actual_yield) * 100, 1),
            "net_used_kg": round(float(net_kg), 1),
            "gross_used_kg": round(gross_kg, 1),
            "avoidable_kg": round(avoidable_kg, 1),
            "avoidable_value": round(avoidable_kg * unit_cost, 2),
        })

    out.sort(key=lambda r: -r["avoidable_value"])
    return out


# --------------------------------------------------------------------------
# Detector 3 — spoilage
# --------------------------------------------------------------------------

def detect_spoilage(tables, start, end) -> dict:
    waste = _window(tables["waste"], start, end)
    sp = waste[waste["reason"] == "spoilage"]
    receipts = tables["goods_receipt"][["batch_id", "received_at", "qty_received"]]
    products = tables["products"]

    if sp.empty:
        return {"by_product": [], "total_value": 0.0, "mean_days_held": 0.0}

    df = sp.merge(receipts, on="batch_id", how="left")
    df["days_held"] = (pd.to_datetime(df["business_date"])
                       - pd.to_datetime(df["received_at"])).dt.days
    df["unsold_share"] = df["qty"] / df["qty_received"].replace(0, pd.NA)

    by_product = []
    for pid, g in df.groupby("product_id"):
        by_product.append({
            "product_id": pid,
            "name": str(products.loc[pid, "name"]),
            "kg": round(float(g["qty"].sum()), 1),
            "value": round(float(g["value"].sum()), 2),
            "batches": int(len(g)),
            "mean_days_held": round(float(g["days_held"].mean()), 1),
            "mean_share_of_batch_lost": round(float(g["unsold_share"].mean(skipna=True)), 3),
        })
    by_product.sort(key=lambda r: -r["value"])
    return {
        "by_product": by_product,
        "total_value": round(float(df["value"].sum()), 2),
        "mean_days_held": round(float(df["days_held"].mean()), 1),
    }


# --------------------------------------------------------------------------
# Detectors 4 and 5 — plate waste and quality rejection
# --------------------------------------------------------------------------

def detect_plate_waste(tables, start, end) -> list[dict]:
    waste = _window(tables["waste"], start, end)
    pw = waste[waste["reason"] == "plate_waste"]
    sales = _window(tables["sales"], start, end)
    products = tables["products"]
    served = sales.groupby("product_id")["qty"].sum()

    out = []
    for pid, g in pw.groupby("product_id"):
        n_served = float(served.get(pid, 0))
        if n_served <= 0:
            continue
        out.append({
            "product_id": pid,
            "name": str(products.loc[pid, "name"]),
            "kg": round(float(g["qty"].sum()), 1),
            "value": round(float(g["value"].sum()), 2),
            "served": int(n_served),
            "returned_share_pct": round(float(g["qty"].sum())
                                        / max(n_served, 1) * 100, 2),
        })
    out.sort(key=lambda r: -r["value"])
    return out


def detect_quality_rejection(tables, start, end) -> list[dict]:
    waste = _window(tables["waste"], start, end)
    qr = waste[waste["reason"] == "quality_rejection"]
    receipts = tables["goods_receipt"]
    products = tables["products"]
    received = receipts.groupby("product_id")["qty_received"].sum()

    out = []
    for pid, g in qr.groupby("product_id"):
        total_in = float(received.get(pid, 0))
        out.append({
            "product_id": pid,
            "name": str(products.loc[pid, "name"]),
            "kg": round(float(g["qty"].sum()), 1),
            "value": round(float(g["value"].sum()), 2),
            "rejects": int(len(g)),
            "reject_share_pct": round(float(g["qty"].sum()) / max(total_in, 1) * 100, 2),
        })
    out.sort(key=lambda r: -r["value"])
    return out


# --------------------------------------------------------------------------
# The contract
# --------------------------------------------------------------------------

def attribute(site_id: str = C.SITE["site_id"], start: str | None = None,
              end: str | None = None, tables=None) -> dict:
    tables = tables or loader.load_all()
    waste = tables["waste"]
    waste = waste[waste["site_id"] == site_id]
    start = start or waste["business_date"].min()
    end = end or waste["business_date"].max()

    w = _window(waste, start, end)
    products = tables["products"]
    total_value = float(w["value"].sum())
    total_kg = float(w["qty"].sum())

    by_cause_value = {c: round(float(w[w["reason"] == c]["value"].sum()), 2)
                      for c in CAUSES}
    by_cause_kg = {c: round(float(w[w["reason"] == c]["qty"].sum()), 1) for c in CAUSES}
    by_cause = {c: round(by_cause_value[c] / total_value * 100, 1) if total_value else 0.0
                for c in CAUSES}

    contrib = (w.groupby("product_id")
                 .agg(kg=("qty", "sum"), value=("value", "sum"))
                 .sort_values("value", ascending=False).head(8))
    top_contributors = [{
        "product_id": pid,
        "name": str(products.loc[pid, "name"]),
        "kg": round(float(r["kg"]), 1),
        "value": round(float(r["value"]), 2),
        "share_pct": round(float(r["value"]) / total_value * 100, 1) if total_value else 0.0,
    } for pid, r in contrib.iterrows()]

    produce_ids = set(products[products["is_produce"] == 1].index)
    produce_kg = float(w[w["product_id"].isin(produce_ids)]["qty"].sum())

    n_days = len(pd.date_range(start, end))
    trim = detect_trim_yield(tables, start, end)

    return {
        "site_id": site_id, "start": str(start), "end": str(end), "days": n_days,
        "total_kg": round(total_kg, 1),
        "total_value": round(total_value, 2),
        "monthly_value": round(total_value / n_days * 30, 2),
        "monthly_kg": round(total_kg / n_days * 30, 1),
        "produce_share_kg_pct": round(produce_kg / total_kg * 100, 1) if total_kg else 0.0,
        "by_cause": by_cause,
        "by_cause_value": by_cause_value,
        "by_cause_kg": by_cause_kg,
        "top_contributors": top_contributors,
        "detectors": {
            "overproduction": detect_overproduction(tables, start, end),
            "trim_yield": trim,
            "spoilage": detect_spoilage(tables, start, end),
            "plate_waste": detect_plate_waste(tables, start, end),
            "quality_rejection": detect_quality_rejection(tables, start, end),
        },
        "avoidable_trim_value_monthly": round(
            sum(t["avoidable_value"] for t in trim) / n_days * 30, 2),
    }


if __name__ == "__main__":
    r = attribute()
    print(f"\nWaste attribution — {r['start']} to {r['end']} ({r['days']} days)")
    print(f"  Rs {r['total_value']:,.0f}   {r['total_kg']:,.0f} kg"
          f"   ({r['produce_share_kg_pct']}% of the weight is fruit & veg)")
    print(f"  Rs {r['monthly_value']:,.0f} / month\n")

    for cause, pct in sorted(r["by_cause"].items(), key=lambda kv: -kv[1]):
        print(f"    {cause:<19}{pct:5.1f}%   Rs {r['by_cause_value'][cause]:>9,.0f}"
              f"   {'#' * int(round(pct / 2.5))}")

    print("\n  worst dish for over-production")
    for d in r["detectors"]["overproduction"]["by_dish"][:3]:
        print(f"    {d['name']:<22} produced {d['produced']:>5}  sold {d['sold']:>5}"
              f"  over {d['over_pct']:>5.1f}%   worst day {d['worst_dow_name']}"
              f" at {d['worst_dow_over_pct']:.1f}%   Rs {d['value']:,.0f}")

    print("\n  yield below the standard table")
    for t in r["detectors"]["trim_yield"][:4]:
        print(f"    {t['name']:<22} {t['actual_yield']:.2f} vs {t['standard_yield']:.2f}"
              f" standard   avoidable {t['avoidable_kg']:>6.1f} kg"
              f"   Rs {t['avoidable_value']:,.0f}")
    print(f"    -> avoidable trim worth Rs {r['avoidable_trim_value_monthly']:,.0f} a month")

    sp = r["detectors"]["spoilage"]
    print(f"\n  spoilage: Rs {sp['total_value']:,.0f}, held {sp['mean_days_held']} days on average")
    for s in sp["by_product"][:3]:
        print(f"    {s['name']:<22} {s['kg']:>6.1f} kg  Rs {s['value']:>8,.0f}"
              f"  {s['batches']} batches  {s['mean_days_held']} days held")
    print()
