"""Seed the agri consignments — §4, H3-8.

`python -m foodos.ingest.seed` has to build the agri demo database *and* the
kitchen one in a single command. This command runs 50 times before the demo; it
is sacred, and it must be idempotent.

The demo batch T1024 is not invented here. Its answers come from
`content/questionnaire/tomato.yaml::demo_answers`, which D owns — so the batch
on stage and the questionnaire a judge fills in are driven by the same file. If
D retunes a constant, T1024 moves with it instead of drifting away from it.
"""

from __future__ import annotations

import csv
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from foodos import content
from foodos.config import SAMPLE_DIR
from foodos.schema import BatchAssessment, Consignment, Organization, ShipmentJourney

FILENAME = "consignments.csv"

#: The demo shipment, §7: 10 t Kolar -> Delhi. Everything else about it comes
#: from D's demo_answers.
DEMO = {
    "code": "T1024",
    "commodity": "tomato",
    "qty_kg": 10000.0,
    "origin": "Kolar Collection Hub",
    "destination": "delhi_apmc",
    "transport": "open_truck",
    "packaging": "ventilated_plastic_crate",
    "harvest_offset_hours": -18,
}

#: Two more so Screen 1 has something to group. Deliberately unremarkable.
FLEET = [
    {
        "code": "T1025",
        "commodity": "tomato",
        "qty_kg": 6000.0,
        "origin": "Kolar Collection Hub",
        "destination": "bengaluru_apmc",
        "transport": "tarpaulin",
        "packaging": "ventilated_plastic_crate",
        "harvest_offset_hours": -6,
        "answers": {"harvest_window": "pre_dawn", "field_heat_hours_over_30c": 1.0},
    },
    {
        "code": "T1026",
        "commodity": "tomato",
        "qty_kg": 12000.0,
        "origin": "Kolar Collection Hub",
        "destination": "delhi_apmc",
        "transport": "open_truck",
        "packaging": "gunny_bag",
        "harvest_offset_hours": -30,
        "answers": {"harvest_window": "midday", "field_heat_hours_over_30c": 7.5},
    },
]


def _rows() -> list[dict]:
    """The demo fleet, from consignments.csv when present, else the built-ins.

    A committed CSV is the documented path (§4 H3-8 ships one); the built-ins
    exist so a fresh clone still seeds if the file is missing.
    """
    path = Path(SAMPLE_DIR) / FILENAME
    if path.exists():
        with path.open(encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))

    demo_answers = {}
    try:
        demo_answers = content.questionnaire("tomato").get("demo_answers", {})
    except Exception:
        demo_answers = {}

    out = [{**DEMO, "answers": demo_answers.get("T1024", {})}]
    out.extend(FLEET)
    return out


def load(session: Session, org_id: int | None = None) -> dict:
    """Insert the consignments. Existing codes are left alone."""
    if org_id is None:
        org = session.scalar(select(Organization))
        org_id = org.id if org else 1

    now = datetime.now()
    created = 0

    for row in _rows():
        code = str(row["code"])
        if session.scalar(select(Consignment).where(Consignment.code == code)):
            continue

        answers = row.get("answers") or {}
        if isinstance(answers, str):
            answers = {}

        consignment = Consignment(
            code=code,
            org_id=org_id,
            commodity=str(row["commodity"]),
            qty_kg=float(row["qty_kg"]),
            origin=str(row["origin"]),
            destination=str(row["destination"]),
            harvested_at=now + timedelta(hours=float(row.get("harvest_offset_hours", -12))),
            status="registered",
            field_heat_hours_over_30c=_float(answers.get("field_heat_hours_over_30c")),
            damage_factor=answers.get("damage_level"),
            maturity=_band(answers.get("maturity_stage")),
        )
        session.add(consignment)
        session.flush()

        session.add(BatchAssessment(consignment_id=consignment.id, answers=answers))
        session.add(
            ShipmentJourney(
                consignment_id=consignment.id,
                transport=str(row["transport"]),
                packaging=str(row["packaging"]),
                depart_at=now,
            )
        )
        created += 1

    session.flush()
    return {"created": created, "source": "content/questionnaire demo_answers"}


def _float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _band(stage) -> str | None:
    if not stage:
        return None
    return {
        "mature_green": "low",
        "breaker": "low",
        "turning": "medium",
        "pink": "medium",
        "light_red": "high",
        "red": "high",
    }.get(str(stage))
