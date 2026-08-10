"""Rescue channels.

Channels are **D's content** (`backend/foodos/content/channels.yaml`), not A's
data — they describe partners and safety rules, not observations. B ships a
working default set so RECOVER is never blocked waiting on D, and reads D's
file the moment it appears.

YAML is read only if PyYAML happens to be installed; JSON always works. B does
not add a dependency for this — if D wants YAML they own that decision.
"""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy.orm import Session

from foodos.config import BACKEND_ROOT
from foodos.schema.enums import ChannelType
from foodos.schema.tables import Channel

CONTENT_DIR = BACKEND_ROOT / "foodos" / "content"

# type, name, distance_km, lead_h, min_qty, max_qty, categories,
# price_factor, fixed_cost, cost_per_km, social_per_kg, rules
DEFAULT_CHANNELS: list[dict] = [
    {
        "type": ChannelType.STAFF_MEAL, "name": "Staff meal",
        "distance_km": 0.0, "lead_time_hours": 0.0, "min_qty": 0.5,
        "max_qty": 8.0, "price_factor": 0.35, "fixed_cost": 0.0,
    },
    {
        "type": ChannelType.MARKDOWN, "name": "In-store markdown 30%",
        "distance_km": 0.0, "lead_time_hours": 2.0, "min_qty": 1.0,
        "price_factor": 0.62, "fixed_cost": 50.0,
    },
    {
        "type": ChannelType.B2B_TRANSFER, "name": "Nalapaka Kitchen (400 m)",
        "distance_km": 0.4, "lead_time_hours": 3.0, "min_qty": 2.0,
        "price_factor": 0.72, "fixed_cost": 120.0, "cost_per_km": 25.0,
    },
    {
        "type": ChannelType.B2B_TRANSFER, "name": "Anna Canteen (2.1 km)",
        "distance_km": 2.1, "lead_time_hours": 6.0, "min_qty": 5.0,
        "price_factor": 0.68, "fixed_cost": 120.0, "cost_per_km": 25.0,
    },
    {
        "type": ChannelType.DONATION, "name": "Feeding Hands NGO",
        "distance_km": 3.2, "lead_time_hours": 12.0, "min_qty": 3.0,
        "price_factor": 0.0, "fixed_cost": 150.0, "cost_per_km": 18.0,
        "social_value_per_kg": 40.0,
        "eligibility_rules": {"min_rsl_days": 1.0, "min_intake_grade": 0.75},
    },
    {
        "type": ChannelType.PROCESSING, "name": "Nandini Puree Unit",
        "distance_km": 8.0, "lead_time_hours": 24.0, "min_qty": 10.0,
        "accepted_categories": ["vegetable", "fruit", "fruiting_vegetable"],
        "price_factor": 0.34, "fixed_cost": 200.0, "cost_per_km": 15.0,
        "eligibility_rules": {"min_intake_grade": 0.6},
    },
    {
        "type": ChannelType.ANIMAL_FEED, "name": "Dairy co-op feed line",
        "distance_km": 6.0, "lead_time_hours": 18.0, "min_qty": 5.0,
        "price_factor": 0.08, "fixed_cost": 90.0, "cost_per_km": 12.0,
    },
    {
        "type": ChannelType.COMPOST, "name": "On-site composter",
        "distance_km": 0.0, "lead_time_hours": 1.0, "min_qty": 0.0,
        "price_factor": 0.0, "fixed_cost": 30.0,
    },
]


# D's content pack and this schema use independent vocabularies for what a
# channel *is*: content/channels.yaml classifies by commercial mechanism
# ("own_demand", "aggregator", "downcycle"), ChannelType classifies by the
# action the engine takes. Only "donation" happens to spell the same. Mapped on
# channel id, which lines up one-to-one, rather than on type, which does not.
_TYPE_BY_ID = {
    "dine_in_special": "markdown",
    "app_flash_deal": "markdown",
    "b2b_transfer": "b2b_transfer",
    "surplus_marketplace": "b2b_transfer",
    "staff_meal": "staff_meal",
    "ngo_donation": "donation",
    "animal_feed": "animal_feed",
    "compost": "compost",
    "disposal": "compost",
}


# D's content pack and A's generator classify produce at different grains.
# channels.yaml speaks in retail categories ("vegetable", "poultry",
# "dry_goods"); the product table holds A's kitchen categories ("hard_veg",
# "leafy", "root_allium", "meat", "dry"). Only "dairy" is spelled the same in
# both. Left untranslated, every channel that restricts by category rejects
# every batch, and the ranker falls through to do-nothing for the whole demo.
_CATEGORY_ALIASES = {
    "vegetable": ["hard_veg", "soft_veg", "leafy", "leafy_green", "root_allium", "herb"],
    "cut_vegetable": ["hard_veg", "soft_veg", "leafy", "leafy_green", "root_allium", "herb"],
    "dry_goods": ["dry"],
    "poultry": ["meat"],
    "red_meat": ["meat"],
    "seafood": ["meat"],
    "dairy": ["dairy"],
    "frozen": ["prepared"],
}


