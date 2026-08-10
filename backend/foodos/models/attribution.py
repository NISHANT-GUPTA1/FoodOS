"""Waste attribution — where today's at-risk value actually came from.

Owner: Person A (Data & Models).

This module carries TWO layers, merged from the two parallel drafts:

  1. `attribute()` — the frozen H3 contract, five rule-based detectors, loads its
     own tables. Callers: verify.py, tests/test_models/.
  2. `attribute_window()` — the pure, dependency-injected window decomposition
     returning an `AttributionResult`. Caller: engine/service.py.
     (Named `attribute` on feat/b-engine; renamed here so both can coexist.)

Consolidating the two is follow-up work; this merge only makes both callers work.

--- Layer 1: the five detectors ---

Deliberately rules and benchmarks, not ML. Every number here is arithmetic a chef
can check on the back of a docket, which is the whole point: the engine has to
survive being argued with by the person whose kitchen it is.

  overproduction     produced vs sold, per dish, with the weekday pattern
  prep_trim          actual yield vs the standard culinary yield table
  spoilage           batches that died on the shelf, and how old they were
  plate_waste        served vs returned, per dish
  quality_rejection  share of intake refused at the gate

One subtlety worth defending in review: the trim detector does NOT read the waste
log. Kitchens weigh only part of their peel, so the log understates trim and would
make a bad yield look good. Instead it compares gross kilos actually drawn from
stock against the net kilos the recipe needed. That needs no extra discipline.

--- Layer 2: the plan-drift / forecast-error split ---

Every unit of over-production sits somewhere in the gap between what the kitchen
made and what customers wanted. That gap splits cleanly in two:

    produced ────────────── forecast median ────────────── actual demand
             |<- plan drift ->|<---- forecast error ---->|

Plan drift is production above the forecast: the model said one thing and the prep
sheet said another. Forecast error is the forecast above what actually happened —
that one is ours. The fixes are opposites: plan drift is fixed by changing a
laminated card, forecast error by a better model. Reporting them as one number is
why kitchens buy a second forecasting tool when their real problem is a card.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

import pandas as pd

from ..data import catalog as C
from . import loader

# ============================================================================
# Layer 1 — five detectors (from main). Callers: verify.py, tests/test_models/
# ============================================================================

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


# ============================================================================
# Layer 2 — window decomposition (from feat/b-engine).
# Caller: engine/service.py.  `attribute` there -> `attribute_window` here.
# ============================================================================

#: Presentation names and the order they should be offered in when shares tie.
CONTRIBUTOR_META = {
    "plan_drift": ("Plan drift", "Production above what the forecast called for"),
    "forecast_error": ("Forecast error", "Demand came in below the forecast"),
    "chiller_temp": ("Chiller temperature", "Stock ageing faster than its label in a warm zone"),
    "over_cut_mise": ("Over-cut mise", "More prepped at the start of service than service needed"),
    "supplier": ("Supplier over-delivery", "More delivered than was ordered"),
}


@dataclass
class Contribution:
    key: str
    name: str
    evidence: str
    value_inr: float = 0.0
    kg: float = 0.0

    @property
    def share_of(self) -> float:  # filled in by the caller
        return 0.0


@dataclass
class AttributionResult:
    date: dt.date
    window_days: int
    value_at_risk_inr: float
    kg_at_risk: float
    contributors: list[dict] = field(default_factory=list)
    worst_dish: str = ""
    worst_dish_name: str = ""
    trim_kg: float = 0.0
    trim_value_inr: float = 0.0
    worst_ingredient: str = ""
    worst_ingredient_yield: float = 1.0

    @property
    def preventable_pct(self) -> float:
        """Everything except forecast error was a decision somebody could have made differently.

        Forecast error is the honest residual — the part that was genuinely not knowable
        on the morning. Calling it preventable would be marking our own homework.
        """
        preventable = sum(
            c["value_inr"] for c in self.contributors if c["key"] != "forecast_error"
        )
        if self.value_at_risk_inr <= 0:
            return 0.0
        return round(100.0 * preventable / self.value_at_risk_inr, 1)

    @property
    def top(self) -> dict | None:
        return self.contributors[0] if self.contributors else None


def attribute_window(
    *,
    date: dt.date,
    waste: pd.DataFrame,
    production: pd.DataFrame,
    sales: pd.DataFrame,
    forecast_median: pd.DataFrame,
    zone_temps: pd.DataFrame,
    zones: dict[str, dict],
    dish_names: dict[str, str],
    ingredient_yields: dict[str, float],
    window_days: int = 14,
) -> AttributionResult:
    """Decompose the trailing window's waste into named contributors.

    A window rather than a single day: one day of a fourteen-dish kitchen is too noisy to
    diagnose anything from, and a manager who is told a different root cause every morning
    stops reading.
    """
    start = date - dt.timedelta(days=window_days)
    in_window = lambda frame: frame[  # noqa: E731
        (frame["date"] > pd.Timestamp(start)) & (frame["date"] <= pd.Timestamp(date))
    ]

    waste_w = in_window(waste)
    prod_w = in_window(production)
    sales_w = in_window(sales)

    buckets = {k: Contribution(k, *CONTRIBUTOR_META[k]) for k in CONTRIBUTOR_META}

    # --- overproduction splits into plan drift and forecast error ----------
    merged = (
        prod_w.merge(sales_w, on=["date", "dish_id"], how="left")
        .merge(forecast_median, on=["date", "dish_id"], how="left")
    )
    # Over-production waste is recorded against the dish, so product_id holds a dish id here.
    over = waste_w[waste_w["reason"] == "overproduction"]
    over_by_key = (
        over.groupby(["date", "product_id"])[["value_inr", "qty_kg"]].sum()
        if not over.empty
        else over.set_index(["date", "product_id"])[["value_inr", "qty_kg"]]
    )

    dish_damage: dict[str, float] = {}

    for row in merged.itertuples():
        key = (row.date, row.dish_id)
        if key not in over_by_key.index:
            continue
        binned_value = float(over_by_key.loc[key, "value_inr"])
        binned_kg = float(over_by_key.loc[key, "qty_kg"])
        dish_damage[row.dish_id] = dish_damage.get(row.dish_id, 0.0) + binned_value

        produced = float(row.produced_portions)
        sold = float(row.qty_portions or 0.0)
        median = float(row.forecast_median) if pd.notna(row.forecast_median) else sold

        drift = max(0.0, produced - median)
        error = max(0.0, median - sold)
        total = drift + error

        if total <= 1e-9:
            # The plan matched the forecast and the forecast matched the day. Whatever was
            # binned is noise; attribute it to forecast error rather than inventing a cause.
            buckets["forecast_error"].value_inr += binned_value
            buckets["forecast_error"].kg += binned_kg
            continue

        for name, part in (("plan_drift", drift), ("forecast_error", error)):
            weight = part / total
            buckets[name].value_inr += binned_value * weight
            buckets[name].kg += binned_kg * weight

    # --- spoilage traced to zones above set point --------------------------
    spoilage = waste_w[waste_w["reason"] == "spoilage"]
    temps = in_window(zone_temps).groupby("zone_id")["service_temp_c"].mean().to_dict()

    for row in spoilage.itertuples():
        zone_id = getattr(row, "zone_id", "") or ""
        set_point = float(zones.get(zone_id, {}).get("set_temp_c", 4.0))
        actual = float(temps.get(zone_id, set_point))
        excess = max(0.0, actual - set_point)
        # Attribute the share of the decay that the temperature gap is responsible for.
        # A zone at set point contributes nothing here; a zone five degrees over carries
        # most of the blame for what spoiled inside it.
        blame = min(1.0, excess / 5.0)
        buckets["chiller_temp"].value_inr += float(row.value_inr) * blame
        buckets["chiller_temp"].kg += float(row.qty_kg) * blame
        buckets["forecast_error"].value_inr += float(row.value_inr) * (1 - blame) * 0.0
        # The unblamed remainder of spoilage is ordinary shrinkage; it is not a contributor
        # anyone can act on, so it is left out rather than padded into another bucket.

    # --- trim and supplier -------------------------------------------------
    trim = waste_w[waste_w["reason"] == "trim"]
    buckets["over_cut_mise"].value_inr += float(trim["value_inr"].sum())
    buckets["over_cut_mise"].kg += float(trim["qty_kg"].sum())

    supplier = waste_w[waste_w["reason"] == "supplier"]
    buckets["supplier"].value_inr += float(supplier["value_inr"].sum())
    buckets["supplier"].kg += float(supplier["qty_kg"].sum())

    # --- assemble ----------------------------------------------------------
    total_value = sum(b.value_inr for b in buckets.values())
    total_kg = sum(b.kg for b in buckets.values())

    days = max(1, window_days)

    # Contributor values are reported PER DAY, like the headline they add up to. Reporting
    # the window total next to a daily headline is how a screen ends up claiming that more
    # than a hundred per cent of today's risk was preventable.
    contributors = [
        {
            "key": b.key,
            "name": b.name,
            "share": round(100.0 * b.value_inr / total_value, 1) if total_value else 0.0,
            "value_inr": round(b.value_inr / days, 2),
            "kg": round(b.kg / days, 3),
            "evidence": b.evidence,
        }
        for b in buckets.values()
        if b.value_inr > 0.005
    ]
    contributors.sort(key=lambda c: c["share"], reverse=True)

    worst_dish = max(dish_damage, key=dish_damage.get) if dish_damage else ""

    # The trim callout names the ingredient losing the most weight to prep, which is a
    # different question from which one costs the most.
    worst_ingredient, worst_yield = "", 1.0
    if ingredient_yields:
        worst_ingredient = min(ingredient_yields, key=ingredient_yields.get)
        worst_yield = ingredient_yields[worst_ingredient]

    return AttributionResult(
        date=date,
        window_days=window_days,
        value_at_risk_inr=round(total_value / days, 2),
        kg_at_risk=round(total_kg / days, 3),
        contributors=contributors,
        worst_dish=worst_dish,
        worst_dish_name=dish_names.get(worst_dish, worst_dish),
        trim_kg=round(float(trim["qty_kg"].sum()) / days, 3),
        trim_value_inr=round(float(trim["value_inr"].sum()) / days, 2),
        worst_ingredient=worst_ingredient,
        worst_ingredient_yield=worst_yield,
    )
