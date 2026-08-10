"""The receiving gate — where a tracked batch becomes stock in a track.

Additive, and shares no path with anything already frozen. `routes/batches.py`
owns Contract 2b (register, score, rank, simulate); `routes/passport.py` owns
identity inside the agri node (timeline, custody, split, QR). This module owns
the one step neither of them covers: taking the crate into a kitchen, store or
plant, and carrying everything known about it across with the code intact.

Two endpoints, because there are exactly two questions:

    POST /api/batches/{code}/receive    take it into stock here
    GET  /api/batches/{code}/lots       where did this code end up?

Nothing here computes a number. The route resolves a site and a SKU, calls
`engine.intake`, and projects the result — the same rule the eleven kitchen
endpoints and the passport surface both follow.

The helpers for "find the batch" and "what time is it" are imported from
`routes/passport.py` rather than restated. `_ensure_identity` in particular
backfills an identity onto consignments that Contract 2b created without one,
and a second copy of that logic would be free to disagree with the first about
the same batch — which is precisely the class of bug this whole layer exists
to remove.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from foodos.api.deps import SessionDep, resolve_site
from foodos.api.routes.passport import _get, _now_for
from foodos.engine import batch_identity as identity
from foodos.engine import intake
from foodos.schema.enums import BatchLifecycle, PartyRole, SiteType
from foodos.schema.tables import Batch, Product, Site, StorageZone

router = APIRouter(prefix="/api", tags=["intake"])


# --------------------------------------------------------------------------
# Bodies and responses
# --------------------------------------------------------------------------


class ReceiveIn(BaseModel):
    """Who is taking it, where, and how much of it they accept."""

    to_party: str = Field(description="Who is accepting the load")
    to_role: str = PartyRole.RETAILER.value

    #: Defaults to the first site of `site_type`, then to the first site at
    #: all. A's dataset is a single kitchen, so demanding a real store id would
    #: make the one endpoint that proves the cross-track claim the one endpoint
    #: that 404s on the shipped database.
    site_id: int | None = None
    site_type: str | None = None
    storage_zone_id: int | None = None

    #: The SKU to stock it under. Omitted, the commodity resolves to one and
    #: opens it if the site has never received this commodity before.
    product_sku: str | None = None

    #: Less than what was shipped is a partial acceptance: the shortfall is
    #: booked as waste against the batch rather than vanishing between the two
    #: ledgers. Omitted means "all of it".
    qty_kg: float | None = None

    occurred_at: datetime | None = None
    note: str | None = None


class InheritedOut(BaseModel):
    """What the lot arrived carrying. The payload of the handover."""

    code: str
    commodity: str
    origin: str
    destination: str
    harvested_at: str
    received_at: str
    qty_registered_kg: float
    qty_received_kg: float
    upstream_loss_pct: float
    rul_hours: float
    rul_at_dispatch: float | None
    age_hours: float
    life_used: float
    quality_score: float | None
    grade: str | None
    level: str | None
    confidence: str | None
    hops: int
    custody: list[str]
    basis: str
    model_run_id: str | None


class LotOut(BaseModel):
    """A lot as the receiving track now holds it."""

    lot_id: int
    lot_code: str
    batch_code: str | None
    site_id: int
    site: str
    track: str
    product_id: int
    product: str
    qty_kg: float
    uom: str
    #: Written from the inherited RUL, not from a shelf-life table.
    rsl_days: float | None
    life_used: float | None
    intake_grade: float
    printed_expiry: str | None
    rsl_explanation: str | None
    inherited: InheritedOut | None


class ReceiptOut(BaseModel):
    batch_id: str
    #: Contract 2b's four-value spelling, so a screen that only knows those
    #: words can render this response without learning the fuller ladder.
    status: str
    lifecycle: str
    accepted_kg: float
    rejected_kg: float
    custody: list[str]
    lot: LotOut


class LotsOut(BaseModel):
    batch_id: str
    #: Every track this code reached. A split sends children to different
    #: destinations, so one code legitimately lands in more than one.
    tracks: list[str]
    total_received_kg: float
    lots: list[LotOut]


# --------------------------------------------------------------------------
# Projection
# --------------------------------------------------------------------------


def _lot_out(session, lot: Batch) -> LotOut:
    site = session.get(Site, lot.site_id)
    product = session.get(Product, lot.product_id)
    inherited = lot.inherited or None
    return LotOut(
        lot_id=lot.id,
        lot_code=lot.lot_code,
        batch_code=lot.batch_code,
        site_id=lot.site_id,
        site=site.name if site else "",
        track=str(intake.track_for(site)) if site else "",
        product_id=lot.product_id,
        product=product.name if product else "",
        qty_kg=lot.qty_remaining,
        uom=lot.uom,
        rsl_days=lot.rsl_days,
        life_used=lot.life_used,
        intake_grade=lot.intake_grade,
        printed_expiry=lot.printed_expiry.isoformat() if lot.printed_expiry else None,
        rsl_explanation=lot.rsl_explanation,
        inherited=InheritedOut(**inherited) if inherited else None,
    )


def _resolve_site(session, body: ReceiveIn) -> Site:
    """The site taking delivery.

    An explicit `site_id` wins. A `site_type` picks the first site of that
    kind, which is how "receive this into a store" works on a dataset that has
    one. Neither given falls back to the first site — see `ReceiveIn.site_id`
    for why that fallback is deliberate rather than lazy.
    """
    if body.site_id is not None:
        return resolve_site(session, body.site_id)

    if body.site_type:
        try:
            wanted = SiteType(body.site_type.strip().lower())
        except ValueError:
            allowed = ", ".join(sorted(e.value for e in SiteType))
            raise HTTPException(422, f"site_type must be one of: {allowed}")
        found = session.scalars(
            select(Site).where(Site.type == wanted).order_by(Site.id).limit(1)
        ).first()
        if found is not None:
            return found

    return resolve_site(session, None)


# --------------------------------------------------------------------------
# 1 · Receive
# --------------------------------------------------------------------------


@router.post(
    "/batches/{code}/receive",
    response_model=ReceiptOut,
    summary="Receive a tracked batch into a track",
)
def post_receive(code: str, body: ReceiveIn, session: SessionDep) -> ReceiptOut:
    """Take the crate into stock, carrying the identity across with it.

    This is the step where the two halves of the product meet. Before it, the
    batch is a consignment with a passport and no stock record; after it, it is
    a lot in a Ledger that still knows it spent forty hours on an open truck.
    The code does not change, which is the whole claim.

    409 when the batch is not in a state that can be received — a load that was
    never dispatched, or one already taken in. 422 for a quantity larger than
    what is left under the identity.
    """
    batch = _get(session, code)
    site = _resolve_site(session, body)
    as_of = body.occurred_at or _now_for(batch)

    product = None
    if body.product_sku:
        product = session.scalars(
            select(Product).where(
                Product.org_id == site.org_id, Product.sku == body.product_sku
            )
        ).first()
        if product is None:
            raise HTTPException(404, f"no product {body.product_sku} at {site.name}")

    zone = None
    if body.storage_zone_id is not None:
        zone = session.get(StorageZone, body.storage_zone_id)
        if zone is None or zone.site_id != site.id:
            raise HTTPException(404, f"no storage zone {body.storage_zone_id} at {site.name}")

    shipped = batch.qty_kg_remaining

    try:
        lot, carried = intake.receive_into_track(
            session,
            batch,
            site=site,
            as_of=as_of,
            to_party=body.to_party,
            to_role=_role_or_422(body.to_role),
            qty_kg=body.qty_kg,
            product=product,
            storage_zone=zone,
            note=body.note,
        )
    except identity.LifecycleError as exc:
        session.rollback()
        raise HTTPException(409, str(exc))
    except ValueError as exc:
        session.rollback()
        raise HTTPException(422, str(exc))

    session.commit()
    session.refresh(batch)
    session.refresh(lot)

    # Re-wrapped rather than used directly: the column is a plain `String`, so
    # a refreshed row hands back the raw value and not the enum member.
    lifecycle = BatchLifecycle(batch.status)

    return ReceiptOut(
        batch_id=batch.code,
        status=lifecycle.contract_status,
        lifecycle=str(lifecycle),
        accepted_kg=round(carried.qty_received_kg, 2),
        rejected_kg=round(max(shipped - carried.qty_received_kg, 0.0), 2),
        custody=carried.custody,
        lot=_lot_out(session, lot),
    )


def _role_or_422(value: str) -> PartyRole:
    try:
        return PartyRole(str(value).strip().lower())
    except ValueError:
        allowed = ", ".join(sorted(e.value for e in PartyRole))
        raise HTTPException(422, f"to_role must be one of: {allowed}")


# --------------------------------------------------------------------------
# 2 · Where did it end up
# --------------------------------------------------------------------------


@router.get(
    "/batches/{code}/lots",
    response_model=LotsOut,
    summary="Downstream lots for a batch code",
)
def get_lots(code: str, session: SessionDep) -> LotsOut:
    """Every lot this code became, across every site and track.

    The other direction of the join `POST /receive` creates, and the thing that
    makes the claim checkable rather than asserted: hand a judge a code from a
    crate and this says which kitchen, store or plant is holding it now.

    An empty list is a normal answer, not an error. Most batches are still on
    the road.
    """
    batch = _get(session, code)
    lots = [_lot_out(session, lot) for lot in intake.lots_for(session, batch.code)]
    return LotsOut(
        batch_id=batch.code,
        tracks=sorted({lot.track for lot in lots if lot.track}),
        total_received_kg=round(sum(lot.qty_kg for lot in lots), 2),
        lots=lots,
    )
