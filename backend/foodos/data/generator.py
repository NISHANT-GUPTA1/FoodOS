"""Synthetic dataset generator.

Produces the CSVs the seed loads. Deterministic: same seed, same numbers, every time —
which matters more than it sounds, because the deck quotes these figures and a demo that
reseeds to different numbers halfway through rehearsals is a demo nobody trusts.

Three pathologies are planted deliberately. They are documented in docs/pathologies.md
and each one is asserted by a test:

    1. PREVENT  — Gobi Manchurian production frozen at 80/day while weekday demand
                  stepped down three weeks ago. The forecast follows; the prep sheet does not.
    2. PRESERVE — COLD_2 runs at 9.2 degC against a 4 degC set point, so fresh dairy in it
                  ages roughly twice as fast as its label suggests.
    3. RECOVER  — a Sunday over-order of boneless chicken, surfacing on a Tuesday when
                  three of the recovery channels happen to be unavailable.

Everything else is ordinary business: weekday rhythm, weekend uplift, monsoon rain
suppressing delivery, the odd holiday, and noise.

    python -m foodos.data.generator            # writes backend/data/*.csv

Owner: Person A.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from ..config import CONTENT_DIR, DATA_DIR, get_config

# --- planted constants -------------------------------------------------------

#: Days before the demo date that weekday demand for the pathology dish stepped down.
STEP_CHANGE_DAYS_AGO = 21
PATHOLOGY_DISH = "gobi_manchurian"
PATHOLOGY_WEEKDAY_FACTOR = 0.76
PATHOLOGY_FROZEN_PLAN = 80.0

#: The prep sheet is a trailing average, so it lags demand by a week or two. That is
#: ordinary and mostly harmless — a competent kitchen tracks its own volumes. What is NOT
#: harmless is one dish whose number stopped moving altogether, which is pathology one.
#: Keeping the systemic lag small is deliberate: if every dish over-plans badly, the kitchen
#: just looks incompetent and the planted failure has nothing to stand out against.
PREP_SHEET_LAG_DAYS = 10
PREP_SHEET_WINDOW = 14
PREP_SHEET_CUSHION = 1.06

WARM_ZONE = "COLD_2"

#: Share of unsold production that is legitimately reused tomorrow rather than binned.
#: A gravy base keeps; a fried starter does not. This is why real kitchen waste is nearer
#: a tenth of purchases than a quarter, and it is also why the pathology dish is a wok
#: item — Gobi Manchurian is one of the few things on this menu with nowhere to go.
CARRYOVER_BY_CATEGORY = {
    "veg_main": 0.55,
    "nonveg_main": 0.55,
    "veg_rice": 0.30,
    "nonveg_rice": 0.30,
    "veg_noodles": 0.10,
    "starter_veg": 0.0,
    "bread": 0.0,
}


@dataclass(frozen=True)
class DishDemand:
    """Demand shape for one dish. Base is portions on an average Monday."""

    base: float
    weekend_uplift: float = 1.35
    rain_sensitivity: float = 0.0  # negative means rain suppresses it
    noise_cv: float = 0.22
    trend_per_100d: float = 0.0


DEMAND: dict[str, DishDemand] = {
    "chicken_biryani":    DishDemand(base=78, weekend_uplift=1.45, rain_sensitivity=0.10, noise_cv=0.20, trend_per_100d=0.06),
    "butter_naan":        DishDemand(base=120, weekend_uplift=1.40, noise_cv=0.18),
    "jeera_rice":         DishDemand(base=62, weekend_uplift=1.25, noise_cv=0.20),
    "butter_chicken":     DishDemand(base=54, weekend_uplift=1.42, noise_cv=0.21, trend_per_100d=0.04),
    "gobi_manchurian":    DishDemand(base=72, weekend_uplift=1.30, noise_cv=0.24),
    "paneer_butter_masala": DishDemand(base=44, weekend_uplift=1.38, noise_cv=0.22),
    "veg_hakka_noodles":  DishDemand(base=40, weekend_uplift=1.30, noise_cv=0.24),
    "dal_makhani":        DishDemand(base=37, weekend_uplift=1.28, noise_cv=0.20),
    "veg_biryani":        DishDemand(base=33, weekend_uplift=1.36, noise_cv=0.24),
    "chilli_paneer":      DishDemand(base=29, weekend_uplift=1.34, noise_cv=0.26),
    "chole":              DishDemand(base=26, weekend_uplift=1.22, noise_cv=0.24),
    "palak_paneer":       DishDemand(base=22, weekend_uplift=1.30, noise_cv=0.26),
    "mutton_rogan_josh":  DishDemand(base=14, weekend_uplift=1.70, noise_cv=0.30),
    "goan_fish_curry":    DishDemand(base=12, weekend_uplift=1.55, noise_cv=0.32),
}

#: Monday through Sunday. Indian delivery kitchens are quiet Monday, busy Friday to Sunday.
DOW_FACTOR = (0.86, 0.92, 0.95, 1.00, 1.22, 1.38, 1.30)

HOLIDAYS_2026 = {
    dt.date(2026, 3, 4), dt.date(2026, 3, 21), dt.date(2026, 4, 14),
    dt.date(2026, 5, 1), dt.date(2026, 8, 15), dt.date(2026, 8, 26),
}


def _load_yaml(name: str) -> dict[str, Any]:
    return yaml.safe_load((CONTENT_DIR / name).read_text(encoding="utf-8"))


class Generator:
    def __init__(self, demo_date: dt.date, history_days: int, seed: int) -> None:
        self.demo_date = demo_date
        self.history_days = history_days
        self.rng = np.random.default_rng(seed)

        self.recipes = _load_yaml("recipes.yaml")
        self.costs = _load_yaml("costs.yaml")
        self.yields = _load_yaml("yield_table.yaml")
        self.shelf = _load_yaml("shelf_life.yaml")

        self.dishes = {d["id"]: d for d in self.recipes["dishes"]}
        self.economics = {d["id"]: d for d in self.costs["dishes"]}
        self.ingredients = self.costs["ingredients"]
        self.zones = self.shelf["storage_zones"]

        self.dates = [
            demo_date - dt.timedelta(days=n) for n in range(history_days, 0, -1)
        ]
        self.step_date = demo_date - dt.timedelta(days=STEP_CHANGE_DAYS_AGO)

    # --- helpers -----------------------------------------------------------

    def prep_yield(self, ingredient: str) -> float:
        entry = self.yields["prep_yield"].get(ingredient)
        if isinstance(entry, dict):
            return float(entry["yield"])
        return float(self.yields["default_prep_yield"])

    def input_kg(self, dish_id: str) -> float:
        return float(self.economics[dish_id]["input_kg_per_portion"])

    def co2e(self, dish_id: str) -> float:
        return float(self.economics[dish_id]["co2e_kg_per_portion"])

    def food_cost(self, dish_id: str) -> float:
        return float(self.economics[dish_id]["food_cost_per_portion"])

    # --- context -----------------------------------------------------------

    def build_context(self) -> list[dict[str, Any]]:
        rows = []
        for date in self.dates + [self.demo_date]:
            dow = date.weekday()
            # Monsoon: June to September gets rain on roughly half its days.
            monsoon = date.month in (6, 7, 8, 9)
            rain = 0.0
            if self.rng.random() < (0.48 if monsoon else 0.08):
                rain = float(abs(self.rng.normal(14 if monsoon else 5, 9)))
            rows.append(
                {
                    "date": date.isoformat(),
                    "dow": dow,
                    "is_weekend": int(dow >= 5),
                    "is_holiday": int(date in HOLIDAYS_2026),
                    "rain_mm": round(rain, 1),
                    "temp_c": round(float(self.rng.normal(29 if not monsoon else 26, 2.5)), 1),
                    "promo": int(self.rng.random() < 0.06),
                    "local_event": int(self.rng.random() < 0.04),
                }
            )
        return rows

    # --- demand ------------------------------------------------------------

    def _demand(self, dish_id: str, date: dt.date, ctx: dict[str, Any], index: int) -> float:
        shape = DEMAND[dish_id]
        value = shape.base * DOW_FACTOR[date.weekday()]

        if date.weekday() >= 5:
            value *= shape.weekend_uplift / 1.30  # DOW_FACTOR already carries part of it

        value *= 1.0 + shape.trend_per_100d * (index / 100.0)

        if ctx["is_holiday"]:
            value *= 1.18
        if ctx["promo"]:
            value *= 1.25
        if ctx["local_event"]:
            value *= 1.15

        # Rain moves delivery volume up and dine-in down; net effect is small and positive.
        value *= 1.0 + shape.rain_sensitivity * min(ctx["rain_mm"], 30) / 30.0

        # PATHOLOGY 1: the weekday step change.
        if dish_id == PATHOLOGY_DISH and date >= self.step_date and date.weekday() < 4:
            value *= PATHOLOGY_WEEKDAY_FACTOR

        noise = self.rng.normal(1.0, shape.noise_cv)
        return max(0.0, value * max(0.25, noise))

    def _prep_sheet(self, dish_id: str, date: dt.date, history: dict[dt.date, float]) -> float:
        """What the laminated card says. A trailing mean, badly out of date."""
        if dish_id == PATHOLOGY_DISH and date.weekday() < 4:
            return PATHOLOGY_FROZEN_PLAN

        # Same weekday, two to five weeks back — "what did we do this time last month".
        # Kitchens do know that Saturday is not Tuesday, so a par level blind to weekday
        # would make every dish look mismanaged and leave the planted failure with nothing
        # to stand out against.
        window = [
            history[date - dt.timedelta(days=7 * week)]
            for week in range(2, 6)
            if (date - dt.timedelta(days=7 * week)) in history
        ]
        if not window:
            base = DEMAND[dish_id].base * DOW_FACTOR[date.weekday()]
        else:
            base = float(np.mean(window))
        # Kitchens plan a cushion, and they round to something a human can count.
        return max(1.0, round(base * PREP_SHEET_CUSHION / 5.0) * 5.0)

    def carryover(self, dish_id: str) -> float:
        return CARRYOVER_BY_CATEGORY.get(self.dishes[dish_id]["category"], 0.3)

    def build_demand(self, context: list[dict[str, Any]]) -> tuple[list[dict], list[dict], dict]:
        by_date = {dt.date.fromisoformat(c["date"]): c for c in context}
        sales_rows: list[dict[str, Any]] = []
        production_rows: list[dict[str, Any]] = []
        realised: dict[str, dict[dt.date, float]] = {d: {} for d in DEMAND}

        for index, date in enumerate(self.dates):
            ctx = by_date[date]
            for dish_id in DEMAND:
                demand = self._demand(dish_id, date, ctx, index)
                realised[dish_id][date] = demand

                planned = self._prep_sheet(dish_id, date, realised[dish_id])
                produced = planned  # the kitchen makes what the sheet says
                sold = min(produced, demand)

                price = float(self.economics[dish_id]["price"])
                sales_rows.append(
                    {
                        "date": date.isoformat(),
                        "dish_id": dish_id,
                        "qty_portions": round(sold, 1),
                        "revenue_inr": round(sold * price, 2),
                    }
                )
                production_rows.append(
                    {
                        "date": date.isoformat(),
                        "dish_id": dish_id,
                        "planned_portions": round(planned, 1),
                        "produced_portions": round(produced, 1),
                    }
                )

        # Demand for the demo date itself is never revealed — it is what we are forecasting.
        return sales_rows, production_rows, realised

    # --- zones -------------------------------------------------------------

    def build_zone_temperatures(self) -> list[dict[str, Any]]:
        rows = []
        for date in self.dates + [self.demo_date]:
            for zone_id, zone in self.zones.items():
                set_point = float(zone["set_temp_c"])
                typical = float(zone["typical_temp_c"])
                # PATHOLOGY 2: COLD_2 looks fine overnight and runs warm through service,
                # which is exactly why a morning spot check has never caught it.
                if zone_id == WARM_ZONE:
                    overnight = set_point + float(self.rng.normal(0.5, 0.3))
                    service = typical + float(self.rng.normal(0.0, 0.6))
                else:
                    overnight = set_point + float(self.rng.normal(0.3, 0.25))
                    service = typical + float(self.rng.normal(0.0, 0.35))
                rows.append(
                    {
                        "date": date.isoformat(),
                        "zone_id": zone_id,
                        "mean_temp_c": round((overnight * 14 + service * 10) / 24, 2),
                        "service_temp_c": round(service, 2),
                    }
                )
        return rows

    # --- waste -------------------------------------------------------------

    def build_waste(
        self, sales: list[dict], production: list[dict]
    ) -> list[dict[str, Any]]:
        sold = {(r["date"], r["dish_id"]): r["qty_portions"] for r in sales}
        rows: list[dict[str, Any]] = []

        for record in production:
            date, dish_id = record["date"], record["dish_id"]
            produced = record["produced_portions"]
            unsold = max(0.0, produced - sold[(date, dish_id)])
            binned = unsold * (1.0 - self.carryover(dish_id))

            if binned > 0.05:
                kg = binned * self.input_kg(dish_id)
                rows.append(
                    {
                        "date": date,
                        "product_id": dish_id,
                        "qty_kg": round(kg, 3),
                        "reason": "overproduction",
                        "value_inr": round(binned * self.food_cost(dish_id), 2),
                        "co2e_kg": round(binned * self.co2e(dish_id), 3),
                        "zone_id": "",
                    }
                )

            # Trim above the standard yield: mise cut for a bigger service than happened.
            excess = max(0.0, float(self.rng.normal(0.04, 0.035)))
            if excess > 0.02 and produced > 0:
                trim_kg = produced * self.input_kg(dish_id) * excess
                rows.append(
                    {
                        "date": date,
                        "product_id": dish_id,
                        "qty_kg": round(trim_kg, 3),
                        "reason": "trim",
                        "value_inr": round(trim_kg * self.food_cost(dish_id) / max(self.input_kg(dish_id), 1e-6), 2),
                        "co2e_kg": round(trim_kg * self.co2e(dish_id) / max(self.input_kg(dish_id), 1e-6), 3),
                        "zone_id": "",
                    }
                )

        # Spoilage, concentrated in the warm zone, on the short-life expensive items.
        perishable = ["paneer", "curd", "spinach", "coriander_leaves", "fish_basa_fillet",
                      "chicken_boneless", "tomato", "mint"]
        for date in self.dates:
            for ingredient in perishable:
                warm = ingredient in ("paneer", "curd", "spinach", "mint")
                if self.rng.random() > (0.30 if warm else 0.10):
                    continue
                kg = float(abs(self.rng.normal(0.9 if warm else 0.5, 0.4)))
                spec = self.ingredients[ingredient]
                rows.append(
                    {
                        "date": date.isoformat(),
                        "product_id": ingredient,
                        "qty_kg": round(kg, 3),
                        "reason": "spoilage",
                        "value_inr": round(kg * spec["unit_cost_per_kg"], 2),
                        "co2e_kg": round(kg * spec["co2e_kg_per_kg"], 3),
                        "zone_id": WARM_ZONE if warm else "COLD_1",
                    }
                )

            # Supplier over-delivery, occasionally.
            if self.rng.random() < 0.05:
                ingredient = str(self.rng.choice(["onion", "tomato", "cauliflower", "potato"]))
                kg = float(abs(self.rng.normal(2.0, 0.8)))
                spec = self.ingredients[ingredient]
                rows.append(
                    {
                        "date": date.isoformat(),
                        "product_id": ingredient,
                        "qty_kg": round(kg, 3),
                        "reason": "supplier",
                        "value_inr": round(kg * spec["unit_cost_per_kg"], 2),
                        "co2e_kg": round(kg * spec["co2e_kg_per_kg"], 3),
                        "zone_id": "DRY_1",
                    }
                )
        return rows

    # --- batches -----------------------------------------------------------

    def build_batches(self) -> tuple[list[dict], list[dict]]:
        """Open stock on the demo morning, including the two planted batches."""
        noon = dt.datetime.combine(self.demo_date, dt.time(11, 30))
        batches: list[dict[str, Any]] = []
        events: list[dict[str, Any]] = []

        def add(
            batch_id: str, product: str, zone: str, qty: float, age_days: float,
            state: str = "raw", is_cut: bool = False, ethylene: bool = False,
            unopened: bool = True,
        ) -> None:
            received = noon - dt.timedelta(days=age_days)
            batches.append(
                {
                    "id": batch_id,
                    "product_id": product,
                    "zone_id": zone,
                    "qty_kg": round(qty, 3),
                    "received_at": received.isoformat(timespec="minutes"),
                    "state": state,
                    "is_cut": int(is_cut),
                    "unit_cost_per_kg": self.ingredients[product]["unit_cost_per_kg"],
                    "is_open": 1,
                    "ethylene_exposed": int(ethylene),
                    "cold_chain_available": int(zone != "DRY_1"),
                    "unopened_packaging": int(unopened),
                }
            )
            events.append(
                {
                    "batch_id": batch_id,
                    "ts": received.isoformat(timespec="minutes"),
                    "event_type": "receive",
                    "qty_kg": round(qty, 3),
                    "note": "goods in",
                }
            )

        # PATHOLOGY 2 — cubed paneer, one day old, in the chiller that runs warm.
        add("B-1042", "paneer", WARM_ZONE, 4.4, age_days=1.0, state="prepped", is_cut=True,
            unopened=False)

        # PATHOLOGY 3 — Sunday's chicken over-order, surfacing on Tuesday.
        add("B-1057", "chicken_boneless", "MEAT_1", 9.6, age_days=0.5, state="raw")

        # Ordinary open stock, so the ledger looks like a real kitchen rather than a stage set.
        ordinary = [
            ("B-1061", "spinach", "COLD_1", 3.1, 1.4, "raw", False, True),
            ("B-1062", "tomato", "COLD_1", 12.5, 2.1, "raw", False, False),
            ("B-1063", "cauliflower", "COLD_1", 8.2, 1.8, "raw", False, True),
            ("B-1064", "curd", WARM_ZONE, 5.0, 1.9, "raw", False, False),
            ("B-1065", "onion", "DRY_1", 24.0, 6.0, "raw", False, False),
            ("B-1066", "chicken_bone_in", "MEAT_1", 11.2, 0.8, "raw", False, False),
            ("B-1067", "mutton", "MEAT_1", 4.8, 1.1, "raw", False, False),
            ("B-1068", "fish_basa_fillet", "MEAT_1", 3.2, 0.6, "raw", False, False),
            ("B-1069", "coriander_leaves", WARM_ZONE, 0.9, 1.2, "raw", True, True),
            ("B-1070", "capsicum", "COLD_1", 4.4, 2.6, "raw", False, True),
            ("B-1071", "green_peas_frozen", "FREEZER_1", 9.0, 21.0, "raw", False, False),
            ("B-1072", "rice_basmati", "DRY_1", 40.0, 15.0, "raw", False, False),
            ("B-1073", "paneer", "COLD_1", 6.0, 0.4, "raw", False, False),
            ("B-1074", "potato", "DRY_1", 18.0, 5.0, "raw", False, False),
        ]
        for batch_id, product, zone, qty, age, state, cut, ethylene in ordinary:
            add(batch_id, product, zone, qty, age, state, cut, ethylene)

        return batches, events


# --- writing ----------------------------------------------------------------

def _write(path: Path, rows: list[dict[str, Any]]) -> int:
    if not rows:
        path.write_text("", encoding="utf-8")
        return 0
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def generate(
    out_dir: Path | None = None,
    demo_date: dt.date | None = None,
    history_days: int | None = None,
    seed: int | None = None,
    quiet: bool = False,
) -> dict[str, int]:
    config = get_config()
    out_dir = Path(out_dir) if out_dir else DATA_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    demo_date = demo_date or config.demo_date
    if demo_date.weekday() != 1:
        raise ValueError(
            f"demo date {demo_date} is a {demo_date.strftime('%A')}, not a Tuesday. "
            "Pathology three depends on the NGO channel being closed today."
        )

    gen = Generator(demo_date, history_days or config.history_days, seed or config.seed)

    context = gen.build_context()
    sales, production, _ = gen.build_demand(context)
    zone_temps = gen.build_zone_temperatures()
    waste = gen.build_waste(sales, production)
    batches, events = gen.build_batches()

    counts = {
        "demand_context.csv": _write(out_dir / "demand_context.csv", context),
        "sales.csv": _write(out_dir / "sales.csv", sales),
        "production.csv": _write(out_dir / "production.csv", production),
        "batches.csv": _write(out_dir / "batches.csv", batches),
        "inventory_events.csv": _write(out_dir / "inventory_events.csv", events),
        "waste_events.csv": _write(out_dir / "waste_events.csv", waste),
        "zone_temperatures.csv": _write(out_dir / "zone_temperatures.csv", zone_temps),
    }

    if not quiet:
        print(f"generated {gen.history_days} days of history to {demo_date} ({out_dir})")
        for name, count in counts.items():
            print(f"  {name:24} {count:6} rows")
    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="foodos.data.generator")
    parser.add_argument("--out", default=None)
    parser.add_argument("--demo-date", default=None)
    parser.add_argument("--history-days", type=int, default=None)
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args(argv)

    generate(
        out_dir=Path(args.out) if args.out else None,
        demo_date=dt.date.fromisoformat(args.demo_date) if args.demo_date else None,
        history_days=args.history_days,
        seed=args.seed,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
