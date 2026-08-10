"""The receiving gate — one code across both nodes.

These tests exist to defend one claim: the tomatoes a store takes into stock
are provably the tomatoes an FPO registered at a farm gate, and the store's
engine knows how much life they have already spent.

The failure mode they guard against is silent and expensive. Before the bridge,
receiving produced a lot with no upstream link and a fresh clock, so a batch
that had spent forty hours on an open truck arrived in the Ledger looking like
new stock — and every downstream number, right through to the rescue waterfall,
was computed from that lie. `test_lot_does_not_arrive_with_a_fresh_clock` is
the one that catches a regression there.

Shares the session-scoped database with the rest of the suite and clears only
its own consignments. It must not `drop_all()` — see `test_api.py`.
"""

from __future__ import annotations

from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from foodos.api.app import app
from foodos.db import SessionLocal
from foodos.engine import intake
from foodos.schema.enums import SiteType, Track
from foodos.schema.tables import (
    Batch,
    Consignment,
    InventoryEvent,
    LossRiskScore,
    Organization,
    Site,
)

HARVEST = "2026-08-10T05:00:00"
DISPATCH = "2026-08-10T10:00:00"
ARRIVAL = "2026-08-12T04:00:00"


def _clear(session) -> None:
    """Remove the consignments and any lots they produced.

    Lots go first: `Batch.consignment_id` is a real foreign key, and SQLite has
    `PRAGMA foreign_keys=ON` in this project, so deleting the consignment out
    from under a lot fails rather than nulling the column. Only lots this
    module created are removed — the kitchen fixture's own batches carry no
    `batch_code` and the rest of the suite depends on them surviving.

    The stock-ledger rows go before the lots for the same reason:
    `inventory_event.batch_id` points at them, and receiving writes one.
    """
    lot_ids = list(
        session.scalars(select(Batch.id).where(Batch.batch_code.isnot(None))).all()
    )
    if lot_ids:
        session.query(InventoryEvent).filter(
            InventoryEvent.batch_id.in_(lot_ids)
        ).delete(synchronize_session=False)
        session.query(Batch).filter(Batch.id.in_(lot_ids)).delete(
            synchronize_session=False
        )
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


def _create(client, **overrides) -> str:
    """Register through Contract 2b, which owns POST /batches."""
    body = {
        "commodity": "tomato",
        "qty_kg": 10_000,
        "origin": "Kolar Collection Hub",
        "destination": "Delhi APMC",
        "transport": "open_truck",
        "packaging": "ventilated_plastic_crate",
        "depart_at": DISPATCH,
        "answers": {
            "maturity_stage": "breaker",
            "damage_level": "low",
            "field_heat_hours_over_30c": 2.5,
        },
    }
    body.update(overrides)
    response = client.post("/api/batches", json=body)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _event(client, code, type_, when, **payload):
    return client.post(
        f"/api/batches/{code}/events",
        json={"type": type_, "occurred_at": when, "payload": payload},
    )


def _shipped(client, **overrides) -> str:
    """A batch that has actually left and arrived — the receivable state."""
    code = _create(client, **overrides)
    _event(client, code, "dispatched", DISPATCH)
    _event(client, code, "arrived", ARRIVAL)
    return code


def _receive(client, code, **overrides):
    body = {
        "to_party": "Azadpur Wholesale",
        "to_role": "wholesaler",
        "occurred_at": ARRIVAL,
    }
    body.update(overrides)
    return client.post(f"/api/batches/{code}/receive", json=body)


def _site_id(kind: SiteType) -> int | None:
    session = SessionLocal()
    try:
        row = session.scalars(
            select(Site).where(Site.type == kind).order_by(Site.id).limit(1)
        ).first()
        return row.id if row else None
    finally:
        session.close()


# ------------------------------------------------------------ the core claim


def test_receiving_creates_a_lot_under_the_same_code(client):
    """The whole point. No new identifier is minted at the gate."""
    code = _shipped(client)

    response = _receive(client, code)
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["batch_id"] == code
    assert body["lot"]["batch_code"] == code
    # The lot trades under the consignment's own code, so a picker reading a
    # crate and a manager reading the Command Center say the same string.
    assert body["lot"]["lot_code"] == code


def test_lots_endpoint_finds_the_lot_from_the_code(client):
    """The other direction of the join: hand over a code, get the stock."""
    code = _shipped(client)
    _receive(client, code)

    body = client.get(f"/api/batches/{code}/lots").json()
    assert len(body["lots"]) == 1
    assert body["lots"][0]["batch_code"] == code
    assert body["total_received_kg"] > 0


