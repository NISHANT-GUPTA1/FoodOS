"""Fixtures for the batch identity layer.

Builds consignments directly rather than going through `ingest/batch_seed.py`:
a test that fails should point at the code under test, not at the seed's
opinion about what a demo batch looks like.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from foodos.engine import batch_identity as identity
from foodos.schema.enums import (
    BatchEventType,
    BatchLifecycle,
    MaturityStage,
    PackagingType,
    PartyRole,
    TransportMode,
)
from foodos.schema.tables import Consignment, Organization, ShipmentJourney

HARVEST = datetime(2026, 8, 10, 5, 0)


@pytest.fixture
def org(session) -> Organization:
    return session.scalars(select(Organization).order_by(Organization.id)).first()


@pytest.fixture
def make_batch(session, org):
    """Factory: a registered consignment with a journey, no events yet."""

    def _make(
        *,
        commodity: str = "tomato",
        qty_kg: float = 10_000,
        origin: str = "Kolar Collection Hub",
        destination: str = "Delhi APMC",
        harvested_at: datetime = HARVEST,
        transit_hours: float = 36.0,
        maturity: MaturityStage = MaturityStage.MEDIUM,
        transport: TransportMode = TransportMode.OPEN_TRUCK,
        status: BatchLifecycle = BatchLifecycle.CREATED,
    ) -> Consignment:
        batch = Consignment(
            code=identity.next_code(session, commodity, origin),
            org_id=org.id,
            commodity=commodity,
            qty_kg=qty_kg,
            qty_kg_remaining=qty_kg,
            origin=origin,
            destination=destination,
            harvested_at=harvested_at,
            status=status,
            current_owner="Kolar FPO",
            current_owner_role=PartyRole.FPO,
            current_location=origin,
            maturity=maturity,
            damage_factor="low",
            field_heat_hours_over_30c=2.5,
        )
        session.add(batch)
        session.flush()
        batch.journey = ShipmentJourney(
            transport=transport,
            packaging=PackagingType.VENTILATED_PLASTIC_CRATE,
            depart_at=harvested_at + timedelta(hours=5),
            distance_km=2150.0,
            transit_hours=transit_hours,
        )
        session.flush()
        return batch

    return _make


@pytest.fixture
def in_transit(session, make_batch):
    """A batch already on the road — the state most events are legal from."""
    batch = make_batch()
    identity.apply_event(
        session, batch, BatchEventType.ASSESSED, occurred_at=HARVEST + timedelta(hours=1)
    )
    batch.status = BatchLifecycle.READY_FOR_DISPATCH
    identity.apply_event(
        session, batch, BatchEventType.DISPATCHED, occurred_at=HARVEST + timedelta(hours=5)
    )
    return batch
