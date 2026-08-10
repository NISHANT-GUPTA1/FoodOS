"""Packaging and transport spellings, across all three teams' vocabularies.

Three enums name the same physical objects and only `ventilated_plastic_crate`
appears in all three:

    A  `agri.scenario.Packaging`   loose_bulk, gunny_bag, wooden_crate, ventilated_plastic_crate
    B  `schema.enums.PackagingType`  loose, jute_sack, ventilated_plastic_crate, cfb_carton
    C  `api/batchContract.ts`        ventilated_plastic_crate, gunny_bag, wooden_crate, corrugated_box

Rows carrying A's spelling are already stored in a column typed with B's — the
seed ships T1026 in a `gunny_bag` — and C's Create Batch screen can send a
fourth set. A strict `PackagingType(value)` in `_declared_base` therefore raised
on three of the four values the UI offers and on a seeded demo batch, turning
every event posted against them into a 500.

These tests pin the tolerant resolution. `conftest.make_batch` builds every
fixture with the one packaging value that happened to work, which is precisely
why nothing here was caught upstream, so each case names its spelling
explicitly rather than going through the factory's default.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from foodos.agri.scenario import Packaging as AgriPackaging
from foodos.agri.scenario import TransportMode as AgriTransport
from foodos.engine import batch_intelligence as intelligence
from foodos.schema.enums import BatchEventType, PackagingType, TransportMode

from .conftest import HARVEST

#: Every spelling any part of the system can put in `ShipmentJourney.packaging`.
ALL_PACKAGING_SPELLINGS = sorted(
    {e.value for e in PackagingType}
    | {e.value for e in AgriPackaging}
    | {"ventilated_plastic_crate", "gunny_bag", "wooden_crate", "corrugated_box"}
)

ALL_TRANSPORT_SPELLINGS = sorted(
    {e.value for e in TransportMode}
    | {e.value for e in AgriTransport}
    | {"open_truck", "tarpaulin", "reefer"}
)


@pytest.mark.parametrize("spelling", ALL_PACKAGING_SPELLINGS)
def test_every_packaging_spelling_resolves(spelling):
    """No spelling in circulation raises, and each lands on one of A's values."""
    assert intelligence._resolve_packaging(spelling) in set(AgriPackaging)


@pytest.mark.parametrize("spelling", ALL_TRANSPORT_SPELLINGS)
def test_every_transport_spelling_resolves(spelling):
    assert intelligence._resolve_transport(spelling) in set(AgriTransport)


@pytest.mark.parametrize("junk", ["", "   ", "banana_box", None])
def test_unknown_packaging_falls_back_rather_than_raising(junk):
    """A bad string costs one crush coefficient, not the batch's whole profile.

    Refusing to score is the worse failure: the manager loses the RUL reading
    they opened the screen for because a packaging string was misspelt.
    """
    assert intelligence._resolve_packaging(junk) == intelligence.DEFAULT_BASE["packaging"]
    assert (
        intelligence._resolve_transport(junk)
        == intelligence.DEFAULT_BASE["transport_mode"]
    )


@pytest.mark.parametrize("spelling", ALL_PACKAGING_SPELLINGS)
def test_declared_base_survives_every_packaging_spelling(session, make_batch, spelling):
    """`build_base` is the function that used to raise. It must not."""
    batch = make_batch()
    batch.journey.packaging = spelling
    session.flush()

    base = intelligence.build_base(batch)
    assert base["packaging"] in set(AgriPackaging)


def test_gunny_bag_batch_can_be_rescored(session, make_batch):
    """The T1026 case, end to end through the engine.

    A seeded demo batch shipping in a gunny bag used to raise ValueError on the
    first event posted against it — and T1026 is the worst-risk batch in the
    seed, so it is the row a demo is most likely to open.
    """
    batch = make_batch()
    batch.journey.packaging = "gunny_bag"
    session.flush()

    scored = intelligence.score(batch, as_of=HARVEST + timedelta(hours=5))
    assert scored.rul_hours > 0
    assert 0.0 <= scored.loss_pct <= 100.0


def test_packaging_ordering_is_physical(session, make_batch):
    """Better packaging must predict less loss, whichever spelling names it.

    Guards the alias table against a silent mis-wiring: aliasing
    `corrugated_box` onto LOOSE would still resolve, still return a number, and
    quietly rank a carton as the worst option on the What-If screen.
    """

    def loss_for(spelling: str) -> float:
        batch = make_batch()
        batch.journey.packaging = spelling
        session.flush()
        return intelligence.score(batch, as_of=HARVEST + timedelta(hours=5)).loss_pct

    crate = loss_for("ventilated_plastic_crate")
    carton = loss_for("corrugated_box")
    sack = loss_for("gunny_bag")

    assert crate < carton < sack, (
        f"expected crate < carton < sack, got {crate} / {carton} / {sack}"
    )


def test_contract_and_simulator_spellings_agree_on_the_same_object(
    session, make_batch
):
    """`gunny_bag` and `jute_sack` are one sack; `reefer` and `refrigerated`
    one truck. Two names for one thing must not score differently."""
    assert intelligence._resolve_packaging("gunny_bag") == intelligence._resolve_packaging(
        "jute_sack"
    )
    assert intelligence._resolve_packaging(
        "corrugated_box"
    ) == intelligence._resolve_packaging("cfb_carton")
    assert intelligence._resolve_transport("reefer") == intelligence._resolve_transport(
        "refrigerated"
    )


@pytest.mark.parametrize(
    "packaging", ["ventilated_plastic_crate", "gunny_bag", "wooden_crate", "corrugated_box"]
)
def test_event_returns_200_for_every_packaging_the_ui_offers(seeded_db, packaging):
    """The 500 exactly as the UI met it.

    Registers through Contract 2b — `POST /api/batches` is the only way to
    create a batch — then posts the first event, which is what triggers the
    identity layer's re-score. Three of these four values used to raise.
    """
    from fastapi.testclient import TestClient

    from foodos.api.app import app

    client = TestClient(app)
    created = client.post(
        "/api/batches",
        json={
            "commodity": "tomato",
            "qty_kg": 10_000,
            "origin": "Kolar Collection Hub",
            "destination": "Delhi APMC",
            "transport": "open_truck",
            "packaging": packaging,
            "depart_at": "2026-08-10T10:00:00",
            "answers": {},
        },
    )
    assert created.status_code == 201, created.text
    code = created.json()["id"]

    response = client.post(
        f"/api/batches/{code}/events",
        json={"type": "dispatched", "occurred_at": "2026-08-10T10:00:00"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert BatchEventType(body["event"]["type"]) is BatchEventType.DISPATCHED
    assert body["lifecycle"] == "in_transit"
    # The re-score is the step that used to raise, so a returned figure is the
    # actual proof the bug is gone — a 200 alone would pass even if the layer
    # had silently stopped scoring.
    assert body["current"] is not None
    assert body["current"]["rul_hours"] > 0
