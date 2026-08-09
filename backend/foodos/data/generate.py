"""Synthetic dataset generator for one commercial kitchen.

OWNER: Person A (Data & Models).
CONTRACT (frozen at H3):  generate_dataset(out_dir, days=90, seed=42) -> None

Writes eight CSVs that every other module reads:

    sites.csv            one kitchen
    storage_zones.csv    declared zone temperatures (no sensors anywhere)
    products.csv         40 ingredients + 14 dishes
    recipes.csv          flattened Recipe + RecipeLine, with standard yields
    demand_context.csv   dow, holiday, festival, weather, promo, covers
    sales.csv            POS lines, per dish per day
    production.csv       planned vs actual portions, per dish per day
    goods_receipt.csv    batches at intake, with zone and dock dwell time
    waste.csv            every waste event, reason-coded and stage-coded

Three faults are planted on purpose. The engine has to rediscover them:

    1. Friday chicken biryani produced ~23% above what sells.
    2. Cauliflower prep yield 0.51 against a 0.58 standard.
    3. A spinach receipt left 4 hours on a 31 C dock, losing ~2.7 days of life.

The simulation is deterministic: same seed, same bytes.
"""

from __future__ import annotations

import os
from datetime import date, timedelta

import numpy as np
import pandas as pd

from . import catalog as C


# --------------------------------------------------------------------------
# Spoilage kinetics — the same Q10 model the RSL engine uses later
# --------------------------------------------------------------------------

def _life_burn_rate(category: str, temp_c: float, intake_grade: float) -> float:
    """Fraction of total shelf life consumed per day at `temp_c`."""
    base_days, ref_temp, q10, _cut, _sens, _emit = C.SHELF_LIFE_PROFILES[category]
    accel = q10 ** ((temp_c - ref_temp) / 10.0)
    return (1.0 / base_days) * accel / max(intake_grade, 0.35)


def _dock_life_burn(category: str, dwell_hours: float, intake_grade: float) -> float:
    dock_temp = dict((z[0], z[2]) for z in C.STORAGE_ZONES)["ZN_DOCK"]
    return _life_burn_rate(category, dock_temp, intake_grade) * (dwell_hours / 24.0)


def _rsl_days(category: str, life_used: float) -> float:
    base_days = C.SHELF_LIFE_PROFILES[category][0]
    return round(max(0.0, base_days * (1.0 - life_used)), 2)


# --------------------------------------------------------------------------
# Demand
# --------------------------------------------------------------------------

def _weather(rng: np.random.Generator, d: date) -> tuple[str, float]:
    """Bengaluru, mid-November to mid-February."""
    seasonal = 29.5 - 3.0 * np.sin((d.timetuple().tm_yday - 330) / 90.0 * np.pi)
    temp_max = float(np.clip(seasonal + rng.normal(0, 1.6), 21.0, 34.0))
    roll = rng.random()
    code = "rain" if roll < 0.08 else ("cloudy" if roll < 0.34 else "clear")
    return code, round(temp_max, 1)


def _demand_lambda(dish_id: str, base: float, d: date, ctx: dict,
                   day_index: int, n_days: int) -> float:
    lam = base * C.dow_multiplier(dish_id, d.weekday())
    lam *= ctx["festival_mult"]
    if ctx["weather_code"] == "rain":
        lam *= 0.88
    promo = C.PROMO_RULES.get(dish_id)
    if promo and d.weekday() == promo[0]:
        lam *= promo[1]
    lam *= 1.0 + 0.10 * (day_index / max(n_days - 1, 1))     # slow growth
    return max(lam, 1.0)


# --------------------------------------------------------------------------
# Inventory
# --------------------------------------------------------------------------