def _expand_categories(values: list) -> list[str]:
    out: list[str] = []
    for v in values:
        out.extend(_CATEGORY_ALIASES.get(str(v), [str(v)]))
    return sorted(set(out))


def _normalise(doc) -> list[dict] | None:
    """Accept either a bare list or D's real file layout.

    content/channels.yaml is a mapping — {version, exclusion_reasons, channels,
    preserve_actions} — not a list, and its field names are the content pack's,
    not this table's. Reading it raw gave `TypeError: string indices must be
    integers` because iterating the mapping yields its keys.
    """
    rows = doc.get("channels") if isinstance(doc, dict) else doc
    if not isinstance(rows, list):
        return None

    out = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        merged = dict(row)
        # D's name -> this table's name, only where they disagree.
        for content_key, table_key in (
            ("min_qty_kg", "min_qty"),
            ("max_qty_kg", "max_qty"),
            ("allowed_categories", "accepted_categories"),
            ("recovery_factor", "price_factor"),
        ):
            if content_key in merged and table_key not in merged:
                merged[table_key] = merged[content_key]

        mapped = _TYPE_BY_ID.get(str(merged.get("id", "")))
        if mapped:
            merged["type"] = mapped

        # D's recovery_factor and this table's price_factor are not the same
        # quantity for a donation. The content pack scores a donation at 0.18
        # because giving food away recovers goodwill and tax relief; the engine
        # scores cash only, and credits the rest through social_value_per_kg.
        # Carrying 0.18 across makes a donation look like an 18% cash sale.
        if mapped == "donation":
            merged["price_factor"] = 0.0

        # D writes the string "any" for an unrestricted channel; this table
        # expresses that as an empty list. Left as a string it reaches
        # rescue.channel_action() truthy and every category then fails the
        # membership test by substring, which silently excludes every channel
        # and leaves do-nothing as the best action.
        # D states the safety bar as min_residual_life_hours plus a `requires`
        # list of prose flags; the engine reads an eligibility_rules mapping.
        rules = dict(merged.get("eligibility_rules") or {})
        hours = merged.get("min_residual_life_hours")
        if hours is not None and "min_rsl_days" not in rules:
            rules["min_rsl_days"] = float(hours) / 24.0
        requires = merged.get("requires") or []
        if isinstance(requires, list) and "unopened_packaging" in requires:
            rules.setdefault("requires_unopened", True)
        # channels.yaml has no intake-grade field at all. A donation is the one
        # route where the engine refuses on grade rather than price — giving
        # away food that is not fit to eat is the failure this gate exists to
        # prevent — so B's own default for the donation channel is applied when
        # the content pack is silent.
        if mapped == "donation":
            rules.setdefault("min_intake_grade", 0.75)
        if rules:
            merged["eligibility_rules"] = rules

        cats = merged.get("accepted_categories")
        if isinstance(cats, str):
            cats = [] if cats.strip().lower() in {"any", "all", "*"} else [cats]
        if isinstance(cats, list):
            merged["accepted_categories"] = _expand_categories(cats)

        out.append(merged)
    return out or None


def _load_from_content() -> list[dict] | None:
    """D's channel file, if it exists. JSON always; YAML when PyYAML is around."""
    json_path = CONTENT_DIR / "channels.json"
    if json_path.exists():
        return _normalise(json.loads(json_path.read_text(encoding="utf-8")))

    yaml_path = CONTENT_DIR / "channels.yaml"
    if yaml_path.exists():
        try:
            import yaml  # noqa: PLC0415 — optional, D's dependency not B's
        except ModuleNotFoundError:
            return None
        return _normalise(yaml.safe_load(yaml_path.read_text(encoding="utf-8")))
    return None


def load(session: Session, org_id: int) -> tuple[int, str]:
    """Populate the channel table. Returns (count, source)."""
    rows = _load_from_content()
    source = "content/" if rows else "B defaults"
    rows = rows or DEFAULT_CHANNELS

    for row in rows:
        session.add(
            Channel(
                org_id=org_id,
                type=row["type"],
                name=row["name"],
                contact=row.get("contact"),
                distance_km=float(row.get("distance_km", 0.0)),
                lead_time_hours=float(row.get("lead_time_hours", 0.0)),
                min_qty=float(row.get("min_qty", 0.0)),
                max_qty=(
                    float(row["max_qty"]) if row.get("max_qty") is not None else None
                ),
                accepted_categories=row.get("accepted_categories", []),
                price_factor=float(row.get("price_factor", 0.0)),
                fixed_cost=float(row.get("fixed_cost", 0.0)),
                cost_per_km=float(row.get("cost_per_km", 0.0)),
                social_value_per_kg=float(row.get("social_value_per_kg", 0.0)),
                eligibility_rules=row.get("eligibility_rules", {}),
                active=bool(row.get("active", True)),
            )
        )
    session.flush()
    return len(rows), source
