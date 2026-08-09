"""Column mapping. Real POS and inventory exports never use our column names.

`resolve()` maps whatever arrived onto the canonical field, case- and
punctuation-insensitively. Unmapped columns are reported, never silently
dropped — a column the wizard did not understand is the single most common
cause of a wrong number downstream.
"""

from __future__ import annotations

import re

ALIASES: dict[str, tuple[str, ...]] = {
    "business_date": ("date", "business date", "txn date", "day", "order date", "bill date"),
    "site": ("site", "outlet", "store", "location", "branch", "kitchen", "plant"),
    "sku": ("sku", "item code", "item", "product", "product code", "code", "dish"),
    "name": ("name", "item name", "product name", "description", "dish name"),
    "category": ("category", "group", "item group", "dept", "department"),
    "qty": ("qty", "quantity", "units", "portions", "sold", "qty sold", "amount"),
    "revenue": ("revenue", "sales", "net sales", "value", "amount", "total"),
    "planned_qty": ("planned qty", "planned", "plan", "production plan", "target"),
    "actual_qty": ("actual qty", "actual", "produced", "production", "made"),
    "uom": ("uom", "unit", "units of measure", "measure"),
    "unit_cost": ("unit cost", "cost", "cost price", "purchase price", "rate"),
    "unit_price": ("unit price", "price", "selling price", "mrp", "sale price"),
    "unit_weight_kg": ("unit weight kg", "weight", "portion weight", "weight kg"),
    "reason": ("reason", "waste reason", "cause", "waste type"),
    "stage": ("stage", "waste stage", "step"),
    "lot_code": ("lot code", "lot", "batch", "batch code", "batch no"),
    "received_at": ("received at", "received", "grn date", "receipt date", "intake"),
    "printed_expiry": ("printed expiry", "expiry", "best before", "use by", "exp date"),
    "qty_received": ("qty received", "received qty", "grn qty", "in qty"),
    "qty_remaining": ("qty remaining", "on hand", "stock", "balance", "closing"),
    "storage_zone": ("storage zone", "zone", "location", "store room", "chiller"),
    "intake_grade": ("intake grade", "grade", "quality grade", "quality"),
    "covers": ("covers", "guests", "pax", "footfall", "customers"),
    "promo_flag": ("promo flag", "promo", "promotion", "offer"),
    "is_holiday": ("is holiday", "holiday", "public holiday"),
}

_NORMALISE = re.compile(r"[^a-z0-9]+")


def _norm(value: str) -> str:
    return _NORMALISE.sub(" ", str(value).strip().lower()).strip()


_LOOKUP: dict[str, str] = {}
for canonical, variants in ALIASES.items():
    _LOOKUP[_norm(canonical)] = canonical
    for variant in variants:
        _LOOKUP.setdefault(_norm(variant), canonical)


def resolve(headers: list[str]) -> tuple[dict[str, str], list[str]]:
    """Map raw headers onto canonical names.

    Returns (mapping from raw header to canonical name, list of unmapped headers).
    """
    mapping: dict[str, str] = {}
    unmapped: list[str] = []
    for header in headers:
        canonical = _LOOKUP.get(_norm(header))
        if canonical is None:
            unmapped.append(header)
        else:
            mapping[header] = canonical
    return mapping, unmapped


def apply(row: dict, mapping: dict[str, str]) -> dict:
    return {mapping[k]: v for k, v in row.items() if k in mapping}