class _Batch:
    __slots__ = ("batch_id", "product_id", "category", "received_on",
                 "qty_remaining", "life_used", "intake_grade", "unit_cost",
                 "zone_id", "zone_temp", "printed_expiry", "buried")

    def __init__(self, batch_id, product_id, category, received_on, qty,
                 intake_grade, unit_cost, zone_id, zone_temp, printed_expiry):
        self.buried = 0
        self.batch_id = batch_id
        self.product_id = product_id
        self.category = category
        self.received_on = received_on
        self.qty_remaining = qty
        self.life_used = 0.0
        self.intake_grade = intake_grade
        self.unit_cost = unit_cost
        self.zone_id = zone_id
        self.zone_temp = zone_temp
        self.printed_expiry = printed_expiry


# --------------------------------------------------------------------------
# Main entry point
# --------------------------------------------------------------------------

def generate_dataset(out_dir: str, days: int = 90, seed: int = 42,
                     end_date: str = C.DEFAULT_END_DATE) -> None:
    # Three independent streams. The inventory simulation draws a variable
    # number of randoms per day (it depends on how many batches are open), so
    # a single stream would make demand chaotic in the parameters: changing an
    # order buffer would silently change Friday's biryani demand. Splitting the
    # streams keeps demand fixed while inventory behaviour is tuned.
    rng_ctx = np.random.default_rng(seed)          # weather
    rng = np.random.default_rng(seed + 1)          # demand, production, service
    rng_inv = np.random.default_rng(seed + 2)      # yields, ordering, storage
    os.makedirs(out_dir, exist_ok=True)

    end = date.fromisoformat(end_date)
    dates = [end - timedelta(days=days - 1 - i) for i in range(days)]

    zone_temp = {z[0]: z[2] for z in C.STORAGE_ZONES}
    excursion_date = dates[-1] - timedelta(days=C.DOCK_EXCURSION["days_before_end"])

    sales_rows, production_rows, context_rows = [], [], []
    receipt_rows, waste_rows, event_rows = [], [], []

    inventory: dict[str, list[_Batch]] = {i[0]: [] for i in C.INGREDIENTS}
    usage_history: dict[str, list[float]] = {i[0]: [] for i in C.INGREDIENTS}
    batch_counter = 0

    for day_index, d in enumerate(dates):
        iso = d.isoformat()
        festival, festival_mult = C.FESTIVAL_CALENDAR.get(iso, ("", 1.0))
        weather_code, temp_max = _weather(rng_ctx, d)
        ctx = {"festival_mult": festival_mult, "weather_code": weather_code}

        # ---- demand, production and sales --------------------------------
        day_sold_total = 0
        net_requirement: dict[str, float] = {}

        for dish_id, name, price, portion_kg, base in C.DISHES:
            lam = _demand_lambda(dish_id, base, d, ctx, day_index, days)
            true_demand = int(rng.poisson(lam))

            factor = C.overprep_factor(dish_id)
            if dish_id == "DSH_CHBIRYANI" and d.weekday() == 4:
                factor = C.FRIDAY_BIRYANI_OVERPREP      # PLANTED FAULT 1
            if dish_id in C.MADE_TO_ORDER:
                planned = int(round(lam * factor))
                actual = true_demand          # fired to order, nothing left over
                sold = true_demand
                unsold = 0
            else:
                planned = int(round(lam * factor))
                actual = max(1, int(round(planned * rng.normal(1.0, 0.025))))
                sold = min(true_demand, actual)
                unsold = actual - sold
            day_sold_total += sold

            sales_rows.append({
                "sale_id": f"S_{iso}_{dish_id}",
                "site_id": C.SITE["site_id"], "product_id": dish_id,
                "business_date": iso, "qty": sold,
                "revenue": round(sold * price, 2), "channel": "dine_in",
            })
            production_rows.append({
                "production_id": f"P_{iso}_{dish_id}",
                "site_id": C.SITE["site_id"], "product_id": dish_id,
                "business_date": iso, "planned_qty": planned,
                "actual_qty": actual, "uom": "portion",
            })

            if unsold > 0:
                binned = unsold * C.UNSOLD_WASTED.get(dish_id, C.UNSOLD_WASTED["default"])
                if binned > 0.4:
                    waste_rows.append({
                        "site_id": C.SITE["site_id"], "business_date": iso,
                        "product_id": dish_id, "batch_id": "",
                        "qty": round(binned * portion_kg, 3), "uom": "kg",
                        "value": round(binned * C.dish_food_cost(dish_id), 2),
                        "reason": "overproduction", "stage": "post_service",
                        "capture_method": "pos_derived",
                        "note": f"{unsold} portions unsold, {binned:.1f} binned",
                    })

            # plate waste on what was served
            returned = int(rng.binomial(sold, C.PLATE_WASTE_RATE))
            if returned > 0:
                kg = returned * portion_kg * C.PLATE_WASTE_FRACTION
                waste_rows.append({
                    "site_id": C.SITE["site_id"], "business_date": iso,
                    "product_id": dish_id, "batch_id": "",
                    "qty": round(kg, 3), "uom": "kg",
                    "value": round(returned * C.PLATE_WASTE_FRACTION
                                   * C.dish_food_cost(dish_id), 2),
                    "reason": "plate_waste", "stage": "service",
                    "capture_method": "manual",
                    "note": f"{returned} plates partly returned",
                })

            # you prep for what you produce, not for what you sell
            for ing_id, net_qty in C.recipe_lines(dish_id):
                net_requirement[ing_id] = net_requirement.get(ing_id, 0.0) + net_qty * actual

        covers = int(round(day_sold_total / 3.3))

        # Sides go out with every cover: produced to order, none left over.
        for ing_id, net_qty in C.recipe_lines(C.SIDES["product_id"]):
            net_requirement[ing_id] = net_requirement.get(ing_id, 0.0) + net_qty * covers
        sales_rows.append({
            "sale_id": f"S_{iso}_{C.SIDES['product_id']}",
            "site_id": C.SITE["site_id"], "product_id": C.SIDES["product_id"],
            "business_date": iso, "qty": covers, "revenue": 0.0, "channel": "dine_in",
        })
        production_rows.append({
            "production_id": f"P_{iso}_{C.SIDES['product_id']}",
            "site_id": C.SITE["site_id"], "product_id": C.SIDES["product_id"],
            "business_date": iso, "planned_qty": covers, "actual_qty": covers,
            "uom": "portion",
        })

        context_rows.append({
            "site_id": C.SITE["site_id"], "business_date": iso,
            "dow": d.weekday(), "is_holiday": int(iso in C.HOLIDAYS),
            "festival": festival, "weather_code": weather_code,
            "temp_max_c": temp_max,
            "promo_flag": int(any(d.weekday() == r[0] for r in C.PROMO_RULES.values())),
            "covers": covers,
        })

        # ---- gross requirement and prep trim ------------------------------
        gross_requirement: dict[str, float] = {}
        for ing_id, net_qty in net_requirement.items():
            true_yield = C.TRUE_YIELD.get(ing_id)
            if true_yield is None:
                gross_requirement[ing_id] = net_qty
                continue
            achieved = float(np.clip(rng_inv.normal(true_yield, 0.012), 0.30, 0.99))
            gross = net_qty / achieved
            gross_requirement[ing_id] = gross
            trim = (gross - net_qty) * C.TRIM_CAPTURE_RATE
            if trim > 0.02:
                waste_rows.append({
                    "site_id": C.SITE["site_id"], "business_date": iso,
                    "product_id": ing_id, "batch_id": "",
                    "qty": round(trim, 3), "uom": "kg",
                    "value": round(trim * C.ingredient_cost(ing_id), 2),
                    "reason": "prep_trim", "stage": "prep",
                    "capture_method": "manual",
                    "note": f"yield {achieved:.2f} on {net_qty:.2f} kg net",
                })

        # ---- goods receipt ------------------------------------------------
        for ing_id, _n, category, uom, unit_cost, _p, _c in C.INGREDIENTS:
            cycle = C.ORDER_CYCLE_DAYS[category]
            if day_index % cycle != 0:
                continue

            is_excursion = (ing_id == C.DOCK_EXCURSION["product_id"]
                            and d == excursion_date)

            hist = usage_history[ing_id][-7:]
            expected_daily = float(np.mean(hist)) if hist else gross_requirement.get(ing_id, 0.0)
            on_hand = sum(b.qty_remaining for b in inventory[ing_id])
            target = expected_daily * cycle * (1.0 + C.ORDER_BUFFER[category])
            order_qty = target - on_hand * C.ON_HAND_NETTING
            if category in C.STANDING_ORDER_CATEGORIES:
                order_qty = max(order_qty, C.STANDING_ORDER_FRACTION
                                * expected_daily * cycle)
            if is_excursion:
                # the oversized delivery happens regardless of what is on hand —
                # that is exactly why there was no room for it and it sat outside
                order_qty = max(order_qty, expected_daily * cycle)
            elif order_qty <= 0.01:
                continue
            order_qty *= rng_inv.normal(1.0, 0.05)
            if rng_inv.random() < C.OPPORTUNISTIC_BUY_PROB:
                order_qty *= C.OPPORTUNISTIC_BUY_MULT
            # suppliers deliver whole crates
            crate = C.CRATE_SIZE_KG[category]
            order_qty = float(np.ceil(order_qty / crate) * crate)
            if order_qty <= 0.01:
                continue

            batch_counter += 1
            batch_id = f"B{batch_counter:05d}"
            grade = float(np.clip(rng_inv.normal(0.94, 0.05), 0.62, 1.0))

            # PLANTED FAULT 3 — the dock excursion
            dwell = C.NORMAL_DOCK_DWELL_HOURS
            if is_excursion:
                dwell = C.DOCK_EXCURSION["dwell_hours"]
                order_qty = round(order_qty * C.DOCK_EXCURSION["order_multiplier"], 2)

            # quality rejection at the gate
            rejected = 0.0
            if _p and rng_inv.random() < C.QUALITY_REJECT_PROB:
                rejected = round(order_qty * float(rng_inv.uniform(0.04, 0.13)), 3)
                waste_rows.append({
                    "site_id": C.SITE["site_id"], "business_date": iso,
                    "product_id": ing_id, "batch_id": batch_id,
                    "qty": rejected, "uom": "kg",
                    "value": round(rejected * unit_cost, 2),
                    "reason": "quality_rejection", "stage": "storage",
                    "capture_method": "manual",
                    "note": f"rejected at goods receipt, intake grade {grade:.2f}",
                })

            accepted = round(order_qty - rejected, 3)
            zone_id = C.ZONE_FOR_CATEGORY[category]
            base_days = C.SHELF_LIFE_PROFILES[category][0]
            batch = _Batch(batch_id, ing_id, category, iso, accepted, grade,
                           unit_cost, zone_id, zone_temp[zone_id],
                           (d + timedelta(days=int(round(base_days)))).isoformat())
            batch.life_used = _dock_life_burn(category, dwell, grade)
            batch.buried = int(len(inventory[ing_id]) > 0
                               and rng_inv.random() < C.BURIED_BATCH_PROB)
            inventory[ing_id].append(batch)

            receipt_rows.append({
                "batch_id": batch_id, "site_id": C.SITE["site_id"],
                "product_id": ing_id, "lot_code": f"LOT-{batch_id}",
                "received_at": f"{iso}T07:00:00", "printed_expiry": batch.printed_expiry,
                "qty_received": accepted, "uom": uom,
                "storage_zone_id": zone_id, "dock_dwell_hours": dwell,
                "intake_grade": round(grade, 3), "unit_cost": unit_cost,
                "state": "whole",
            })
            event_rows.append({
                "site_id": C.SITE["site_id"], "batch_id": batch_id,
                "product_id": ing_id, "ts": f"{iso}T07:00:00", "type": "receive",
                "qty": accepted, "uom": "kg", "ref": f"LOT-{batch_id}",
            })

        # ---- consume ---------------------------------------------------------
        # The kitchen picks by the date printed on the crate, because that is
        # the only thing it can see. It has no way to know that one crate has
        # already lost half its life on the dock. That blindness is the point.
        for ing_id, need in gross_requirement.items():
            usage_history[ing_id].append(need)
            # A crate stacked at the back of the walk-in stays at the back: it is
            # picked only once everything in front of it is gone, which for a
            # short-life item is often never. That is what kills it.
            #
            # Burial reorders the pick, it never removes stock. Skipping it
            # outright would let the kitchen produce dishes without consuming
            # ingredients, which silently breaks the yield benchmark downstream.
            batches = sorted(inventory[ing_id],
                             key=lambda b: (b.buried, b.received_on, b.batch_id))
            for b in batches:
                if need <= 1e-6:
                    break
                take = min(b.qty_remaining, need)
                b.qty_remaining -= take
                need -= take
                event_rows.append({
                    "site_id": C.SITE["site_id"], "batch_id": b.batch_id,
                    "product_id": ing_id, "ts": f"{iso}T09:00:00", "type": "consume",
                    "qty": round(take, 4), "uom": "kg", "ref": "prep",
                })
            inventory[ing_id] = [b for b in inventory[ing_id] if b.qty_remaining > 1e-6]

        # ---- age and expire -------------------------------------------------
        for ing_id, batches in inventory.items():
            survivors = []
            for b in batches:
                if b.received_on != iso:      # a batch received today ages from tomorrow
                    b.life_used += _life_burn_rate(b.category, b.zone_temp, b.intake_grade)
                if b.life_used >= 1.0:
                    waste_rows.append({
                        "site_id": C.SITE["site_id"], "business_date": iso,
                        "product_id": ing_id, "batch_id": b.batch_id,
                        "qty": round(b.qty_remaining, 3), "uom": "kg",
                        "value": round(b.qty_remaining * b.unit_cost, 2),
                        "reason": "spoilage", "stage": "storage",
                        "capture_method": "manual",
                        "note": f"received {b.received_on}, zone {b.zone_id}",
                    })
                    event_rows.append({
                        "site_id": C.SITE["site_id"], "batch_id": b.batch_id,
                        "product_id": ing_id, "ts": f"{iso}T23:00:00",
                        "type": "waste", "qty": round(b.qty_remaining, 4),
                        "uom": "kg", "ref": "spoilage",
                    })
                else:
                    survivors.append(b)
            inventory[ing_id] = survivors

    # ---- context for the day being planned --------------------------------
    # Tomorrow has no sales yet, but its calendar and its weather forecast are
    # both known today, and the forecaster needs them to predict it.
    plan_day = date.fromisoformat(C.PLAN_DATE)
    plan_festival, _ = C.FESTIVAL_CALENDAR.get(C.PLAN_DATE, ("", 1.0))
    plan_weather, plan_temp = _weather(rng_ctx, plan_day)
    context_rows.append({
        "site_id": C.SITE["site_id"], "business_date": C.PLAN_DATE,
        "dow": plan_day.weekday(), "is_holiday": int(C.PLAN_DATE in C.HOLIDAYS),
        "festival": plan_festival, "weather_code": plan_weather,
        "temp_max_c": plan_temp,
        "promo_flag": int(any(plan_day.weekday() == r[0]
                              for r in C.PROMO_RULES.values())),
        "covers": "",          # not known until the day is over
    })

    # ---- open batches at the end of the window ----------------------------
    open_rows = []
    for ing_id, batches in inventory.items():
        for b in batches:
            category = b.category
            open_rows.append({
                "batch_id": b.batch_id, "site_id": C.SITE["site_id"],
                "product_id": ing_id, "qty_remaining": round(b.qty_remaining, 3),
                "uom": "kg", "storage_zone_id": b.zone_id,
                "received_at": f"{b.received_on}T07:00:00",
                "printed_expiry": b.printed_expiry,
                "intake_grade": round(b.intake_grade, 3),
                "life_used": round(b.life_used, 4),
                "rsl_days": _rsl_days(category, b.life_used),
                "unit_cost": b.unit_cost,
                "value_on_hand": round(b.qty_remaining * b.unit_cost, 2),
                "state": "whole",
            })

    # ---- catalogue tables ---------------------------------------------------
    product_rows = []
    for pid, name, category, uom, cost, is_produce, co2e in C.INGREDIENTS:
        product_rows.append({
            "product_id": pid, "sku": pid.replace("ING_", "SKU-"), "name": name,
            "category": category, "uom": uom, "unit_cost": cost,
            "unit_price": "", "is_dish": 0,
            "perishable": int(category != "dry"), "is_produce": int(is_produce),
            "co2e_kg_per_uom": co2e, "portion_kg": "", "plannable": 0,
        })
    menu = [(d[0], d[1], d[2], d[3]) for d in C.DISHES]
    menu.append((C.SIDES["product_id"], C.SIDES["name"], C.SIDES["price"],
                 C.SIDES["portion_kg"]))
    for did, name, price, portion_kg in menu:
        product_rows.append({
            "product_id": did, "sku": did.replace("DSH_", "MENU-"), "name": name,
            "category": "dish", "uom": "portion",
            "unit_cost": C.dish_food_cost(did), "unit_price": price, "is_dish": 1,
            "perishable": 1, "is_produce": 0, "co2e_kg_per_uom": C.dish_co2e(did),
            "portion_kg": portion_kg,
            # There is only a quantity decision to make where the kitchen
            # batch-prepares ahead of service. Breads and dosa are fired to
            # order and the sides go out with the cover count, so no newsvendor
            # applies: planning a quantity for them would invent both a waste
            # figure and a saving that do not exist.
            "plannable": int(price > 0 and did not in C.MADE_TO_ORDER),
        })

    recipe_rows = []
    for did in C.RECIPES:
        for ing_id, qty in C.recipe_lines(did):
            recipe_rows.append({
                "recipe_id": f"R_{did}", "product_id": did,
                "yield_qty": 1, "yield_uom": "portion",
                "ingredient_product_id": ing_id, "qty": qty, "uom": "kg",
                "standard_yield_pct": C.STANDARD_YIELD.get(ing_id, 1.0),
            })

    site_rows = [C.SITE]
    zone_rows = [{"storage_zone_id": z[0], "site_id": C.SITE["site_id"],
                  "name": z[1], "mean_temp_c": z[2], "temp_source": z[3]}
                 for z in C.STORAGE_ZONES]

    # ---- write ---------------------------------------------------------------
    waste_df = pd.DataFrame(waste_rows)
    waste_df.insert(0, "waste_id", [f"W{i:06d}" for i in range(1, len(waste_df) + 1)])

    tables = {
        "sites.csv": pd.DataFrame(site_rows),
        "storage_zones.csv": pd.DataFrame(zone_rows),
        "products.csv": pd.DataFrame(product_rows),
        "recipes.csv": pd.DataFrame(recipe_rows),
        "demand_context.csv": pd.DataFrame(context_rows),
        "sales.csv": pd.DataFrame(sales_rows),
        "production.csv": pd.DataFrame(production_rows),
        "goods_receipt.csv": pd.DataFrame(receipt_rows),
        "waste.csv": waste_df,
        "open_batches.csv": pd.DataFrame(open_rows),
        "inventory_events.csv": pd.DataFrame(event_rows),
    }
    for filename, df in tables.items():
        df.to_csv(os.path.join(out_dir, filename), index=False)

    _print_summary(tables, dates)


