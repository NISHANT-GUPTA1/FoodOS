"""The batch identity surface — timeline, custody, splitting, the passport.

**Strictly additive to `routes/batches.py`.** That module owns Contract 2b:
registering a consignment, scoring it, ranking plans, the What-If simulator.
This one owns the questions Contract 2b does not ask — what has happened to
this batch, who has held it, what did we believe at each point, and how does a
retailer holding the crate find out. Not one path is shared between the two.

The division is deliberate rather than incidental. `POST /api/batches`,
`GET /api/batches` and `GET /api/batches/{code}` belong to Contract 2b, are
frozen, and have four frontend screens built against them. Re-declaring any of
them here would shadow the frozen surface with a second opinion depending on
router registration order — the worst kind of bug, because it works locally and
silently changes what C's screens receive.

So the full identity profile lives at `GET /api/batches/{code}/identity`
alongside the Contract 2b profile, not instead of it.

Nothing here computes a number. Routes assemble arguments, call
`engine.batch_identity` or `engine.batch_intelligence`, and project the result.
That is the same rule the eleven kitchen endpoints follow, and it is what makes
"one objective function" a fact about the code rather than a claim on a slide.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from foodos import qr
from foodos.api.batch_schemas import (
    BatchProfileOut,
    BatchRiskOut,
    BatchStateOut,
    ChildOut,
    DriverOut,
    EventIn,
    EventOut,
    EventOutcome,
    FefoOut,
    FefoRowOut,
    HandoffIn,
    HandoffOut,
    PartyOut,
    PassportOut,
    SnapshotOut,
    SplitIn,
    SplitOut,
    TimelineOut,
)
from foodos.api.deps import SessionDep
from foodos.config import settings
from foodos.engine import batch_identity as identity
from foodos.engine import batch_intelligence as intelligence
from foodos.schema.enums import (
    BatchEventType,
    BatchLifecycle,
    MaturityStage,
    PackagingType,
    PartyRole,
    TransportMode,
)
from foodos.schema.tables import (
    BatchAssessment,
    BatchEvent,
    BatchHandoff,
    BatchStateSnapshot,
    Consignment,
    Organization,
    ShipmentJourney,
)

router = APIRouter(prefix="/api", tags=["passport"])


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def _now() -> datetime:
    """The demo clock, as a naive datetime to match the stored columns.

    The demo runs against a pinned date so the same story tells the same way
    every rehearsal; `FOODOS_DEMO_TODAY` moves it. Time-of-day comes from the
    wall clock so a timeline built during a five-minute demo still advances.
    """
    wall = datetime.now(timezone.utc).replace(tzinfo=None)
    return wall.replace(
        year=settings.demo_today.year,
        month=settings.demo_today.month,
        day=settings.demo_today.day,
    )


def _now_for(batch: Consignment) -> datetime:
    """"Now", but never before the batch's own history.

    `FOODOS_DEMO_TODAY` is pinned to the kitchen dataset's date. A batch
    harvested in August therefore has a timeline that runs *ahead* of the
    clock, and defaulting an untimestamped action to the raw clock would file
    it before the dispatch it follows. The replay is ordered by `occurred_at`,
    so that does not merely mislabel the event — it feeds the simulator a
    journey in the wrong order and the numbers stop moving.

    Taking the later of the two is correct under both readings: for a batch
    inside the demo window the clock wins, and for one whose story has already
    run past it, its own last event does.
    """
    latest = max(
        (e.occurred_at for e in batch.events),
        default=batch.harvested_at,
    )
    return max(_now(), latest)


def _get(session: Session, code: str) -> Consignment:
    batch = session.scalars(
        select(Consignment).where(Consignment.code == code)
    ).first()
    if batch is None:
        raise HTTPException(404, f"batch {code} not found")
    _ensure_identity(session, batch)
    return batch


def _ensure_identity(session: Session, batch: Consignment) -> None:
    """Give a consignment an identity if it does not have one yet.

    `routes/batches.py` and `ingest/consignments.py` both create consignments
    without one: they set `status` and the assessment, which is all Contract 2b
    needs, but leave `qty_kg_remaining` at zero and write no events. A batch
    like that would show an empty timeline and no custody chain, and — worse —
    would look to the FEFO queue like a batch with nothing left in it.

    Backfilling here rather than editing their creation path is the whole point
    of keeping the layers separate: the Contract 2b surface stays exactly as
    frozen, and a batch grows an identity the first time anything asks for one.
    Idempotent, and cheap after the first call.
    """
    if batch.events:
        return

    if not batch.qty_kg_remaining:
        batch.qty_kg_remaining = batch.qty_kg
    if not batch.current_location:
        batch.current_location = batch.origin
    if not batch.current_owner:
        org = session.get(Organization, batch.org_id)
        batch.current_owner = org.name if org else "Origin FPO"
    if not batch.current_owner_role:
        batch.current_owner_role = PartyRole.FPO

    identity.apply_event(
        session,
        batch,
        BatchEventType.HARVEST,
        occurred_at=batch.harvested_at,
        location=batch.origin,
    )
    # A batch the Contract 2b endpoint has already scored is past CREATED, and
    # its own `status` says so. Record that as an event rather than inventing
    # a transition, so the ladder and the timeline agree from the first read.
    if BatchLifecycle(batch.status) is BatchLifecycle.ASSESSED:
        batch.status = BatchLifecycle.CREATED
        identity.apply_event(
            session,
            batch,
            BatchEventType.ASSESSED,
            occurred_at=batch.harvested_at,
            location=batch.origin,
        )

    # Having an intelligence profile is what makes a batch dispatchable — the
    # same rule `batch_intelligence.rescore` applies when it does the scoring.
    # `routes/batches.py` scores through its own `_score_batch`, which knows
    # nothing about the lifecycle, so without this a batch registered through
    # Contract 2b would sit at ASSESSED with a full profile and refuse to
    # dispatch: legal ladder, impossible product.
    if batch.risk is not None and BatchLifecycle(batch.status) is BatchLifecycle.ASSESSED:
        batch.status = BatchLifecycle.READY_FOR_DISPATCH

    session.commit()


def _passport_url(code: str) -> str:
    return f"{settings.public_base_url.rstrip('/')}/batch/{code}"


def _qr_url(code: str) -> str:
    return f"/api/batches/{code}/qr.svg"


def _enum_or_400(enum_cls, value, field: str):
    try:
        return enum_cls(str(value).strip().lower())
    except ValueError:
        allowed = ", ".join(sorted(e.value for e in enum_cls))
        raise HTTPException(422, f"{field} must be one of: {allowed}")


def _risk_out(batch: Consignment) -> BatchRiskOut | None:
    risk = batch.risk
    if risk is None:
        return None
    latest = batch.snapshots[-1] if batch.snapshots else None
    return BatchRiskOut(
        loss_pct=risk.loss_pct,
        loss_kg=risk.loss_kg,
        low=risk.low,
        high=risk.high,
        rul_hours=risk.rul_hours,
        level=str(risk.level),
        confidence=str(risk.confidence),
        rul_at_dispatch=(latest.inputs or {}).get("_rul_at_dispatch") if latest else None,
    )


def _state_out(batch: Consignment) -> BatchStateOut:
    return BatchStateOut(
        quality_score=batch.quality_score,
        grade=batch.grade,
        maturity=str(batch.maturity) if batch.maturity else None,
        damage_factor=batch.damage_factor,
        field_heat_hours_over_30c=batch.field_heat_hours_over_30c,
    )


def _event_out(event: BatchEvent) -> EventOut:
    payload = event.payload or {}
    return EventOut(
        id=event.id,
        type=str(event.type),
        occurred_at=event.occurred_at,
        recorded_at=event.created_at,
        location=event.location,
        actor=event.actor,
        actor_role=str(event.actor_role) if event.actor_role else None,
        qty_kg=event.qty_kg,
        payload=payload,
        from_status=str(event.from_status) if event.from_status else None,
        to_status=str(event.to_status) if event.to_status else None,
        inherited=bool(payload.get("inherited")),
    )


def _snapshot_out(snap: BatchStateSnapshot) -> SnapshotOut:
    return SnapshotOut(
        sequence=snap.sequence,
        as_of=snap.as_of,
        reason=snap.reason,
        status=str(snap.status),
        location=snap.location,
        qty_kg=snap.qty_kg,
        quality_score=snap.quality_score,
        loss_pct=snap.loss_pct,
        loss_kg=snap.loss_kg,
        low=snap.low,
        high=snap.high,
        rul_hours=snap.rul_hours,
        level=str(snap.level) if snap.level else None,
        confidence=str(snap.confidence) if snap.confidence else None,
        model_run_id=snap.model_run_id,
        inputs=snap.inputs or {},
    )


def _custody_out(batch: Consignment) -> list[PartyOut]:
    return [PartyOut(**row) for row in identity.custody_chain(batch)]


def _sorted_events(batch: Consignment) -> list[BatchEvent]:
    return sorted(batch.events, key=lambda e: (e.occurred_at, e.id or 0))


def _profile_out(batch: Consignment) -> BatchProfileOut:
    lifecycle = BatchLifecycle(batch.status)
    journey = batch.journey
    risk = batch.risk
    return BatchProfileOut(
        id=batch.code,
        commodity=batch.commodity,
        qty_kg=batch.qty_kg,
        qty_kg_remaining=batch.qty_kg_remaining,
        origin=batch.origin,
        destination=batch.destination,
        harvested_at=batch.harvested_at,
        transport=str(journey.transport) if journey else None,
        packaging=str(journey.packaging) if journey else None,
        state=_state_out(batch),
        risk=_risk_out(batch),
        drivers=[DriverOut(**d) for d in (risk.drivers if risk else [])],
        best_plan_id=risk.best_plan_id if risk else None,
        status=lifecycle.contract_status,
        lifecycle=str(lifecycle),
        is_terminal=lifecycle.is_terminal,
        current_owner=batch.current_owner,
        current_owner_role=str(batch.current_owner_role)
        if batch.current_owner_role
        else None,
        current_location=batch.current_location,
        parent_id=batch.parent.code if batch.parent else None,
        children=[
            ChildOut(
                id=c.code,
                qty_kg=c.qty_kg,
                destination=c.destination,
                status=BatchLifecycle(c.status).contract_status,
                lifecycle=str(c.status),
                rul_hours=c.risk.rul_hours if c.risk else None,
                level=str(c.risk.level) if c.risk else None,
            )
            for c in batch.children
        ],
        custody=_custody_out(batch),
        passport_url=_passport_url(batch.code),
        qr_url=_qr_url(batch.code),
    )


# 2 · Reading
# --------------------------------------------------------------------------

@router.get(
    "/batches/{code}/identity",
    response_model=BatchProfileOut,
    summary="Profile, custody chain and children",
)
def get_identity(code: str, session: SessionDep) -> BatchProfileOut:
    """The Contract 2b profile plus everything the passport layer adds.

    Deliberately *not* mounted at `/batches/{code}` — that is Contract 2b's,
    and two handlers on one path resolve by registration order.
    """
    return _profile_out(_get(session, code))


@router.get(
    "/batches/{code}/timeline", response_model=TimelineOut, summary="Full history"
)
def get_timeline(code: str, session: SessionDep) -> TimelineOut:
    batch = _get(session, code)
    return TimelineOut(
        batch_id=batch.code,
        events=[_event_out(e) for e in _sorted_events(batch)],
        snapshots=[_snapshot_out(s) for s in batch.snapshots],
        custody=_custody_out(batch),
    )


# --------------------------------------------------------------------------
# 3 · Events — where the system becomes proactive
# --------------------------------------------------------------------------


@router.post(
    "/batches/{code}/events",
    response_model=EventOutcome,
    summary="Report an event and re-score",
)
def post_event(code: str, body: EventIn, session: SessionDep) -> EventOutcome:
    """Record something that happened, and recompute if it changed the physics.

    The response carries both the previous and the current risk so the caller
    renders "46 h -> 18 h" without doing arithmetic. Not every event re-scores:
    a change of owner does not move a tomato's temperature, and re-running the
    model on a handoff would make the number move for a reason nobody could
    explain. `rescored` says which happened.
    """
    batch = _get(session, code)
    event_type = _enum_or_400(BatchEventType, body.type, "type")
    previous = _risk_out(batch)

    try:
        event = identity.apply_event(
            session,
            batch,
            event_type,
            occurred_at=body.occurred_at or _now_for(batch),
            location=body.location,
            actor=body.actor,
            actor_role=_enum_or_400(PartyRole, body.actor_role, "actor_role")
            if body.actor_role
            else None,
            qty_kg=body.qty_kg,
            payload=body.payload,
        )
    except identity.LifecycleError as exc:
        # A refused transition is the caller's mistake, not a server fault.
        raise HTTPException(409, str(exc))

    snapshot = None
    if event_type.rescores:
        snapshot = intelligence.rescore(
            session,
            batch,
            as_of=event.occurred_at,
            reason=str(event_type),
        )
        event.snapshot_id = snapshot.id

    session.commit()
    session.refresh(batch)

    lifecycle = BatchLifecycle(batch.status)
    return EventOutcome(
        batch_id=batch.code,
        event=_event_out(event),
        previous=previous,
        current=_risk_out(batch),
        lifecycle=str(lifecycle),
        status=lifecycle.contract_status,
        rescored=snapshot is not None,
        snapshot=_snapshot_out(snapshot) if snapshot else None,
    )


# --------------------------------------------------------------------------
# 4 · Custody
# --------------------------------------------------------------------------


@router.post(
    "/batches/{code}/handoff", response_model=HandoffOut, summary="Change custody"
)
def post_handoff(code: str, body: HandoffIn, session: SessionDep) -> HandoffOut:
    """Hand the batch to the next party. Same batch, same code, new holder."""
    batch = _get(session, code)
    try:
        handoff = identity.hand_over(
            session,
            batch,
            to_party=body.to_party,
            to_role=_enum_or_400(PartyRole, body.to_role, "to_role"),
            occurred_at=body.occurred_at or _now_for(batch),
            location=body.location,
            qty_kg=body.qty_kg,
            note=body.note,
        )
    except identity.LifecycleError as exc:
        raise HTTPException(409, str(exc))
    except ValueError as exc:
        raise HTTPException(422, str(exc))

    session.commit()
    session.refresh(batch)

    rejected = next(
        (
            (e.payload or {}).get("rejected_kg", 0.0)
            for e in reversed(_sorted_events(batch))
            if BatchEventType(e.type) is BatchEventType.HANDOFF
        ),
        0.0,
    )
    return HandoffOut(
        batch_id=batch.code,
        from_party=handoff.from_party,
        from_role=str(handoff.from_role) if handoff.from_role else None,
        to_party=handoff.to_party,
        to_role=str(handoff.to_role),
        occurred_at=handoff.occurred_at,
        location=handoff.location,
        qty_kg=handoff.qty_kg,
        rejected_kg=rejected or 0.0,
        custody=_custody_out(batch),
    )


# --------------------------------------------------------------------------
# 5 · Splitting
# --------------------------------------------------------------------------


@router.post("/batches/{code}/split", response_model=SplitOut, summary="Split a batch")
def post_split(code: str, body: SplitIn, session: SessionDep) -> SplitOut:
    """Divide a batch into children, each independently scored.

    Quantities must sum to what the parent has left. A mismatch is a 422 rather
    than a silent rescale — a split that quietly loses forty kilograms is
    exactly the failure this layer exists to make impossible.
    """
    parent = _get(session, code)
    occurred_at = body.occurred_at or _now_for(parent)

    try:
        children = identity.split(
            session,
            parent,
            [
                identity.Allocation(
                    qty_kg=a.qty_kg,
                    destination=a.destination,
                    owner=a.owner,
                    owner_role=_enum_or_400(PartyRole, a.owner_role, "owner_role")
                    if a.owner_role
                    else None,
                )
                for a in body.allocations
            ],
            occurred_at=occurred_at,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc))

    for child in children:
        intelligence.rescore(session, child, as_of=occurred_at, reason="split")

    session.commit()
    for child in children:
        session.refresh(child)

    return SplitOut(
        parent_id=parent.code, children=[_profile_out(c) for c in children]
    )


# --------------------------------------------------------------------------
# 6 · FEFO
# --------------------------------------------------------------------------


@router.get("/inventory/fefo", response_model=FefoOut, summary="First-Expire-First-Out")
def get_fefo(
    session: SessionDep,
    owner: Annotated[str | None, Query(description="restrict to one holder")] = None,
    commodity: Annotated[str | None, Query()] = None,
) -> FefoOut:
    """The sell-first queue, ordered by remaining life.

    Not received-date order. A batch that arrived this morning after a
    thirty-six hour open-truck haul has less life left than one that arrived
    yesterday in a reefer, and FIFO picks the wrong one every time.
    """
    now = _now()
    rows = list(session.scalars(select(Consignment)))
    # Backfill identity across the whole set, not just the batch someone
    # happened to open. `_ensure_identity` normally fires on a fetch by code,
    # and a queue that skipped every batch nobody had visited would silently
    # report an inventory of one — while looking perfectly healthy.
    for row in rows:
        _ensure_identity(session, row)
    if owner:
        rows = [b for b in rows if (b.current_owner or "").lower() == owner.lower()]
    if commodity:
        rows = [b for b in rows if b.commodity.lower() == commodity.strip().lower()]
    # Terminal batches are history, not inventory.
    rows = [b for b in rows if not BatchLifecycle(b.status).is_terminal]

    ordered = identity.fefo_order(rows, now=now)
    return FefoOut(
        as_of=now,
        rows=[
            FefoRowOut(
                rank=r.rank,
                id=r.code,
                commodity=r.commodity,
                qty_kg=r.qty_kg,
                rul_hours=r.rul_hours,
                expires_at=r.expires_at,
                level=r.level,
                beats_fifo=r.beats_fifo,
            )
            for r in ordered
        ],
        disagreements=sum(1 for r in ordered if r.beats_fifo),
    )


# --------------------------------------------------------------------------
# 7 · The physical bridge — QR and the scan view
# --------------------------------------------------------------------------


@router.get(
    "/batches/{code}/qr.svg",
    summary="QR code for the batch passport",
    response_class=Response,
    responses={200: {"content": {"image/svg+xml": {}}}},
)
def get_qr(
    code: str,
    session: SessionDep,
    scale: Annotated[int, Query(ge=1, le=20)] = 6,
) -> Response:
    """One QR per batch — not one per crate, and certainly not one per tomato.

    The batch is checked to exist before anything is encoded: a QR for a
    nonexistent code would scan perfectly and then 404, which is the most
    confusing possible failure to hit at a mandi gate.
    """
    batch = _get(session, code)
    svg = qr.svg(_passport_url(batch.code), scale=scale)
    return Response(
        content=svg,
        media_type="image/svg+xml",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.get(
    "/batches/{code}/passport", response_model=PassportOut, summary="Public scan view"
)
def get_passport(code: str, session: SessionDep) -> PassportOut:
    """What a scan shows. Deliberately a subset of the profile.

    Anyone holding the crate can scan this, including people with no commercial
    relationship to the seller. So it carries what a holder needs in order to
    handle the produce correctly — condition, remaining life, what to do — and
    none of what a competitor would want: no prices, no plan economics, no
    supplier terms, no candidate-plan matrix.

    Custody is included, because a receiver's first question is "where has this
    been", and that is the entire argument for the layer. Roles and party names
    only; no contact details.
    """
    batch = _get(session, code)
    lifecycle = BatchLifecycle(batch.status)
    risk = batch.risk
    return PassportOut(
        id=batch.code,
        commodity=batch.commodity,
        qty_kg=batch.qty_kg_remaining or batch.qty_kg,
        origin=batch.origin,
        destination=batch.destination,
        harvested_at=batch.harvested_at,
        status=lifecycle.contract_status,
        lifecycle=str(lifecycle),
        state=_state_out(batch),
        risk=_risk_out(batch),
        recommended_action=_handling_advice(batch),
        handle_within_hours=risk.rul_hours if risk else None,
        custody=_custody_out(batch),
        events=[_event_out(e) for e in _sorted_events(batch)],
        qr_url=_qr_url(batch.code),
    )


def _handling_advice(batch: Consignment) -> str:
    """One instruction, in the language of the person holding the crate.

    A retailer does not need the physics. They need to know what to do with
    this batch before the end of the day.
    """
    lifecycle = BatchLifecycle(batch.status)
    if lifecycle.is_terminal:
        return f"Closed — {lifecycle.replace('_', ' ')}"
    risk = batch.risk
    if risk is None:
        return "Awaiting assessment"
    hours = risk.rul_hours
    if hours <= 0:
        return "Do not sell as fresh — route to processing or recovery now"
    if hours < 12:
        return f"Sell first — under {hours:.0f} h of fresh life left"
    if str(risk.level) == "HIGH":
        return f"Prioritise sale within {hours:.0f} h"
    if str(risk.level) == "MEDIUM":
        return f"Sell ahead of newer stock — about {hours:.0f} h left"
    return f"Normal handling — about {hours:.0f} h of life left"
