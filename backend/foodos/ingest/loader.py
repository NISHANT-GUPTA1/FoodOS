"""CSV loader — reads A's generated dataset.

**The file and column contract is A's, not B's.**

A keys every row with a readable string id — `SITE_KIT_01`, `ING_TOMATO`,
`DSH_CHBIRYANI`, `B01609`, `ZN_COLD` — which is far easier to debug than an
integer surrogate. The database keeps integer primary keys, so this module
holds the translation: one `external id -> row` map per entity, built as each
file loads and used to resolve every later reference. Nothing is matched by
name, so a renamed product never silently splits into two.

Expected files (all optional except `products.csv`; the loader ingests what is
present and reports what was missing, so a partial drop still works):

    sites.csv             site_id, name, type, timezone, currency
    products.csv          product_id, sku, name, category, uom, unit_cost,
                          unit_price, is_dish, perishable, is_produce,
                          co2e_kg_per_uom, portion_kg, plannable
    recipes.csv           recipe_id, product_id, yield_qty, yield_uom,
                          ingredient_product_id, qty, uom, standard_yield_pct
    storage_zones.csv     storage_zone_id, site_id, name, mean_temp_c, temp_source
    goods_receipt.csv     batch_id, site_id, product_id, lot_code, received_at,
                          printed_expiry, qty_received, uom, storage_zone_id,
                          dock_dwell_hours, intake_grade, unit_cost, state
    open_batches.csv      batch_id, ..., qty_remaining, life_used, rsl_days,
                          value_on_hand, state
    inventory_events.csv  site_id, batch_id, product_id, ts, type, qty, uom, ref
    sales.csv             sale_id, site_id, product_id, business_date, qty,
                          revenue, channel
    production.csv        production_id, site_id, product_id, business_date,
                          planned_qty, actual_qty, uom
    waste.csv             waste_id, site_id, business_date, product_id, batch_id,
                          qty, uom, value, reason, stage, capture_method, note
    demand_context.csv    site_id, business_date, dow, is_holiday, festival,
                          weather_code, temp_max_c, promo_flag, covers

`open_batches.rsl_days` is A's RSL model output and always wins. Where a batch
has no score, B falls back to the deterministic Q10 estimate using the receipt's
`dock_dwell_hours` and the zone temperature.

Rescue channels are not in A's dataset — they are D's content. See
`ingest/channels.py`.
"""

from __future__ import annotations

import csv
from datetime import date, datetime, timedelta
from pathlib import Path

from sqlalchemy.orm import Session

from foodos.ingest import profiles
from foodos.ingest.shelf_life import ShelfLifeInputs, estimate
from foodos.ingest.validation import (
    ValidationReport,
    to_bool,
    to_date,
    to_datetime,
    to_float,
    to_int,
)
from foodos.schema.enums import SiteType, Track, WasteReason, WasteStage
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

DOCK_TEMP_C = 31.0  # ZN_DOCK in A's dataset; used only by the fallback estimate


def has_data(data_dir: Path) -> bool:
    return data_dir.exists() and (data_dir / "products.csv").exists()


def _ext(value) -> str:
    """A's external key. Always a string; empty means absent."""
    return "" if value is None else str(value).strip()


def _read(path: Path, report: ValidationReport) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    report.rows_seen = len(rows)
    return rows


