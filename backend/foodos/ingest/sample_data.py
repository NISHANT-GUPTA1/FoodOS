"""Built-in deterministic fixture.

This is **B's test fixture**, not A's dataset. `data/` is A's. This exists so
the engine, the API and the tests are never blocked waiting on anyone, and so
`git clone && seed && uvicorn` produces a working system.

Three faults are planted on purpose, because an engine that discovers a real
problem is far more convincing than one that recites a total:

  1. Friday over-prep on chicken biryani  (~34% over, vs ~12% other days)
  2. Cauliflower trim yield 0.51 against a 0.58 standard
  3. A 4-hour dock excursion at 31 C that costs the spinach ~2 days of life

Deterministic: one fixed RNG seed, no wall-clock reads. Same database every run.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import numpy as np
from sqlalchemy.orm import Session

from foodos.ingest.shelf_life import ShelfLifeInputs, estimate
from foodos.schema.enums import (
    BatchState,
    InventoryEventType,
    SiteType,
    Track,
    WasteReason,
    WasteStage,
)
from foodos.schema.tables import (
    Batch,
    DemandContext,
    InventoryEvent,
    Organization,
    Product,
    ProductionRecord,
    Recipe,
    RecipeLine,
    SalesRecord,
    ShelfLifeProfile,
    Site,
    StorageZone,
    WasteEvent,
)

SEED = 7
HISTORY_DAYS = 90

# category -> (base_days, ref_temp, q10, cut_factor, sensitive, emitter)
PROFILES = {
    "leafy_green": (7.0, 4.0, 2.5, 0.35, True, False),
    "vegetable": (10.0, 6.0, 2.2, 0.40, False, False),
    "fruiting_vegetable": (8.0, 8.0, 2.3, 0.40, False, True),
    "fruit": (7.0, 8.0, 2.4, 0.45, False, True),
    "dairy": (12.0, 4.0, 2.8, 0.50, False, False),
    "meat": (4.0, 2.0, 2.6, 0.50, False, False),
    "staple": (180.0, 20.0, 1.2, 0.80, False, False),
    "bakery": (3.0, 20.0, 1.8, 0.60, False, False),
    # Onions and potatoes are stored at ambient on purpose and keep for weeks.
    # Scoring them against a 6 C reference would decay them to zero in a week
    # and flood the ledger with false criticals.
    "root_ambient": (30.0, 25.0, 1.5, 0.40, False, False),
}

# name, sku, base_demand, price, cost, portion_kg, dow_factors, overprep
DISHES = [
    ("Chicken Biryani", "D-BIR", 52, 278.0, 92.0, 0.45,
     (0.82, 0.85, 0.88, 0.95, 1.15, 1.25, 1.18), "friday"),
    ("Paneer Butter Masala", "D-PBM", 40, 240.0, 88.0, 0.35,
     (0.90, 0.92, 0.95, 1.00, 1.10, 1.15, 1.08), "steady"),
    ("Dal Tadka", "D-DAL", 46, 150.0, 38.0, 0.30,
     (1.00, 1.00, 0.98, 1.02, 1.05, 1.00, 0.95), "steady"),
    ("Butter Naan", "D-NAN", 105, 45.0, 12.0, 0.09,
     (0.88, 0.90, 0.93, 1.00, 1.12, 1.22, 1.15), "high"),
    ("Veg Pulao", "D-PUL", 30, 180.0, 62.0, 0.40,
     (0.95, 0.95, 1.00, 1.00, 1.08, 1.10, 1.05), "steady"),
    ("Palak Paneer", "D-PAL", 26, 250.0, 96.0, 0.35,
     (0.92, 0.95, 0.98, 1.02, 1.08, 1.12, 1.05), "steady"),
]

# name, sku, category, profile, cost_per_kg, standard_yield, actual_yield
INGREDIENTS = [
    ("Tomato", "I-TOM", "vegetable", "fruiting_vegetable", 34.0, 0.91, 0.89),
    ("Onion", "I-ONI", "vegetable", "root_ambient", 30.0, 0.89, 0.88),
    ("Potato", "I-POT", "vegetable", "root_ambient", 26.0, 0.81, 0.80),
    ("Spinach", "I-SPI", "leafy_green", "leafy_green", 40.0, 0.74, 0.72),
    ("Cauliflower", "I-CAU", "vegetable", "vegetable", 38.0, 0.58, 0.51),  # fault 2
    ("Capsicum", "I-CAP", "vegetable", "vegetable", 60.0, 0.82, 0.81),
    ("Carrot", "I-CAR", "vegetable", "vegetable", 40.0, 0.82, 0.81),
    ("Coriander", "I-COR", "leafy_green", "leafy_green", 80.0, 0.60, 0.57),
    ("Paneer", "I-PNR", "dairy", "dairy", 320.0, 1.00, 1.00),
    ("Chicken", "I-CHK", "meat", "meat", 240.0, 0.92, 0.91),
    ("Basmati Rice", "I-RIC", "staple", "staple", 62.0, 1.00, 1.00),
]

# dish sku -> [(ingredient sku, kg per portion)]
RECIPES = {
    "D-BIR": [("I-RIC", 0.120), ("I-CHK", 0.150), ("I-ONI", 0.060),
              ("I-TOM", 0.040), ("I-COR", 0.005)],
    "D-PBM": [("I-PNR", 0.100), ("I-TOM", 0.120), ("I-ONI", 0.050),
              ("I-COR", 0.004)],
    "D-DAL": [("I-ONI", 0.030), ("I-TOM", 0.030), ("I-COR", 0.003)],
    "D-NAN": [],
    "D-PUL": [("I-RIC", 0.110), ("I-CAR", 0.040), ("I-CAP", 0.030),
              ("I-CAU", 0.050), ("I-ONI", 0.030), ("I-POT", 0.045)],
    "D-PAL": [("I-SPI", 0.140), ("I-PNR", 0.090), ("I-ONI", 0.030),
              ("I-TOM", 0.030)],
}

RETAIL_SKUS = [
    ("Toned Milk 1L", "R-MLK", "dairy", "dairy", 52.0, 62.0, 1.03, 42),
    ("Curd 400g", "R-CRD", "dairy", "dairy", 38.0, 48.0, 0.40, 18),
    ("Pav Bread", "R-BRD", "bakery", "bakery", 28.0, 40.0, 0.30, 31),
    ("Paneer 200g", "R-PNR", "dairy", "dairy", 76.0, 95.0, 0.20, 11),
    ("Spinach Bunch", "R-SPI", "leafy_green", "leafy_green", 18.0, 30.0, 0.25, 14),
    ("Tomato 1kg", "R-TOM", "vegetable", "fruiting_vegetable", 34.0, 48.0, 1.00, 26),
]

PRODUCTION_SKUS = [
    ("Sandwich Bread 400g", "P-BRD", "bakery", 22.0, 38.0, 0.40, 2100),
    ("Butter Croissant", "P-CRS", "bakery", 26.0, 55.0, 0.08, 780),
    ("Blueberry Muffin", "P-MUF", "bakery", 18.0, 45.0, 0.09, 420),
    ("Celebration Cake", "P-CAK", "bakery", 210.0, 520.0, 1.20, 95),
]

# Rescue channels live in `ingest/channels.py` — they are D's content, not
# observed data, so the seed loads them separately for every source.

PRODUCE_CATEGORIES = {"vegetable", "fruit", "leafy_green"}

# kg CO2e per unit of measure, standing in for what A supplies per product.
CO2E_PER_UOM = {
    "vegetable": 0.5, "leafy_green": 0.4, "fruit": 0.6,
    "dairy": 3.2, "meat": 6.9, "staple": 2.7, "bakery": 1.1,
}


def _dow_noise(rng: np.random.Generator, scale: float) -> float:
    return float(np.clip(rng.normal(1.0, scale), 0.55, 1.6))


def build(session: Session, today: date) -> dict:
    """Populate an empty database. Returns a summary for the seed report."""
    rng = np.random.default_rng(SEED)

    org = Organization(name="Spice Garden Hospitality", track=Track.KITCHEN)
    session.add(org)
    session.flush()

    kitchen = Site(org_id=org.id, name="Spice Garden, Koramangala", type=SiteType.KITCHEN)
    store = Site(org_id=org.id, name="FreshMart, Indiranagar", type=SiteType.STORE)
    plant = Site(org_id=org.id, name="Daily Bakes Central", type=SiteType.PLANT)
    session.add_all([kitchen, store, plant])
    session.flush()

    profiles: dict[str, ShelfLifeProfile] = {}
    for category, (base, ref, q10, cut, sens, emit) in PROFILES.items():
        p = ShelfLifeProfile(
            category=category,
            base_shelf_life_days=base,
            ref_temp_c=ref,
            q10=q10,
            cut_life_factor=cut,
            ethylene_sensitive=sens,
            ethylene_emitter=emit,
        )
        session.add(p)
        profiles[category] = p
    session.flush()

    zones = {}
    for site, name, temp in [
        (kitchen, "Walk-in chiller", 4.0),
        (kitchen, "Dry store", 24.0),
        (kitchen, "Veg cold room", 8.0),
        (store, "Chiller aisle", 4.0),
        (store, "Produce shelf", 12.0),
    ]:
        z = StorageZone(site_id=site.id, name=name, mean_temp_c=temp, temp_source="declared")
        session.add(z)
        zones[(site.id, name)] = z
    session.flush()

    # ------------------------------------------------------------ products
    products: dict[str, Product] = {}

    for name, sku, _, price, cost, kg, _, _ in DISHES:
        p = Product(
            org_id=org.id, sku=sku, name=name, category="prepared_dish", uom="portion",
            unit_cost=cost, unit_price=price, unit_weight_kg=kg, is_dish=True,
            is_produce=False, plannable=True, co2e_kg_per_uom=kg * 2.5,
            shelf_life_profile_id=profiles["bakery"].id,
        )
        session.add(p)
        products[sku] = p

    yields: dict[str, tuple[float, float]] = {}
    for name, sku, category, profile, cost, std_yield, actual_yield in INGREDIENTS:
        p = Product(
            org_id=org.id, sku=sku, name=name, category=category, uom="kg",
            unit_cost=cost, unit_price=0.0, unit_weight_kg=1.0, is_dish=False,
            is_produce=category in PRODUCE_CATEGORIES, plannable=False,
            co2e_kg_per_uom=CO2E_PER_UOM.get(category, 2.5),
            shelf_life_profile_id=profiles[profile].id,
        )
        session.add(p)
        products[sku] = p
        yields[sku] = (std_yield, actual_yield)

    for name, sku, category, profile, cost, price, kg, _ in RETAIL_SKUS:
        p = Product(
            org_id=org.id, sku=sku, name=name, category=category, uom="unit",
            unit_cost=cost, unit_price=price, unit_weight_kg=kg, is_dish=False,
            is_produce=category in PRODUCE_CATEGORIES, plannable=True,
            co2e_kg_per_uom=CO2E_PER_UOM.get(category, 2.5) * kg,
            shelf_life_profile_id=profiles[profile].id,
        )
        session.add(p)
        products[sku] = p

    for name, sku, profile, cost, price, kg, _ in PRODUCTION_SKUS:
        p = Product(
            org_id=org.id, sku=sku, name=name, category="bakery", uom="unit",
            unit_cost=cost, unit_price=price, unit_weight_kg=kg, is_dish=False,
            is_produce=False, plannable=True, co2e_kg_per_uom=1.1 * kg,
            shelf_life_profile_id=profiles[profile].id,
        )
        session.add(p)
        products[sku] = p
    session.flush()

    # ------------------------------------------------------------- recipes
    for dish_sku, lines in RECIPES.items():
        if not lines:
            continue
        recipe = Recipe(product_id=products[dish_sku].id, yield_qty=1.0, yield_uom="portion")
        session.add(recipe)
        session.flush()
        for ing_sku, qty in lines:
            std_yield, _ = yields[ing_sku]
            session.add(
                RecipeLine(
                    recipe_id=recipe.id,
                    ingredient_product_id=products[ing_sku].id,
                    qty=qty,
                    uom="kg",
                    standard_yield_pct=std_yield,
                )
            )
    session.flush()

    # ------------------------------------------- kitchen history (90 days)
    start = today - timedelta(days=HISTORY_DAYS)
    ingredient_usage: dict[str, dict[date, float]] = {i[1]: {} for i in INGREDIENTS}
    consume_rows: list[tuple[str, date, float]] = []

    for offset in range(HISTORY_DAYS + 1):
        day = start + timedelta(days=offset)
        dow = day.weekday()
        session.add(
            DemandContext(
                site_id=kitchen.id, business_date=day, dow=dow,
                is_holiday=False, weather_code="clear",
                temp_max_c=float(round(26 + 6 * rng.random(), 1)),
                promo_flag=bool(dow == 2 and rng.random() < 0.2),
                covers=int(160 + 90 * [0.82, 0.85, 0.88, 0.95, 1.15, 1.25, 1.18][dow] * rng.random()),
            )
        )

        for name, sku, base, price, cost, kg, dow_factors, overprep in DISHES:
            product = products[sku]
            expected = base * dow_factors[dow]

            # The kitchen decides production from habit, *before* it sees the
            # day's demand. Deriving production from realised sales would give
            # the baseline perfect foresight, which no forecaster can beat and
            # which no real kitchen has.
            # Every kitchen over-preps, because running out is loud and waste
            # is silent. 1.20 puts the habitual quantity at roughly the 92nd
            # percentile of demand, which is where real kitchens sit.
            if overprep == "friday":  # fault 1, planted on chicken biryani
                factor = 1.38 if dow == 4 else 1.20
            elif overprep == "high":
                factor = 1.30 if dow in (4, 5) else 1.20
            else:
                factor = 1.20
            produced = max(int(round(expected * factor * _dow_noise(rng, 0.06))), 0)

            # True demand is unobserved; the POS only records what was sold, so
            # sales are censored at whatever was actually prepared.
            demand_true = expected * _dow_noise(rng, 0.14)
            sold = max(min(int(round(demand_true)), produced), 0)

            session.add(
                SalesRecord(
                    site_id=kitchen.id, product_id=product.id, business_date=day,
                    qty=sold, revenue=sold * price, channel="dine_in",
                )
            )
            session.add(
                ProductionRecord(
                    site_id=kitchen.id, product_id=product.id, business_date=day,
                    planned_qty=produced, actual_qty=produced, uom="portion",
                )
            )

            leftover = max(produced - sold, 0)
            if leftover > 0:
                session.add(
                    WasteEvent(
                        site_id=kitchen.id, business_date=day, product_id=product.id,
                        qty=leftover, uom="portion", qty_kg=round(leftover * kg, 3),
                        value=round(leftover * cost, 2),
                        reason=WasteReason.OVERPRODUCTION,
                        stage=WasteStage.POST_SERVICE, capture_method="pos_derived",
                    )
                )

            plate = sold * 0.028 * _dow_noise(rng, 0.3)
            if plate > 0.5:
                session.add(
                    WasteEvent(
                        site_id=kitchen.id, business_date=day, product_id=product.id,
                        qty=round(plate, 2), uom="portion", qty_kg=round(plate * kg, 3),
                        value=round(plate * cost, 2), reason=WasteReason.PLATE_WASTE,
                        stage=WasteStage.SERVICE, capture_method="manual",
                    )
                )

            for ing_sku, per_portion in RECIPES[sku]:
                used = produced * per_portion
                ingredient_usage[ing_sku][day] = (
                    ingredient_usage[ing_sku].get(day, 0.0) + used
                )

        # Prep trim per ingredient. Fault 2 lives here: cauliflower's actual
        # yield is 0.51 against a 0.58 standard, so the gap is avoidable.
        for ing_sku, usage_by_day in ingredient_usage.items():
            used = usage_by_day.get(day, 0.0)
            if used <= 0:
                continue
            product = products[ing_sku]
            std_yield, actual_yield = yields[ing_sku]
            purchased = used / max(actual_yield, 1e-6)
            trim = purchased - used
            if trim > 0.01:
                session.add(
                    WasteEvent(
                        site_id=kitchen.id, business_date=day, product_id=product.id,
                        qty=round(trim, 3), uom="kg", qty_kg=round(trim, 3),
                        value=round(trim * product.unit_cost, 2),
                        reason=WasteReason.PREP_TRIM, stage=WasteStage.PREP,
                        capture_method="manual",
                        note=f"yield {actual_yield:.2f} vs {std_yield:.2f} standard",
                    )
                )
            # Buffered — the batch these belong to does not exist yet.
            consume_rows.append((ing_sku, day, round(used, 3)))

            if rng.random() < 0.06:
                spoil = purchased * 0.05 * rng.random()
                if spoil > 0.05:
                    session.add(
                        WasteEvent(
                            site_id=kitchen.id, business_date=day,
                            product_id=product.id, qty=round(spoil, 3), uom="kg",
                            qty_kg=round(spoil, 3),
                            value=round(spoil * product.unit_cost, 2),
                            reason=WasteReason.SPOILAGE, stage=WasteStage.STORAGE,
                            capture_method="manual",
                        )
                    )
    session.flush()

    avg_usage = {
        sku: sum(days.values()) / max(len(days), 1)
        for sku, days in ingredient_usage.items()
    }

    # -------------------------------------------------- kitchen inventory
    now = datetime.combine(today, datetime.min.time()) + timedelta(hours=9)
    chiller = zones[(kitchen.id, "Walk-in chiller")]
    dry = zones[(kitchen.id, "Dry store")]
    veg = zones[(kitchen.id, "Veg cold room")]

    # (sku, zone, days_held, qty, state, intake_grade, excursion_h, excursion_c)
    KITCHEN_BATCHES = [
        ("I-SPI", veg, 2.1, 20.0, BatchState.WHOLE, 0.92, 4.0, 31.0),   # fault 3
        ("I-TOM", veg, 3.0, 26.0, BatchState.WHOLE, 0.95, 0.0, None),   # emitter
        ("I-COR", veg, 1.5, 3.0, BatchState.WHOLE, 0.90, 0.0, None),
        ("I-CAU", veg, 2.0, 14.0, BatchState.WHOLE, 0.94, 0.0, None),
        ("I-ONI", dry, 6.0, 48.0, BatchState.WHOLE, 0.97, 0.0, None),
        ("I-POT", dry, 5.0, 40.0, BatchState.WHOLE, 0.96, 0.0, None),
        ("I-CAP", veg, 2.5, 9.0, BatchState.WHOLE, 0.93, 0.0, None),
        ("I-CAR", veg, 3.5, 12.0, BatchState.WHOLE, 0.95, 0.0, None),
        ("I-PNR", chiller, 3.0, 11.0, BatchState.WHOLE, 0.98, 0.0, None),
        ("I-CHK", chiller, 1.2, 16.0, BatchState.WHOLE, 0.97, 0.0, None),
        ("I-RIC", dry, 20.0, 90.0, BatchState.WHOLE, 1.00, 0.0, None),
    ]

    batches: list[Batch] = []
    for sku, zone, days_held, qty, state, grade, exc_h, exc_c in KITCHEN_BATCHES:
        product = products[sku]
        profile = session.get(ShelfLifeProfile, product.shelf_life_profile_id)
        received = now - timedelta(days=days_held)
        rsl, explanation = estimate(
            ShelfLifeInputs(
                base_shelf_life_days=profile.base_shelf_life_days,
                ref_temp_c=profile.ref_temp_c,
                q10=profile.q10,
                received_at=received,
                as_of=now,
                storage_temp_c=zone.mean_temp_c,
                intake_grade=grade,
                state=str(state),
                excursion_hours=exc_h,
                excursion_temp_c=exc_c,
            )
        )
        batch = Batch(
            site_id=kitchen.id, product_id=product.id,
            lot_code=f"{sku}-{received:%y%m%d}",
            received_at=received,
            printed_expiry=(received + timedelta(days=profile.base_shelf_life_days)).date(),
            qty_received=qty, qty_remaining=qty, uom="kg",
            storage_zone_id=zone.id, intake_grade=grade, state=state,
            unit_cost=product.unit_cost, rsl_days=rsl, rsl_explanation=explanation,
        )
        session.add(batch)
        batches.append(batch)
    session.flush()

    # Flush the buffered consumption history now that the batches exist.
    # (A real ingest links an issue to its batch at the moment of issue.)
    batch_by_product = {b.product_id: b.id for b in batches}
    for sku, day, qty in consume_rows:
        batch_id = batch_by_product.get(products[sku].id)
        if batch_id is None:
            continue
        session.add(
            InventoryEvent(
                batch_id=batch_id,
                ts=datetime.combine(day, datetime.min.time()),
                type=InventoryEventType.CONSUME,
                qty=qty,
                ref=f"usage:{sku}",
            )
        )
    session.flush()

    # ------------------------------------------------------ retail (Track 2)
    for name, sku, category, profile_key, cost, price, kg, daily in RETAIL_SKUS:
        product = products[sku]
        profile = session.get(ShelfLifeProfile, product.shelf_life_profile_id)
        for offset in range(HISTORY_DAYS + 1):
            day = start + timedelta(days=offset)
            qty = max(int(round(daily * _dow_noise(rng, 0.18))), 0)
            session.add(
                SalesRecord(
                    site_id=store.id, product_id=product.id, business_date=day,
                    qty=qty, revenue=qty * price, channel="retail",
                )
            )
        zone = zones[(store.id, "Chiller aisle" if category == "dairy" else "Produce shelf")]
        days_held = float(np.clip(rng.normal(2.2, 0.8), 0.5, 5.0))
        received = now - timedelta(days=days_held)
        rsl, explanation = estimate(
            ShelfLifeInputs(
                base_shelf_life_days=profile.base_shelf_life_days,
                ref_temp_c=profile.ref_temp_c, q10=profile.q10,
                received_at=received, as_of=now,
                storage_temp_c=zone.mean_temp_c, intake_grade=0.95,
            )
        )
        on_hand = float(round(daily * rng.uniform(2.2, 4.5)))
        session.add(
            Batch(
                site_id=store.id, product_id=product.id,
                lot_code=f"{sku}-{received:%y%m%d}", received_at=received,
                printed_expiry=(received + timedelta(days=profile.base_shelf_life_days)).date(),
                qty_received=on_hand, qty_remaining=on_hand, uom="unit",
                storage_zone_id=zone.id, intake_grade=0.95,
                unit_cost=cost, rsl_days=rsl, rsl_explanation=explanation,
            )
        )

    # -------------------------------------------------- production (Track 3)
    for name, sku, profile_key, cost, price, kg, daily in PRODUCTION_SKUS:
        product = products[sku]
        for offset in range(HISTORY_DAYS + 1):
            day = start + timedelta(days=offset)
            dow = day.weekday()
            factor = 1.18 if dow in (4, 5) else 0.95 if dow == 0 else 1.0
            qty = max(int(round(daily * factor * _dow_noise(rng, 0.12))), 0)
            session.add(
                SalesRecord(
                    site_id=plant.id, product_id=product.id, business_date=day,
                    qty=qty, revenue=qty * price, channel="wholesale",
                )
            )
            produced = int(round(qty * 1.24 * _dow_noise(rng, 0.04)))
            session.add(
                ProductionRecord(
                    site_id=plant.id, product_id=product.id, business_date=day,
                    planned_qty=produced, actual_qty=produced, uom="unit",
                )
            )

    session.flush()
    return {
        "organization": org.name,
        "sites": {"kitchen": kitchen.id, "store": store.id, "plant": plant.id},
        "history_days": HISTORY_DAYS,
        "planted_faults": [
            "Friday over-prep on Chicken Biryani (~34% vs ~12%)",
            "Cauliflower trim yield 0.51 against a 0.58 standard",
            "4 h dock excursion at 31 C on the spinach batch",
        ],
        "avg_daily_ingredient_usage": {k: round(v, 2) for k, v in avg_usage.items()},
    }
