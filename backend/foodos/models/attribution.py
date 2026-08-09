"""Attribution — where today's at-risk value actually came from.

A waste report tells you *what* went in the bin. This tells you *which decision* put it
there, which is the only version a manager can act on.

The decomposition, and why it is defensible:

Every unit of over-production sits somewhere in the gap between what the kitchen made and
what customers wanted. That gap splits cleanly in two:

    produced ────────────── forecast median ────────────── actual demand
             |<- plan drift ->|<---- forecast error ---->|

* **Plan drift** is production above the forecast. The model said one thing and the prep
  sheet said another. Nobody was surprised; nobody looked.
* **Forecast error** is the forecast above what actually happened. That one is ours.

Splitting them matters because the fixes are opposites. Plan drift is fixed by changing a
laminated card. Forecast error is fixed by a better model. Reporting them as one number —
"waste" — is why kitchens buy a second forecasting tool when their real problem is a card.

The remaining contributors are direct: spoilage traced to a zone above its set point, trim
above the standard yield, and supplier over-delivery.

Owner: Person A.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

import pandas as pd

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


def attribute(
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