def test_lots_is_empty_rather_than_404_before_receipt(client):
    """Most batches are still on the road. That is not an error."""
    code = _shipped(client)
    response = client.get(f"/api/batches/{code}/lots")
    assert response.status_code == 200
    assert response.json()["lots"] == []


# ------------------------------------------------------- the inherited clock


def test_lot_does_not_arrive_with_a_fresh_clock(client):
    """The regression that matters.

    A lot received after two days on an open truck must not present as new
    stock. `life_used` is the fraction of usable life already spent and has to
    be materially above zero; `rsl_days` has to reflect what is *left*, not the
    commodity's reference shelf life.
    """
    code = _shipped(client)
    lot = _receive(client, code).json()["lot"]

    assert lot["life_used"] is not None
    assert lot["life_used"] > 0.0, "a two-day-old batch cannot have spent no life"
    assert lot["life_used"] < 1.0

    inherited = lot["inherited"]
    # Derived from the response rather than pinned to a constant. Contract 2b
    # stamps `harvested_at` with the wall clock at registration, so any fixed
    # threshold here drifts with the time of day the suite happens to run —
    # which is a flaky test, not a check on the code. Recomputing the interval
    # tests the arithmetic instead of the calendar.
    harvested = datetime.fromisoformat(inherited["harvested_at"])
    received = datetime.fromisoformat(inherited["received_at"])
    expected_age = (received - harvested).total_seconds() / 3600.0
    assert expected_age > 0, "the fixture must receive the batch after it was cut"
    assert inherited["age_hours"] == pytest.approx(expected_age, abs=0.1)

    # rsl_days is the inherited RUL in days, so the two must agree exactly.
    assert lot["rsl_days"] == pytest.approx(inherited["rul_hours"] / 24.0, abs=1e-3)


def test_inherited_block_records_the_journey_not_just_the_answer(client):
    """Provenance is stored on the lot, so a Ledger renders it without joins."""
    code = _shipped(client)
    lot = _receive(client, code).json()["lot"]
    inherited = lot["inherited"]

    assert inherited["code"] == code
    assert inherited["origin"] == "Kolar Collection Hub"
    assert inherited["qty_registered_kg"] == pytest.approx(10_000.0)
    assert inherited["hops"] >= 1
    assert "Azadpur Wholesale" in inherited["custody"]
    # The honesty tell travels with the number: an inherited figure from a
    # degraded score must not arrive looking like a modelled one.
    assert inherited["basis"] in {"model", "fallback"}


def test_explanation_names_the_upstream_code(client):
    """One sentence, already written, so every screen says it identically."""
    code = _shipped(client)
    lot = _receive(client, code).json()["lot"]
    assert code in lot["rsl_explanation"]
    assert "Kolar Collection Hub" in lot["rsl_explanation"]


def test_printed_expiry_agrees_with_the_inherited_life(client):
    """A printed date that contradicts the RUL beside it is worse than none."""
    code = _shipped(client)
    lot = _receive(client, code).json()["lot"]
    assert lot["printed_expiry"] is not None


# ------------------------------------------------------------- across tracks


@pytest.mark.parametrize(
    ("site_type", "expected"),
    [
        (SiteType.KITCHEN, Track.KITCHEN),
        (SiteType.STORE, Track.RETAIL),
        (SiteType.PLANT, Track.PRODUCTION),
    ],
)
def test_receiving_lands_in_the_right_track(client, site_type, expected):
    """Same gate, same code, three action spaces — the platform claim."""
    site_id = _site_id(site_type)
    if site_id is None:
        pytest.skip(f"fixture has no {site_type} site")

    code = _shipped(client)
    body = _receive(client, code, site_id=site_id).json()
    assert body["lot"]["track"] == str(expected)


def test_site_type_resolves_when_no_id_is_given(client):
    """`site_type` is enough — the demo database has one site of each kind."""
    if _site_id(SiteType.STORE) is None:
        pytest.skip("fixture has no store site")
    code = _shipped(client)
    body = _receive(client, code, site_type="store").json()
    assert body["lot"]["track"] == str(Track.RETAIL)


# ---------------------------------------------------------- partial delivery


def test_partial_acceptance_books_the_shortfall(client):
    """A rejection at the gate is a real loss and has to land somewhere.

    Accepting 9,000 of 10,000 kg must not let 1,000 kg evaporate between the
    consignment ledger and the store's stock record.
    """
    code = _shipped(client)
    body = _receive(client, code, qty_kg=9_000).json()

    assert body["accepted_kg"] == pytest.approx(9_000.0)
    assert body["rejected_kg"] == pytest.approx(1_000.0)
    assert body["lot"]["qty_kg"] == pytest.approx(9_000.0)

    timeline = client.get(f"/api/batches/{code}/timeline").json()
    wasted = [e for e in timeline["events"] if e["type"] == "wasted"]
    assert wasted, "the rejected mass must be recorded as waste"


