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


def _load_from_content() -> list[dict] | None:
    """D's channel file, if it exists. JSON always; YAML when PyYAML is around."""
    json_path = CONTENT_DIR / "channels.json"
    if json_path.exists():
        return json.loads(json_path.read_text(encoding="utf-8"))

    yaml_path = CONTENT_DIR / "channels.yaml"
    if yaml_path.exists():
        try:
            import yaml  # noqa: PLC0415 — optional, D's dependency not B's
        except ModuleNotFoundError:
            return None
        return yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
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