def load_all(session: Session, data_dir: Path, today: date) -> dict:
    reports: dict[str, dict] = {}

    def start(name: str) -> ValidationReport:
        return ValidationReport(source=name)

    def finish(r: ValidationReport) -> None:
        reports[r.source] = r.as_dict()

    org = Organization(name="FoodOS Customer", track=Track.KITCHEN)
    session.add(org)
    session.flush()

    sites: dict[str, Site] = {}
    products: dict[str, Product] = {}
    zones: dict[str, StorageZone] = {}
    batches: dict[str, int] = {}
    profile_cache: dict[str, ShelfLifeProfile] = {}

    # ----------------------------------------------------------------- sites
    path = data_dir / "sites.csv"
    if path.exists():
        r = start(path.name)
        for row in _read(path, r):
            key = _ext(row.get("site_id"))
            raw_type = (row.get("type") or "kitchen").strip().lower()
            try:
                stype = SiteType(raw_type)
            except ValueError:
                stype = SiteType.KITCHEN
            site = Site(
                org_id=org.id,
                name=(row.get("name") or key or "Site").strip(),
                type=stype,
            )
            session.add(site)
            session.flush()
            sites[key] = site
            r.rows_loaded += 1
        finish(r)

    if not sites:
        site = Site(org_id=org.id, name="Default site", type=SiteType.KITCHEN)
        session.add(site)
        session.flush()
        sites[""] = site

    default_site = next(iter(sites.values()))

    def site_id_of(value) -> int:
        return sites.get(_ext(value), default_site).id

    # -------------------------------------------------------------- products
    path = data_dir / "products.csv"
    if not path.exists():
        raise FileNotFoundError(
            f"{path} is required. Run A's generator, or seed with --source fixture."
        )

    r = start(path.name)
    for row in _read(path, r):
        key = _ext(row.get("product_id"))
        if not key:
            r.errors.append("a row has no product_id")
            continue
        name = (row.get("name") or key).strip()
        category = (row.get("category") or "general").strip()

        cat_key, base_days, ref_temp, q10, cut, sensitive, emitter = (
            profiles.profile_for(category, name)
        )
        # One profile row per (category, ethylene behaviour) pair — tomatoes and
        # cabbage are both "vegetable" but must not share ethylene flags.
        cache_key = f"{cat_key}|{int(sensitive)}{int(emitter)}"
        profile = profile_cache.get(cache_key)
        if profile is None:
            profile = ShelfLifeProfile(
                category=cache_key,
                base_shelf_life_days=base_days,
                ref_temp_c=ref_temp,
                q10=q10,
                cut_life_factor=cut,
                ethylene_sensitive=sensitive,
                ethylene_emitter=emitter,
            )
            session.add(profile)
            session.flush()
            profile_cache[cache_key] = profile

        product = Product(
            org_id=org.id,
            sku=(row.get("sku") or key).strip(),
            name=name,
            category=category,
            uom=(row.get("uom") or "kg").strip(),
            unit_cost=to_float(row.get("unit_cost")),
            unit_price=to_float(row.get("unit_price")),
            # Ingredients are priced and measured per kg, so an empty
            # portion_kg means one unit already is one kilogram.
            unit_weight_kg=to_float(row.get("portion_kg"), 1.0) or 1.0,
            is_dish=to_bool(row.get("is_dish")),
            perishable=to_bool(row.get("perishable"), True),
            is_produce=to_bool(row.get("is_produce")),
            co2e_kg_per_uom=(
                to_float(row.get("co2e_kg_per_uom"))
                if _ext(row.get("co2e_kg_per_uom"))
                else None
            ),
            plannable=to_bool(row.get("plannable")),
            shelf_life_profile_id=profile.id,
        )
        session.add(product)
        session.flush()
        products[key] = product
        r.rows_loaded += 1
    finish(r)

    # --------------------------------------------------------------- recipes
    path = data_dir / "recipes.csv"
    if path.exists():
        r = start(path.name)
        recipes: dict[str, Recipe] = {}
        for i, row in enumerate(_read(path, r), start=1):
            dish_key = _ext(row.get("product_id"))
            ing_key = _ext(row.get("ingredient_product_id"))
            if dish_key not in products or ing_key not in products:
                r.errors.append(f"row {i}: unknown product {dish_key!r} -> {ing_key!r}")
                continue
            recipe = recipes.get(dish_key)
            if recipe is None:
                recipe = Recipe(
                    product_id=products[dish_key].id,
                    yield_qty=to_float(row.get("yield_qty"), 1.0) or 1.0,
                    yield_uom=(row.get("yield_uom") or "portion").strip(),
                )
                session.add(recipe)
                session.flush()
                recipes[dish_key] = recipe
            session.add(
                RecipeLine(
                    recipe_id=recipe.id,
                    ingredient_product_id=products[ing_key].id,
                    qty=to_float(row.get("qty")),
                    uom=(row.get("uom") or "kg").strip(),
                    standard_yield_pct=to_float(row.get("standard_yield_pct"), 1.0) or 1.0,
                )
            )
            r.rows_loaded += 1
        session.flush()
        finish(r)

    # --------------------------------------------------------- storage zones
    path = data_dir / "storage_zones.csv"
    if path.exists():
        r = start(path.name)
        for row in _read(path, r):
            key = _ext(row.get("storage_zone_id"))
            zone = StorageZone(
                site_id=site_id_of(row.get("site_id")),
                name=(row.get("name") or key or "zone").strip(),
                mean_temp_c=to_float(row.get("mean_temp_c"), 8.0),
                temp_source=(row.get("temp_source") or "declared").strip(),
            )
            session.add(zone)
            session.flush()
            zones[key] = zone
            r.rows_loaded += 1
        finish(r)

    # --------------------------------------------------------------- batches
    #
    # goods_receipt describes intake (and the dock dwell that damages produce);
    # open_batches describes what is still on hand and carries A's rsl_days.
    # Merge on batch_id, preferring A's RSL wherever it exists.
    as_of = datetime.combine(today, datetime.min.time()) + timedelta(hours=9)
    receipts: dict[str, dict] = {}

    path = data_dir / "goods_receipt.csv"
    if path.exists():
        r = start(path.name)
        for row in _read(path, r):
            key = _ext(row.get("batch_id"))
            if key:
                receipts[key] = row
                r.rows_loaded += 1
        finish(r)

    path = data_dir / "open_batches.csv"
    if path.exists():
        r = start(path.name)
        for i, row in enumerate(_read(path, r), start=1):
            key = _ext(row.get("batch_id"))
            product = products.get(_ext(row.get("product_id")))
            if product is None:
                r.errors.append(f"row {i}: unknown product for batch {key!r}")
                continue

            receipt = receipts.get(key, {})
            zone = zones.get(_ext(row.get("storage_zone_id")))
            received = (
                to_datetime(row.get("received_at"))
                or to_datetime(receipt.get("received_at"))
                or as_of
            )
            grade = to_float(row.get("intake_grade"), 1.0) or 1.0
            state = (row.get("state") or receipt.get("state") or "whole").strip()
            dwell = to_float(receipt.get("dock_dwell_hours"))

            rsl = to_float(row.get("rsl_days"), -1.0) if _ext(row.get("rsl_days")) else -1.0
            if rsl < 0:
                # A has not scored this batch — deterministic Q10 fallback.
                profile = session.get(ShelfLifeProfile, product.shelf_life_profile_id)
                rsl, explanation = estimate(
                    ShelfLifeInputs(
                        base_shelf_life_days=profile.base_shelf_life_days,
                        ref_temp_c=profile.ref_temp_c,
                        q10=profile.q10,
                        received_at=received,
                        as_of=as_of,
                        storage_temp_c=zone.mean_temp_c if zone else 8.0,
                        intake_grade=grade,
                        state=state,
                        excursion_hours=dwell,
                        excursion_temp_c=DOCK_TEMP_C if dwell > 0 else None,
                    )
                )
                explanation = f"[B fallback] {explanation}"
            else:
                life_used = to_float(row.get("life_used"))
                explanation = (
                    f"{life_used:.0%} of usable life consumed since intake on "
                    f"{received:%d %b}"
                    + (
                        f", held in {zone.name} at {zone.mean_temp_c:.0f} C"
                        if zone
                        else ""
                    )
                    + (
                        f". {dwell:.1f} h on the receiving dock at "
                        f"{DOCK_TEMP_C:.0f} C before it reached storage."
                        if dwell > 0
                        else "."
                    )
                )

            qty_remaining = to_float(row.get("qty_remaining"))
            batch = Batch(
                site_id=site_id_of(row.get("site_id")),
                product_id=product.id,
                lot_code=(row.get("lot_code") or receipt.get("lot_code") or key),
                received_at=received,
                printed_expiry=(
                    to_date(row.get("printed_expiry"))
                    or to_date(receipt.get("printed_expiry"))
                ),
                qty_received=to_float(receipt.get("qty_received"), qty_remaining),
                qty_remaining=qty_remaining,
                uom=(row.get("uom") or product.uom).strip(),
                storage_zone_id=zone.id if zone else None,
                intake_grade=grade,
                state=state,
                unit_cost=to_float(row.get("unit_cost"), product.unit_cost),
                rsl_days=round(rsl, 2),
                life_used=to_float(row.get("life_used")) or None,
                rsl_explanation=explanation[:400],
            )
            session.add(batch)
            session.flush()
            batches[key] = batch.id
            r.rows_loaded += 1
        finish(r)

    # ----------------------------------------------------- inventory events
    path = data_dir / "inventory_events.csv"
    if path.exists():
        r = start(path.name)
        for row in _read(path, r):
            batch_id = batches.get(_ext(row.get("batch_id")))
            ts = to_datetime(row.get("ts"))
            if batch_id is None or ts is None:
                continue  # events for batches that are already fully depleted
            session.add(
                InventoryEvent(
                    batch_id=batch_id,
                    ts=ts,
                    type=(row.get("type") or "consume").strip().lower(),
                    qty=abs(to_float(row.get("qty"))),
                    ref=row.get("ref"),
                )
            )
            r.rows_loaded += 1
        session.flush()
        finish(r)

    # ------------------------------------------------- sales and production
    path = data_dir / "sales.csv"
    if path.exists():
        r = start(path.name)
        for row in _read(path, r):
            product = products.get(_ext(row.get("product_id")))
            day = to_date(row.get("business_date"))
            if product is None or day is None:
                continue
            session.add(
                SalesRecord(
                    site_id=site_id_of(row.get("site_id")),
                    product_id=product.id,
                    business_date=day,
                    qty=to_float(row.get("qty")),
                    revenue=to_float(row.get("revenue")),
                    channel=(row.get("channel") or "dine_in").strip(),
                )
            )
            r.rows_loaded += 1
        session.flush()
        finish(r)

    path = data_dir / "production.csv"
    if path.exists():
        r = start(path.name)
        for row in _read(path, r):
            product = products.get(_ext(row.get("product_id")))
            day = to_date(row.get("business_date"))
            if product is None or day is None:
                continue
            actual = to_float(row.get("actual_qty"))
            session.add(
                ProductionRecord(
                    site_id=site_id_of(row.get("site_id")),
                    product_id=product.id,
                    business_date=day,
                    planned_qty=to_float(row.get("planned_qty"), actual),
                    actual_qty=actual,
                    uom=(row.get("uom") or "portion").strip(),
                )
            )
            r.rows_loaded += 1
        session.flush()
        finish(r)

    # ----------------------------------------------------------------- waste
    path = data_dir / "waste.csv"
    if path.exists():
        r = start(path.name)
        for row in _read(path, r):
            day = to_date(row.get("business_date"))
            if day is None:
                continue
            product = products.get(_ext(row.get("product_id")))
            qty = to_float(row.get("qty"))
            uom = (row.get("uom") or "kg").strip()
            weight = product.unit_weight_kg if product else 1.0
            try:
                reason = WasteReason((row.get("reason") or "spoilage").strip().lower())
            except ValueError:
                reason = WasteReason.SPOILAGE
            try:
                stage = WasteStage((row.get("stage") or "service").strip().lower())
            except ValueError:
                stage = WasteStage.SERVICE
            session.add(
                WasteEvent(
                    site_id=site_id_of(row.get("site_id")),
                    business_date=day,
                    product_id=product.id if product else None,
                    batch_id=batches.get(_ext(row.get("batch_id"))),
                    qty=qty,
                    uom=uom,
                    qty_kg=round(qty if uom == "kg" else qty * weight, 3),
                    value=to_float(
                        row.get("value"), qty * (product.unit_cost if product else 0.0)
                    ),
                    reason=reason,
                    stage=stage,
                    capture_method=(row.get("capture_method") or "manual").strip(),
                    note=row.get("note"),
                )
            )
            r.rows_loaded += 1
        session.flush()
        finish(r)

    # -------------------------------------------------------- demand context
    path = data_dir / "demand_context.csv"
    if path.exists():
        r = start(path.name)
        seen: set[tuple[int, date]] = set()
        for row in _read(path, r):
            day = to_date(row.get("business_date"))
            if day is None:
                continue
            sid = site_id_of(row.get("site_id"))
            if (sid, day) in seen:
                continue
            seen.add((sid, day))
            session.add(
                DemandContext(
                    site_id=sid,
                    business_date=day,
                    dow=to_int(row.get("dow"), day.weekday()),
                    is_holiday=to_bool(row.get("is_holiday")),
                    festival=row.get("festival") or None,
                    weather_code=row.get("weather_code") or None,
                    temp_max_c=to_float(row.get("temp_max_c")) or None,
                    promo_flag=to_bool(row.get("promo_flag")),
                    covers=to_int(row.get("covers")) or None,
                )
            )
            r.rows_loaded += 1
        session.flush()
        finish(r)

    return {
        "organization": org.name,
        "sites": {s.id: s.name for s in sites.values()},
        "default_site_id": default_site.id,
        "products": len(products),
        "batches": len(batches),
        "files": reports,
    }
