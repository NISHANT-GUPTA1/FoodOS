"""All database reads for the engine.

Keeping every SELECT here means the decision modules stay pure functions —
easy to unit-test, and impossible to accidentally couple to the ORM.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from foodos.engine.distribution import DemandDistribution
from foodos.schema.tables import (
    Batch,
    Channel,
    Forecast,
    InventoryEvent,
    Product,
    ProductionRecord,
    Recipe,
    RecipeLine,
    SalesRecord,
    Site,
    StorageZone,
    WasteEvent,
)

EMPIRICAL_WINDOW_DAYS = 56


def get_site(session: Session, site_id: int | None = None) -> Site:
    stmt = select(Site) if site_id is None else select(Site).where(Site.id == site_id)
    site = session.scalars(stmt.limit(1)).first()
    if site is None:
        raise LookupError("no site found — run `python -m foodos.ingest.seed`")
    return site


def plannable_products(session: Session, site_id: int) -> list[Product]:
    """Products that get a PREVENT quantity recommendation.

    A flags these with `plannable`, which is not the same as `is_dish` — a
    bakery's finished SKUs are plannable and are not dishes.
    """
    org_id = session.get(Site, site_id).org_id
    return list(
        session.scalars(
            select(Product)
            .where(Product.org_id == org_id, Product.plannable.is_(True))
            .order_by(Product.name)
        )
    )


# Kept as the old name so nothing downstream breaks mid-hackathon.
dishes = plannable_products


def products(session: Session, site_id: int, is_dish: bool | None = None) -> list[Product]:
    org_id = session.get(Site, site_id).org_id
    stmt = select(Product).where(Product.org_id == org_id)
    if is_dish is not None:
        stmt = stmt.where(Product.is_dish.is_(is_dish))
    return list(session.scalars(stmt.order_by(Product.name)))


# ---------------------------------------------------------------- forecasts


def demand_distribution(
    session: Session, site_id: int, product_id: int, target: date
) -> DemandDistribution | None:
    """Prefer a stored Forecast row (written by A). Fall back to the empirical
    day-of-week distribution, which is the seasonal-naive baseline."""
    fc = session.scalars(
        select(Forecast).where(
            Forecast.site_id == site_id,
            Forecast.product_id == product_id,
            Forecast.target_date == target,
        )
    ).first()
    if fc is not None:
        return DemandDistribution.from_quantiles(
            fc.q10, fc.q25, fc.q50, fc.q66, fc.q75, fc.q90
        )
    return empirical_distribution(session, site_id, product_id, target)


def empirical_distribution(
    session: Session,
    site_id: int,
    product_id: int,
    target: date,
    match_dow: bool = True,
    window_days: int = EMPIRICAL_WINDOW_DAYS,
) -> DemandDistribution | None:
    """Seasonal-naive baseline: the spread of the same weekday's sales."""
    start = target - timedelta(days=window_days)
    rows = session.execute(
        select(SalesRecord.business_date, SalesRecord.qty).where(
            SalesRecord.site_id == site_id,
            SalesRecord.product_id == product_id,
            SalesRecord.business_date >= start,
            SalesRecord.business_date < target,
        )
    ).all()
    if not rows:
        return None
    if match_dow:
        same = [q for d, q in rows if d.weekday() == target.weekday()]
        # Below ~5 observations the same-weekday spread is too tight and the
        # 10-90 band under-covers. Pool all days rather than lie about it.
        if len(same) >= 5:
            return DemandDistribution.from_samples(same)
    return DemandDistribution.from_samples([q for _, q in rows])


def daily_usage_distribution(
    session: Session, site_id: int, product_id: int, target: date
) -> DemandDistribution:
    """Daily consumption of an *ingredient*, for the RSL risk window.

    Uses CONSUME inventory events where they exist, sales otherwise, and a
    degenerate zero distribution when the product has no history at all.
    """
    start = target - timedelta(days=EMPIRICAL_WINDOW_DAYS)
    rows = session.execute(
        select(func.date(InventoryEvent.ts), func.sum(InventoryEvent.qty))
        .join(Batch, Batch.id == InventoryEvent.batch_id)
        .where(
            Batch.site_id == site_id,
            Batch.product_id == product_id,
            InventoryEvent.type == "consume",
            InventoryEvent.ts >= start,
        )
        .group_by(func.date(InventoryEvent.ts))
    ).all()
    daily = [abs(float(q)) for _, q in rows if q is not None]
    if len(daily) >= 4:
        return DemandDistribution.from_samples(daily)

    fallback = empirical_distribution(
        session, site_id, product_id, target, match_dow=False
    )
    return fallback or DemandDistribution.from_quantiles(0, 0, 0, 0, 0, 0)


# ------------------------------------------------------------------- recipes


def recipe_map(
    session: Session, site_id: int
) -> dict[int, list[tuple[int, str, float, float]]]:
    """product_id -> [(ingredient_id, name, qty_per_unit, standard_yield_pct)]"""
    org_id = session.get(Site, site_id).org_id
    rows = session.execute(
        select(
            Recipe.product_id,
            RecipeLine.ingredient_product_id,
            Product.name,
            RecipeLine.qty,
            RecipeLine.standard_yield_pct,
            Recipe.yield_qty,
        )
        .join(RecipeLine, RecipeLine.recipe_id == Recipe.id)
        .join(Product, Product.id == RecipeLine.ingredient_product_id)
        .where(Product.org_id == org_id)
    ).all()

    out: dict[int, list[tuple[int, str, float, float]]] = defaultdict(list)
    for pid, ing_id, ing_name, qty, std_yield, yield_qty in rows:
        per_unit = qty / (yield_qty or 1.0)
        out[pid].append((ing_id, ing_name, per_unit, std_yield or 1.0))
    return dict(out)