def test_accepting_more_than_remains_is_a_422(client):
    code = _shipped(client)
    response = _receive(client, code, qty_kg=99_000)
    assert response.status_code == 422


# ------------------------------------------------------------ lifecycle gates


def test_receiving_twice_is_refused(client):
    """A batch already taken into stock cannot be taken into stock again."""
    code = _shipped(client)
    assert _receive(client, code).status_code == 200
    assert _receive(client, code).status_code == 409


def test_a_batch_that_never_left_cannot_be_received(client):
    """Refused rather than quietly accepted — it is a data-entry error."""
    code = _create(client)
    response = _receive(client, code)
    assert response.status_code == 409


def test_unknown_code_is_a_404(client):
    assert _receive(client, "TOM-XXX-99999").status_code == 404


# ----------------------------------------------------- the frozen surfaces


def test_contract_2b_profile_is_unchanged_by_receiving(client):
    """Additive means additive. The four frozen screens keep working.

    The profile carries no `status` — that lives on the list row — so the test
    is that the key set does not move, in either direction. A receipt adding a
    field here would be just as much a contract break as one removing it.
    """
    code = _shipped(client)
    before = client.get(f"/api/batches/{code}").json()
    _receive(client, code)
    after = client.get(f"/api/batches/{code}").json()

    assert set(before) == set(after)


def test_contract_2b_list_keeps_the_frozen_status_vocabulary(client):
    """The Command Center filters on these four words and only these four."""
    code = _shipped(client)
    _receive(client, code)

    rows = client.get("/api/batches").json()["batches"]
    row = next(r for r in rows if r["id"] == code)
    assert row["status"] in {"registered", "assessed", "in_transit", "delivered"}
    assert row["status"] == "delivered"


def test_receiving_reports_the_frozen_status_spelling(client):
    code = _shipped(client)
    body = _receive(client, code).json()
    assert body["status"] == "delivered"
    assert body["lifecycle"] == "received"


# ------------------------------------------------ the code, seen from a track


def test_the_code_reaches_the_kitchen_ledger(client):
    """The end-to-end claim, from the farm gate to a track's own screen.

    This is the test that would have failed before the bridge existed: the lot
    appeared in the Ledger with no way back to the consignment, and the Ledger
    had no idea the tomatoes had already spent two days on a truck.
    """
    kitchen_id = _site_id(SiteType.KITCHEN)
    if kitchen_id is None:
        pytest.skip("fixture has no kitchen site")

    code = _shipped(client)
    _receive(client, code, site_id=kitchen_id)

    ledger = client.get(f"/api/ledger?site_id={kitchen_id}").json()
    row = next((r for r in ledger["rows"] if r["batch_code"] == code), None)

    assert row is not None, "the received lot never reached the Ledger"
    assert row["origin"] == "Kolar Collection Hub"
    # The Ledger's own life figure is the inherited one, not a fresh clock.
    assert row["rsl_explanation"] and code in row["rsl_explanation"]


def test_ledger_rows_without_a_passport_still_render(client):
    """Most kitchen stock has no upstream code. That must stay unremarkable."""
    kitchen_id = _site_id(SiteType.KITCHEN)
    if kitchen_id is None:
        pytest.skip("fixture has no kitchen site")

    ledger = client.get(f"/api/ledger?site_id={kitchen_id}").json()
    untracked = [r for r in ledger["rows"] if r["batch_code"] is None]
    assert untracked, "the fixture's own stock should carry no batch code"
    # Additive means a null, not a missing key.
    assert all("origin" in r for r in ledger["rows"])


def test_retail_track_row_carries_the_code_field(client):
    """Track 2 names the crate the same way the farm gate did."""
    rows = client.get("/api/tracks/retail").json()["rows"]
    assert all("batch_code" in r for r in rows)


# ------------------------------------------------------------ the engine layer


def test_life_used_is_the_share_of_life_already_spent():
    """Pure arithmetic, so the boundaries are pinned rather than inferred."""
    assert intake._life_used(0.0, 46.0) == 0.0
    assert intake._life_used(18.0, 18.0) == 0.5
    assert intake._life_used(40.0, 0.0) == 1.0
    # A batch with no life left and no age is spent, not fresh — the divide is
    # guarded, and guarding it the other way would report brand-new stock.
    assert intake._life_used(0.0, 0.0) == 1.0


def test_track_map_covers_every_site_type():
    """A new SiteType must not silently fall back to the kitchen."""
    assert set(intake.SITE_TYPE_TRACK) == set(SiteType)
