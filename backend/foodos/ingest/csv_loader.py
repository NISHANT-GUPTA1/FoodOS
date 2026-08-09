"""CSV loading, with column mapping and validation.

Person A's generator writes these files, but so could a real customer's export — which is
the reason for the column mapping layer. A restaurant group's POS calls it ``item_name``,
another calls it ``Product``, a third exports ``Sales Qty``. Every one of them should land
in the same table without anybody editing engine code.

Validation is strict and loud. A silently dropped row is a wrong number on stage.

Owner: Person B.
"""

from __future__ import annotations

import csv
import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable

from sqlalchemy.orm import Session

from ..schema import (
    Batch,
    DemandContext,
    InventoryEvent,
    ProductionRecord,
    SalesRecord,
    WasteEvent,
    ZoneTemperature,
)


class IngestError(Exception):
    pass


@dataclass
class LoadReport:
    loaded: dict[str, int] = field(default_factory=dict)
    skipped: list[str] = field(default_factory=list)

    def total(self) -> int:
        return sum(self.loaded.values())


#: Canonical column -> the names a real export might use for it. Lowercased and stripped
#: of punctuation before matching, so "Sales Qty" and "sales_qty" are the same key.
COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "date": ("date", "business_date", "day", "txn_date", "order_date"),
    "dish_id": ("dish_id", "item_id", "sku", "product", "item", "item_name", "menu_item"),
    "product_id": ("product_id", "ingredient_id", "item_id", "sku", "product", "ingredient"),
    "qty_portions": ("qty_portions", "qty", "quantity", "sales_qty", "units", "covers"),
    "revenue_inr": ("revenue_inr", "revenue", "net_sales", "amount", "value"),
    "planned_portions": ("planned_portions", "planned", "prep_qty", "par"),
    "produced_portions": ("produced_portions", "produced", "made", "output"),
    "qty_kg": ("qty_kg", "kg", "weight_kg", "quantity_kg", "net_weight"),
    "value_inr": ("value_inr", "value", "cost", "amount"),
    "co2e_kg": ("co2e_kg", "co2e", "carbon_kg"),
    "reason": ("reason", "waste_reason", "cause", "category"),
    "zone_id": ("zone_id", "zone", "location", "storage"),
    "batch_id": ("batch_id", "lot", "lot_id", "batch"),
}


def _normalise(name: str) -> str:
    return "".join(ch for ch in name.strip().lower() if ch.isalnum() or ch == "_").replace("__", "_")


def map_columns(header: Iterable[str]) -> dict[str, str]:
    """Map a file's actual header onto canonical names. Unknown columns are left alone."""
    lookup = {}
    for column in header:
        key = _normalise(column)
        for canonical, aliases in COLUMN_ALIASES.items():
            if key == canonical or key in aliases:
                lookup[column] = canonical
                break
        else:
            lookup[column] = key
    return lookup


def read_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise IngestError(f"missing CSV: {path}")
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            return []
        mapping = map_columns(reader.fieldnames)
        return [{mapping[k]: v for k, v in row.items() if k in mapping} for row in reader]


# --- coercion ---------------------------------------------------------------

def as_date(value: Any, *, field_name: str, row: int) -> dt.date:
    try:
        return dt.date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        raise IngestError(f"row {row}: {field_name}={value!r} is not an ISO date") from None


def as_datetime(value: Any, *, field_name: str, row: int) -> dt.datetime:
    try:
        return dt.datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        raise IngestError(f"row {row}: {field_name}={value!r} is not an ISO datetime") from None


def as_float(value: Any, *, field_name: str, row: int, default: float | None = None) -> float:
    if value in (None, ""):
        if default is not None:
            return default
        raise IngestError(f"row {row}: {field_name} is empty")
    try:
        return float(value)
    except (TypeError, ValueError):
        raise IngestError(f"row {row}: {field_name}={value!r} is not a number") from None