# ----------------------------------------------------------------- inventory


def open_batches(session: Session, site_id: int) -> list[Batch]:
    return list(
        session.scalars(
            select(Batch)
            .where(Batch.site_id == site_id, Batch.qty_remaining > 0)
            .order_by(Batch.rsl_days.is_(None), Batch.rsl_days)
        )
    )


def zone_map(session: Session, site_id: int) -> dict[int, StorageZone]:
    zones = session.scalars(
        select(StorageZone).where(StorageZone.site_id == site_id)
    )
    return {z.id: z for z in zones}


def channels(session: Session, site_id: int) -> list[Channel]:
    org_id = session.get(Site, site_id).org_id
    return list(
        session.scalars(
            select(Channel).where(Channel.org_id == org_id, Channel.active.is_(True))
        )
    )


# --------------------------------------------------------------------- waste


def waste_by_reason(
    session: Session, site_id: int, start: date, end: date
) -> list[dict]:
    rows = session.execute(
        select(
            WasteEvent.reason,
            func.sum(WasteEvent.qty_kg),
            func.sum(WasteEvent.value),
            func.count(WasteEvent.id),
        )
        .where(
            WasteEvent.site_id == site_id,
            WasteEvent.business_date >= start,
            WasteEvent.business_date <= end,
        )
        .group_by(WasteEvent.reason)
    ).all()
    return [
        {
            "reason": str(reason),
            "kg": round(float(kg or 0), 2),
            "value": round(float(val or 0), 2),
            "events": int(n),
        }
        for reason, kg, val, n in rows
    ]


def waste_by_product(
    session: Session, site_id: int, start: date, end: date, limit: int = 10
) -> list[dict]:
    rows = session.execute(
        select(
            Product.id,
            Product.name,
            Product.category,
            func.sum(WasteEvent.qty_kg),
            func.sum(WasteEvent.value),
        )
        .join(Product, Product.id == WasteEvent.product_id)
        .where(
            WasteEvent.site_id == site_id,
            WasteEvent.business_date >= start,
            WasteEvent.business_date <= end,
        )
        .group_by(Product.id, Product.name, Product.category)
        .order_by(func.sum(WasteEvent.value).desc())
        .limit(limit)
    ).all()
    return [
        {
            "product_id": pid,
            "product": name,
            "category": category,
            "kg": round(float(kg or 0), 2),
            "value": round(float(val or 0), 2),
        }
        for pid, name, category, kg, val in rows
    ]


def waste_daily(session: Session, site_id: int, start: date, end: date) -> list[dict]:
    rows = session.execute(
        select(
            WasteEvent.business_date,
            func.sum(WasteEvent.qty_kg),
            func.sum(WasteEvent.value),
        )
        .where(
            WasteEvent.site_id == site_id,
            WasteEvent.business_date >= start,
            WasteEvent.business_date <= end,
        )
        .group_by(WasteEvent.business_date)
        .order_by(WasteEvent.business_date)
    ).all()
    return [
        {"date": d.isoformat(), "kg": round(float(kg or 0), 2), "value": round(float(v or 0), 2)}
        for d, kg, v in rows
    ]


def produce_share(session: Session, site_id: int, start: date, end: date) -> dict:
    """Fruit and vegetable share of wasted weight — the headline number."""
    total_kg, total_val = session.execute(
        select(func.sum(WasteEvent.qty_kg), func.sum(WasteEvent.value)).where(
            WasteEvent.site_id == site_id,
            WasteEvent.business_date >= start,
            WasteEvent.business_date <= end,
        )
    ).one()
    # `is_produce` comes from A and is authoritative. Matching on the category
    # string would miss anything A classifies differently, and the fruit-and-veg
    # share is the headline number — it has to be right.
    produce_kg, produce_val = session.execute(
        select(func.sum(WasteEvent.qty_kg), func.sum(WasteEvent.value))
        .join(Product, Product.id == WasteEvent.product_id)
        .where(
            WasteEvent.site_id == site_id,
            WasteEvent.business_date >= start,
            WasteEvent.business_date <= end,
            Product.is_produce.is_(True),
        )
    ).one()

    total_kg = float(total_kg or 0)
    produce_kg = float(produce_kg or 0)
    return {
        "total_kg": round(total_kg, 2),
        "total_value": round(float(total_val or 0), 2),
        "produce_kg": round(produce_kg, 2),
        "produce_value": round(float(produce_val or 0), 2),
        "produce_share_of_weight": round(produce_kg / total_kg, 4) if total_kg else 0.0,
    }


# ---------------------------------------------------------------- production


def production_history(
    session: Session, site_id: int, product_id: int, start: date, end: date
) -> list[ProductionRecord]:
    return list(
        session.scalars(
            select(ProductionRecord)
            .where(
                ProductionRecord.site_id == site_id,
                ProductionRecord.product_id == product_id,
                ProductionRecord.business_date >= start,
                ProductionRecord.business_date <= end,
            )
            .order_by(ProductionRecord.business_date)
        )
    )


def recent_baseline_qty(
    session: Session, site_id: int, product_id: int, target: date, lookback: int = 28
) -> float | None:
    """What the site habitually produces on this weekday."""
    start = target - timedelta(days=lookback)
    rows = session.execute(
        select(ProductionRecord.business_date, ProductionRecord.actual_qty).where(
            ProductionRecord.site_id == site_id,
            ProductionRecord.product_id == product_id,
            ProductionRecord.business_date >= start,
            ProductionRecord.business_date < target,
        )
    ).all()
    if not rows:
        return None
    same_dow = [q for d, q in rows if d.weekday() == target.weekday()]
    pool = same_dow if len(same_dow) >= 2 else [q for _, q in rows]
    return float(sum(pool) / len(pool)) if pool else None