# --------------------------------------------------------------------------
# Sanity report — run this every time you change a parameter
# --------------------------------------------------------------------------

def _print_summary(tables: dict[str, pd.DataFrame], dates: list[date]) -> None:
    waste = tables["waste.csv"]
    products = tables["products.csv"].set_index("product_id")
    sales = tables["sales.csv"]

    n_months = len(dates) / 30.0
    purchase = float((tables["goods_receipt.csv"]["qty_received"]
                      * tables["goods_receipt.csv"]["unit_cost"]).sum())
    total_value = float(waste["value"].sum())
    total_kg = float(waste["qty"].sum())

    print(f"\nFoodOS synthetic dataset — {dates[0]} to {dates[-1]} ({len(dates)} days)")
    print(f"  revenue          Rs {sales['revenue'].sum():>12,.0f}")
    print(f"  purchases        Rs {purchase:>12,.0f}"
          f"   (food cost {purchase / float(sales['revenue'].sum()) * 100:.1f}% of revenue)")
    print(f"  waste            Rs {total_value:>12,.0f}   {total_kg:,.0f} kg"
          f"   ({total_value / purchase * 100:.1f}% of purchases)")
    print(f"  per month        Rs {total_value / n_months:>12,.0f}"
          f"   {total_kg / n_months:,.0f} kg")

    print("\n  waste by cause (share of value)")
    by_cause = waste.groupby("reason")["value"].sum().sort_values(ascending=False)
    for reason, value in by_cause.items():
        bar = "#" * int(round(value / total_value * 40))
        print(f"    {reason:<18} {value / total_value * 100:5.1f}%  {bar}")

    produce_ids = set(products[products["is_produce"] == 1].index)
    dish_ids = set(products[products["is_dish"] == 1].index)
    produce_kg = float(waste[waste["product_id"].isin(produce_ids)]["qty"].sum())
    dish_kg = float(waste[waste["product_id"].isin(dish_ids)]["qty"].sum())
    print(f"\n  fruit & veg share of wasted weight   "
          f"{produce_kg / total_kg * 100:.1f}%  (dishes {dish_kg / total_kg * 100:.1f}%)")

    print("\n  top contributors by value")
    top = waste.groupby("product_id")["value"].sum().sort_values(ascending=False).head(6)
    for pid, value in top.items():
        print(f"    {products.loc[pid, 'name']:<22} Rs {value:>9,.0f}")

    print("\n  planted faults")
    prod = tables["production.csv"].merge(sales, on=["product_id", "business_date"])
    prod["dow"] = pd.to_datetime(prod["business_date"]).dt.weekday
    bir = prod[(prod["product_id"] == "DSH_CHBIRYANI")]

    def over_pct(frame: pd.DataFrame) -> float:
        # ratio of totals, not mean of daily ratios: a single low-demand day
        # would otherwise dominate the average
        return (frame["actual_qty"].sum() - frame["qty"].sum()) / frame["qty"].sum() * 100

    print(f"    1. biryani over-production  Friday {over_pct(bir[bir['dow'] == 4]):5.1f}%"
          f"   other days {over_pct(bir[bir['dow'] != 4]):5.1f}%")
    cauli = waste[(waste["product_id"] == "ING_CAULI") & (waste["reason"] == "prep_trim")]
    cauli_trim = float(cauli["qty"].sum())
    print(f"    2. cauliflower trim         {cauli_trim:,.0f} kg over the window"
          f"   ({cauli_trim / n_months:,.0f} kg/month)")
    spin = tables["open_batches.csv"]
    spin = spin[spin["product_id"] == "ING_SPINACH"]
    print(f"    3. spinach batches open at end of window: {len(spin)}"
          f"   min RSL {spin['rsl_days'].min() if len(spin) else float('nan'):.2f} d")
    print()


if __name__ == "__main__":
    here = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    generate_dataset(os.path.join(here, "data", "sample"))