def as_bool(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y", "t"}


# --- loaders ----------------------------------------------------------------

def _load(
    session: Session, path: Path, builder: Callable[[dict, int], Any]
) -> int:
    rows = read_csv(path)
    for index, row in enumerate(rows, start=2):  # start=2 so numbers match a spreadsheet
        session.add(builder(row, index))
    session.flush()
    return len(rows)


def load_demand_context(session: Session, path: Path) -> int:
    return _load(session, path, lambda r, i: DemandContext(
        date=as_date(r["date"], field_name="date", row=i),
        dow=int(as_float(r["dow"], field_name="dow", row=i)),
        is_weekend=as_bool(r["is_weekend"]),
        is_holiday=as_bool(r["is_holiday"]),
        rain_mm=as_float(r["rain_mm"], field_name="rain_mm", row=i, default=0.0),
        temp_c=as_float(r["temp_c"], field_name="temp_c", row=i, default=28.0),
        promo=as_bool(r["promo"]),
        local_event=as_bool(r["local_event"]),
    ))


def load_sales(session: Session, path: Path) -> int:
    return _load(session, path, lambda r, i: SalesRecord(
        date=as_date(r["date"], field_name="date", row=i),
        dish_id=r["dish_id"],
        qty_portions=as_float(r["qty_portions"], field_name="qty_portions", row=i),
        revenue_inr=as_float(r["revenue_inr"], field_name="revenue_inr", row=i, default=0.0),
    ))


def load_production(session: Session, path: Path) -> int:
    return _load(session, path, lambda r, i: ProductionRecord(
        date=as_date(r["date"], field_name="date", row=i),
        dish_id=r["dish_id"],
        planned_portions=as_float(r["planned_portions"], field_name="planned_portions", row=i),
        produced_portions=as_float(r["produced_portions"], field_name="produced_portions", row=i),
    ))


def load_batches(session: Session, path: Path) -> int:
    return _load(session, path, lambda r, i: Batch(
        id=r["id"],
        product_id=r["product_id"],
        zone_id=r["zone_id"],
        qty_kg=as_float(r["qty_kg"], field_name="qty_kg", row=i),
        received_at=as_datetime(r["received_at"], field_name="received_at", row=i),
        state=r.get("state", "raw"),
        is_cut=as_bool(r.get("is_cut")),
        unit_cost_per_kg=as_float(r["unit_cost_per_kg"], field_name="unit_cost_per_kg", row=i),
        is_open=as_bool(r.get("is_open", "1")),
        ethylene_exposed=as_bool(r.get("ethylene_exposed")),
        cold_chain_available=as_bool(r.get("cold_chain_available", "1")),
        unopened_packaging=as_bool(r.get("unopened_packaging")),
    ))


def load_inventory_events(session: Session, path: Path) -> int:
    return _load(session, path, lambda r, i: InventoryEvent(
        batch_id=r["batch_id"],
        ts=as_datetime(r["ts"], field_name="ts", row=i),
        event_type=r["event_type"],
        qty_kg=as_float(r["qty_kg"], field_name="qty_kg", row=i),
        note=r.get("note") or None,
    ))


def load_waste_events(session: Session, path: Path) -> int:
    return _load(session, path, lambda r, i: WasteEvent(
        date=as_date(r["date"], field_name="date", row=i),
        product_id=r["product_id"],
        qty_kg=as_float(r["qty_kg"], field_name="qty_kg", row=i),
        reason=r["reason"],
        value_inr=as_float(r["value_inr"], field_name="value_inr", row=i, default=0.0),
        co2e_kg=as_float(r["co2e_kg"], field_name="co2e_kg", row=i, default=0.0),
        zone_id=(r.get("zone_id") or None),
    ))


def load_zone_temperatures(session: Session, path: Path) -> int:
    return _load(session, path, lambda r, i: ZoneTemperature(
        date=as_date(r["date"], field_name="date", row=i),
        zone_id=r["zone_id"],
        mean_temp_c=as_float(r["mean_temp_c"], field_name="mean_temp_c", row=i),
        service_temp_c=as_float(r["service_temp_c"], field_name="service_temp_c", row=i),
    ))


LOADERS: dict[str, Callable[[Session, Path], int]] = {
    "demand_context.csv": load_demand_context,
    "sales.csv": load_sales,
    "production.csv": load_production,
    "batches.csv": load_batches,
    "inventory_events.csv": load_inventory_events,
    "waste_events.csv": load_waste_events,
    "zone_temperatures.csv": load_zone_temperatures,
}


def load_all(session: Session, data_dir: Path) -> LoadReport:
    """Load every CSV in dependency order. Any failure aborts the whole seed."""
    report = LoadReport()
    for filename, loader in LOADERS.items():
        path = data_dir / filename
        if not path.exists():
            report.skipped.append(filename)
            continue
        report.loaded[filename] = loader(session, path)
    return report
