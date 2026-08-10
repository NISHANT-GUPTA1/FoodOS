"""The batch identity endpoints, over HTTP.

Shares the session-scoped database with the rest of the suite and clears only
its own consignments between tests. It must not `drop_all()`: that fixture is
built once per session, and tearing the schema down here would take the kitchen
regression suite with it depending on which test ran first.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from foodos.api.app import app
from foodos.db import SessionLocal
from foodos.schema.tables import Consignment, LossRiskScore, Organization

HARVEST = "2026-08-10T05:00:00"


def _clear(session) -> None:
    """Remove every consignment, through the ORM.

    Not a bulk `DELETE FROM consignment`: seven tables hang off it — events,
    handoffs, snapshots, risk, journey, assessment, weather — and a bulk delete
    goes round the cascades and trips the foreign keys. Children are deleted
    before parents because `parent_id` is self-referential.
    """
    # `LossRiskScore.best_plan_id` is a real FK into candidate_plan, so the
    # score has to stop pointing at a plan before the plans can go. This is the
    # same ordering `routes/batches.py::_score_batch` observes on a re-score.
    for score in session.scalars(select(LossRiskScore)):
        score.best_plan_id = None
    session.flush()
    rows = list(session.scalars(select(Consignment)))
    for batch in sorted(rows, key=lambda b: b.parent_id is None):
        session.delete(batch)
    session.commit()


@pytest.fixture
def client(seeded_db):
    session = SessionLocal()
    try:
        _clear(session)
        if session.scalars(select(Organization).limit(1)).first() is None:
            session.add(Organization(id=1, name="Kolar FPO"))
            session.commit()
    finally:
        session.close()

    yield TestClient(app)

    session = SessionLocal()
    try:
        _clear(session)
    finally:
        session.close()


def _create(client, **overrides) -> dict:
    """Register through Contract 2b — `routes/batches.py` owns POST /batches.

    The passport layer deliberately does not offer a second way to create a
    batch; it grows an identity onto whatever that endpoint made.
    """
    body = {
        "commodity": "tomato",
        "qty_kg": 10_000,
        "origin": "Kolar Collection Hub",
        "destination": "Delhi APMC",
        "transport": "open_truck",
        "packaging": "ventilated_plastic_crate",
        "depart_at": "2026-08-10T10:00:00",
        "answers": {
            "maturity_stage": "breaker",
            "damage_level": "low",
            "field_heat_hours_over_30c": 2.5,
        },
    }
    body.update(overrides)
    response = client.post("/api/batches", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def _event(client, code, type_, when, **payload):
    return client.post(
        f"/api/batches/{code}/events",
        json={"type": type_, "occurred_at": when, "payload": payload},
    )


# ---------------------------------------------------------------- create


def test_a_contract_2b_batch_grows_an_identity_on_first_touch(client):
    """The bridge between the two layers. `routes/batches.py` writes a
    consignment with a status and no history; the passport layer backfills the
    identity the first time anything asks for one."""
    code = _create(client)["id"]
    body = client.get(f"/api/batches/{code}/identity").json()

    assert body["id"] == code
    # Registered through Contract 2b, so it is scored — and therefore
    # dispatchable rather than stuck at ASSESSED.
    assert body["lifecycle"] == "ready_for_dispatch"
    assert body["status"] == "assessed"
    assert body["qty_kg_remaining"] == 10_000, "backfilled from qty_kg"
    assert body["current_owner"], "backfilled from the organisation"
    assert body["passport_url"].endswith(f"/batch/{code}")






# ---------------------------------------------------------------- events


def test_an_event_returns_the_before_and_after(client):
    code = _create(client)["id"]
    _event(client, code, "dispatched", "2026-08-10T10:00:00")
    response = _event(
        client, code, "delay", "2026-08-11T01:00:00", duration_hours=6
    )
    assert response.status_code == 200
    body = response.json()

    assert body["rescored"] is True
    assert body["previous"]["rul_hours"] > body["current"]["rul_hours"]
    assert body["previous"]["loss_pct"] < body["current"]["loss_pct"]
    assert body["snapshot"]["reason"] == "delay"


def test_an_illegal_transition_is_a_409_not_a_500(client):
    code = _create(client)["id"]
    response = _event(client, code, "received", "2026-08-10T11:00:00")
    assert response.status_code == 409
    assert "cannot become received" in response.json()["detail"]


def test_an_unknown_event_type_is_a_422(client):
    code = _create(client)["id"]
    response = _event(client, code, "abducted", "2026-08-10T11:00:00")
    assert response.status_code == 422


def test_an_unknown_batch_is_a_404(client):
    response = client.get("/api/batches/TOM-XXX-99999/identity")
    assert response.status_code == 404


def test_a_custody_event_does_not_rescore(client):
    code = _create(client)["id"]
    _event(client, code, "dispatched", "2026-08-10T10:00:00")
    response = client.post(
        f"/api/batches/{code}/handoff",
        json={"to_party": "Hauler", "to_role": "transporter",
              "occurred_at": "2026-08-10T10:30:00"},
    )
    assert response.status_code == 200
    timeline = client.get(f"/api/batches/{code}/timeline").json()
    handoffs = [e for e in timeline["events"] if e["type"] == "handoff"]
    assert len(handoffs) == 1


# ---------------------------------------------------------------- timeline


def test_the_timeline_is_ordered_and_complete(client):
    """Times are derived from the batch's own harvest rather than hardcoded.

    `routes/batches.py` stamps `harvested_at` from the wall clock, so a fixed
    literal here would sort before or after the backfilled HARVEST event
    depending on the hour the suite happens to run.
    """
    created = _create(client)
    code = created["id"]
    harvest = datetime.fromisoformat(
        client.get(f"/api/batches/{code}/identity").json()["harvested_at"]
    )
    _event(client, code, "dispatched", (harvest + timedelta(hours=5)).isoformat())
    _event(
        client, code, "delay", (harvest + timedelta(hours=20)).isoformat(),
        duration_hours=6,
    )

    body = client.get(f"/api/batches/{code}/timeline").json()
    types = [e["type"] for e in body["events"]]
    assert types == ["harvest", "assessed", "dispatched", "delay"]
    times = [e["occurred_at"] for e in body["events"]]
    assert times == sorted(times)
    assert [s["sequence"] for s in body["snapshots"]] == sorted(
        s["sequence"] for s in body["snapshots"]
    )



# ---------------------------------------------------------------- handoff


def test_handoff_keeps_the_code_and_records_the_chain(client):
    code = _create(client)["id"]
    _event(client, code, "dispatched", "2026-08-10T10:00:00")
    _event(client, code, "arrived", "2026-08-12T04:00:00")
    body = client.post(
        f"/api/batches/{code}/handoff",
        json={"to_party": "Azadpur Wholesaler", "to_role": "wholesaler",
              "occurred_at": "2026-08-12T04:30:00", "qty_kg": 9850},
    ).json()

    assert body["batch_id"] == code, "the id must survive a change of hands"
    assert body["rejected_kg"] == 150.0
    assert [p["role"] for p in body["custody"]] == ["fpo", "wholesaler"]

    profile = client.get(f"/api/batches/{code}/identity").json()
    assert profile["qty_kg"] == 10_000          # as registered
    assert profile["qty_kg_remaining"] == 9_850  # what is actually there


def test_handoff_of_more_than_remains_is_a_422(client):
    code = _create(client)["id"]
    response = client.post(
        f"/api/batches/{code}/handoff",
        json={"to_party": "X", "to_role": "wholesaler", "qty_kg": 20_000},
    )
    assert response.status_code == 422


# ---------------------------------------------------------------- split


def test_split_produces_scored_children(client):
    code = _create(client)["id"]
    _event(client, code, "dispatched", "2026-08-10T10:00:00")
    _event(client, code, "arrived", "2026-08-12T04:00:00")

    body = client.post(
        f"/api/batches/{code}/split",
        json={"allocations": [
            {"qty_kg": 3000, "destination": "Retailer A", "owner_role": "retailer"},
            {"qty_kg": 7000, "destination": "Retailer B", "owner_role": "retailer"},
        ]},
    ).json()

    assert [c["id"] for c in body["children"]] == [f"{code}-A", f"{code}-B"]
    for child in body["children"]:
        assert child["parent_id"] == code
        assert child["risk"]["rul_hours"] is not None

    parent = client.get(f"/api/batches/{code}/identity").json()
    assert parent["qty_kg_remaining"] == 0
    assert [c["id"] for c in parent["children"]] == [f"{code}-A", f"{code}-B"]


def test_children_are_not_fresher_than_their_parent(client):
    """The bug this guards: a child scored without the parent's journey comes
    out looking better than the batch it was cut from."""
    code = _create(client)["id"]
    _event(client, code, "dispatched", "2026-08-10T10:00:00")
    _event(client, code, "delay", "2026-08-11T01:00:00", duration_hours=6)
    _event(client, code, "arrived", "2026-08-12T04:00:00")

    parent = client.get(f"/api/batches/{code}/identity").json()
    body = client.post(
        f"/api/batches/{code}/split",
        json={"allocations": [{"qty_kg": 10_000, "destination": "Retailer A"}]},
    ).json()
    child = body["children"][0]

    assert child["risk"]["rul_hours"] <= parent["risk"]["rul_hours"] + 1e-6
    assert child["risk"]["loss_pct"] >= parent["risk"]["loss_pct"] - 1e-6


def test_an_unbalanced_split_is_refused(client):
    code = _create(client)["id"]
    response = client.post(
        f"/api/batches/{code}/split",
        json={"allocations": [{"qty_kg": 3000, "destination": "A"}]},
    )
    assert response.status_code == 422
    assert "allocations sum" in response.json()["detail"]


# ---------------------------------------------------------------- list & fefo








def test_fefo_excludes_emptied_and_terminal_batches(client):
    code = _create(client)["id"]
    _create(client, transit_hours=3, transport="reefer")
    _event(client, code, "dispatched", "2026-08-10T10:00:00")
    _event(client, code, "arrived", "2026-08-12T04:00:00")
    client.post(
        f"/api/batches/{code}/split",
        json={"allocations": [{"qty_kg": 10_000, "destination": "A"}]},
    )

    body = client.get("/api/inventory/fefo").json()
    codes = [row["id"] for row in body["rows"]]
    assert code not in codes, "an emptied parent is history, not inventory"
    assert f"{code}-A" in codes
    lives = [r["rul_hours"] for r in body["rows"] if r["rul_hours"] is not None]
    assert lives == sorted(lives)


# ---------------------------------------------------------------- passport


def test_the_passport_carries_handling_advice_not_economics(client):
    code = _create(client)["id"]
    body = client.get(f"/api/batches/{code}/passport").json()

    assert body["recommended_action"]
    assert body["handle_within_hours"] is not None
    assert [p["role"] for p in body["custody"]] == ["fpo"]
    # Anyone holding the crate can scan this.
    blob = str(body)
    for leaked in ("net_value", "gross_revenue", "unit_price", "logistics_cost"):
        assert leaked not in blob, leaked


def test_the_qr_encodes_the_passport_url(client):
    from tests.test_batch.test_qr import _decode

    code = _create(client)["id"]
    response = client.get(f"/api/batches/{code}/qr.svg")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/svg+xml")

    from foodos import qr as qrlib
    from foodos.config import settings

    expected = f"{settings.public_base_url.rstrip('/')}/batch/{code}"
    assert _decode(qrlib.encode(expected)) == expected


def test_a_qr_is_never_issued_for_a_batch_that_does_not_exist(client):
    """A QR that scans perfectly and then 404s is the worst failure to hit at
    a mandi gate."""
    assert client.get("/api/batches/TOM-XXX-99999/qr.svg").status_code == 404
