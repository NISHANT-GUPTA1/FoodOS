"""The batch identity layer — codes, lifecycle, events, custody, splitting.

This module owns the answer to "how does the retailer know these are the same
tomatoes the FPO registered?". Everything here is bookkeeping about a batch's
identity; nothing here predicts anything. The physics lives in
`engine/batch_intelligence.py`, which calls into A's `agri.predict`.

Three rules the whole layer rests on.

**One identity, many holders.** A change of owner is a `BatchHandoff` against
the existing consignment, never a new consignment. If handing over minted a new
code, traceability would end at the first gate — which is exactly how it fails
in the field today, where the mandi's records and the FPO's records cannot be
joined at all.

**Nothing mutates silently.** Every state change goes through `apply_event`,
which appends a `BatchEvent` and returns it. The columns on `Consignment` are a
cache of the newest event, not the record of it.

**Splitting produces children, not replacements.** `TOM-KLR-00124` does not
become three batches; it *has* three children, each carrying `parent_id` and a
suffixed code. The parent row stays queryable forever, which is what lets the
Impact screen say "of the ten tonnes registered at Kolar, this is where it all
went" rather than losing the aggregate at the first split.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from foodos.schema.enums import BatchEventType, BatchLifecycle, PartyRole
from foodos.schema.tables import BatchEvent, BatchHandoff, Consignment

# --------------------------------------------------------------------------
# Codes
# --------------------------------------------------------------------------

#: `TOM-KLR-00124`, and children `TOM-KLR-00124-A`. Anchored, because this
#: string ends up in a URL behind a QR code and a loose pattern there is how a
#: scan endpoint becomes an injection surface.
CODE_RE = re.compile(r"^[A-Z]{2,4}-[A-Z]{2,4}-\d{5}(-[A-Z])?$")

_VOWELS = frozenset("AEIOU")


def commodity_slug(commodity: str) -> str:
    """`tomato` -> `TOM`. The first three letters, which stay readable."""
    letters = re.sub(r"[^A-Za-z]", "", commodity).upper()
    if not letters:
        raise ValueError(f"commodity {commodity!r} has no letters to slug")
    return letters[:3].ljust(3, "X")


def origin_slug(origin: str) -> str:
    """`Kolar Collection Hub` -> `KLR`.

    First letter, then the following consonants — not simply the first three
    letters, and the difference matters. Indian district names collide heavily
    at three characters: Kolar, Kolhapur and Kollam are all `KOL`, and a batch
    code that cannot separate three real mandis is not an identifier. Squeezing
    the vowels gives `KLR`, `KLH`, `KLM`.

    Only the first token is used. "Kolar Collection Hub" and "Kolar Farm Gate"
    are the same place for the purpose of a batch code; the precise location
    lives in `Consignment.origin`, unabbreviated.
    """
    token = re.sub(r"[^A-Za-z]", "", origin.split()[0] if origin.split() else origin)
    if not token:
        raise ValueError(f"origin {origin!r} has no letters to slug")
    token = token.upper()
    slug = token[0] + "".join(c for c in token[1:] if c not in _VOWELS)
    return slug[:3].ljust(3, "X")


def next_code(session: Session, commodity: str, origin: str) -> str:
    """The next free code for this commodity/origin pair.

    The counter is scoped to the prefix rather than global so that the number a
    human reads out loud stays short for years, and so two FPOs registering
    simultaneously in different districts never contend on the same counter.

    Derived by counting existing codes rather than from a sequence table: this
    is a single-writer hackathon database, and a `SELECT max` that is obviously
    correct beats a sequence that needs its own migration. Under real
    concurrency this wants a unique-constraint retry, which the caller gets for
    free from `uq_consignment_code`.
    """
    prefix = f"{commodity_slug(commodity)}-{origin_slug(origin)}-"
    highest = session.scalars(
        select(func.max(Consignment.code)).where(
            Consignment.code.like(f"{prefix}%"),
            # Children carry a suffix and must not advance the parent counter.
            func.length(Consignment.code) == len(prefix) + 5,
        )
    ).first()
    n = int(highest[len(prefix) :]) + 1 if highest else 1
    return f"{prefix}{n:05d}"


def child_code(parent_code: str, index: int) -> str:
    """`TOM-KLR-00124` + 0 -> `TOM-KLR-00124-A`.

    Letters rather than numbers because `-1` beside a five-digit sequence reads
    as part of the sequence when spoken over a phone, which is how a batch code
    gets written down wrong at a mandi gate.
    """
    if index >= 26:
        raise ValueError("a batch cannot be split more than 26 ways in one operation")
    return f"{parent_code}-{chr(ord('A') + index)}"


# --------------------------------------------------------------------------
# Lifecycle
# --------------------------------------------------------------------------

L = BatchLifecycle

#: Legal moves. Declared rather than inferred from the order of the enum,
#: because the interesting transitions are the ones that skip ahead: a batch
#: diverted on the highway never becomes RECEIVED at its original destination,
#: and a load rejected at the gate goes straight to WASTED from ARRIVED.
#:
#: Every non-terminal state can reach WASTED. That is not pessimism — it is the
#: only way the ledger can book a total loss at the moment it happens rather
#: than at the moment someone remembers to close the record.
TRANSITIONS: dict[BatchLifecycle, frozenset[BatchLifecycle]] = {
    L.CREATED: frozenset({L.ASSESSED, L.WASTED}),
    # Re-assessment is a self-loop: new photos, or a corrected questionnaire,
    # land on a batch that is already assessed and must be allowed to.
    L.ASSESSED: frozenset({L.ASSESSED, L.READY_FOR_DISPATCH, L.DIVERTED, L.WASTED}),
    L.READY_FOR_DISPATCH: frozenset(
        {L.ASSESSED, L.IN_TRANSIT, L.DIVERTED, L.WASTED}
    ),
    L.IN_TRANSIT: frozenset({L.ARRIVED, L.DIVERTED, L.WASTED}),
    L.ARRIVED: frozenset({L.RECEIVED, L.DIVERTED, L.WASTED}),
    L.RECEIVED: frozenset(
        {L.IN_INVENTORY, L.SOLD, L.PROCESSED, L.DONATED, L.DIVERTED, L.WASTED}
    ),
    # An onward shipment from a wholesaler to a retailer puts an inventoried
    # batch back on a truck. Without this edge the second leg of the chain
    # would need a new batch id, which is the thing this layer exists to avoid.
    L.IN_INVENTORY: frozenset(
        {L.IN_TRANSIT, L.SOLD, L.PROCESSED, L.DONATED, L.DIVERTED, L.WASTED}
    ),
    L.DIVERTED: frozenset(
        {L.ARRIVED, L.RECEIVED, L.SOLD, L.PROCESSED, L.DONATED, L.WASTED}
    ),
    L.SOLD: frozenset(),
    L.PROCESSED: frozenset(),
    L.DONATED: frozenset(),
    L.WASTED: frozenset(),
}

#: The lifecycle state each event drives the batch to. `None` means the event
#: is informational about a batch that stays where it is — a delay does not
#: move a truck out of IN_TRANSIT, it just makes the arrival worse.
EVENT_TARGET: dict[BatchEventType, BatchLifecycle | None] = {
    BatchEventType.HARVEST: None,
    BatchEventType.FIELD_HOLD: None,
    BatchEventType.PACKED: None,
    BatchEventType.ASSESSED: L.ASSESSED,
    BatchEventType.PHOTOS_ADDED: None,
    BatchEventType.DISPATCHED: L.IN_TRANSIT,
    BatchEventType.DELAY: None,
    BatchEventType.TEMPERATURE_EXPOSURE: None,
    BatchEventType.ARRIVED: L.ARRIVED,
    BatchEventType.HANDOFF: None,
    BatchEventType.RECEIVED: L.RECEIVED,
    BatchEventType.SPLIT: None,
    BatchEventType.DIVERTED: L.DIVERTED,
    BatchEventType.SOLD: L.SOLD,
    BatchEventType.PROCESSED: L.PROCESSED,
    BatchEventType.DONATED: L.DONATED,
    BatchEventType.WASTED: L.WASTED,
}


class LifecycleError(ValueError):
    """An illegal lifecycle move. Surfaces as a 409, never a 500."""


def can_transition(current: BatchLifecycle, target: BatchLifecycle) -> bool:
    return target in TRANSITIONS.get(current, frozenset())


def assert_transition(current: BatchLifecycle, target: BatchLifecycle) -> None:
    """Self-loops are covered by `TRANSITIONS` too: ASSESSED -> ASSESSED is
    declared legal there and ARRIVED -> ARRIVED is not, so a re-assessment is
    accepted and a second arrival report is refused without a special case."""
    if not can_transition(current, target):
        allowed = ", ".join(sorted(TRANSITIONS.get(current, frozenset()))) or "nothing"
        raise LifecycleError(
            f"a batch that is {current} cannot become {target} (allowed: {allowed})"
        )


# --------------------------------------------------------------------------
# Events
# --------------------------------------------------------------------------


def apply_event(
    session: Session,
    batch: Consignment,
    event_type: BatchEventType,
    *,
    occurred_at: datetime,
    location: str | None = None,
    actor: str | None = None,
    actor_role: PartyRole | None = None,
    qty_kg: float | None = None,
    payload: dict | None = None,
) -> BatchEvent:
    """Append one event and move the lifecycle if the event says to.

    The single write path. Callers do not set `Consignment.status` themselves —
    if they did, the timeline and the row would be able to disagree, and the
    timeline is the thing we show a judge.

    Raises `LifecycleError` if the event is illegal from where the batch is.
    Nothing is written when it raises: the event and the status move together
    or not at all.
    """
    current = BatchLifecycle(batch.status)
    target = EVENT_TARGET[event_type]

    if target is not None:
        assert_transition(current, target)

    event = BatchEvent(
        type=event_type,
        occurred_at=occurred_at,
        location=location or batch.current_location,
        actor=actor or batch.current_owner,
        actor_role=actor_role or batch.current_owner_role,
        qty_kg=qty_kg,
        payload=payload or {},
        from_status=current,
        to_status=target or current,
    )
    # Appended to the relationship rather than `session.add`-ed with a raw
    # foreign key. With the FK set by hand, an already-loaded `batch.events`
    # collection never learns about the new row, and the re-score — which
    # replays exactly that collection — silently reads a stale timeline. The
    # symptom is the worst kind: every number simply refuses to move.
    batch.events.append(event)

    if target is not None and target != current:
        batch.status = target
    if location:
        batch.current_location = location

    # A terminal event closes out the remaining mass. WASTED writes it off;
    # the recovery states move it out of this identity and into a channel.
    if target is not None and target.is_terminal:
        batch.qty_kg_remaining = 0.0

    session.flush()
    return event


# --------------------------------------------------------------------------
# Custody
# --------------------------------------------------------------------------


def hand_over(
    session: Session,
    batch: Consignment,
    *,
    to_party: str,
    to_role: PartyRole,
    occurred_at: datetime,
    location: str | None = None,
    qty_kg: float | None = None,
    note: str | None = None,
) -> BatchHandoff:
    """Move custody. Same batch, new holder.

    `qty_kg` defaults to everything still under the identity. Passing less is
    how a partial rejection at a mandi gate is recorded — the receiver accepts
    9,850 of 10,000 kg, and the 150 kg difference is a real loss that has to
    land somewhere rather than evaporating between two ledgers. That shortfall
    is written as a WASTED event against the batch, so the mass balance closes.
    """
    accepted = batch.qty_kg_remaining if qty_kg is None else float(qty_kg)
    if accepted <= 0:
        raise ValueError("a handoff must move a positive quantity")
    if accepted > batch.qty_kg_remaining + 1e-6:
        raise ValueError(
            f"cannot hand over {accepted} kg — only {batch.qty_kg_remaining} kg remains"
        )

    handoff = BatchHandoff(
        from_party=batch.current_owner,
        from_role=batch.current_owner_role,
        to_party=to_party,
        to_role=to_role,
        occurred_at=occurred_at,
        location=location or batch.current_location,
        qty_kg=accepted,
        note=note,
    )
    batch.handoffs.append(handoff)

    shortfall = batch.qty_kg_remaining - accepted

    apply_event(
        session,
        batch,
        BatchEventType.HANDOFF,
        occurred_at=occurred_at,
        location=location,
        actor=to_party,
        actor_role=to_role,
        qty_kg=accepted,
        payload={
            "from_party": handoff.from_party,
            "from_role": str(handoff.from_role) if handoff.from_role else None,
            "to_party": to_party,
            "to_role": str(to_role),
            "rejected_kg": round(shortfall, 2) if shortfall > 1e-6 else 0.0,
        },
    )

    batch.current_owner = to_party
    batch.current_owner_role = to_role
    batch.qty_kg_remaining = accepted

    if shortfall > 1e-6:
        # Written directly rather than through `apply_event`, and this is the
        # one place that is correct: a WASTED *event* here concerns 150 kg of
        # a 10,000 kg load, but the WASTED *lifecycle state* means the whole
        # batch is gone. Routing a partial rejection through the normal path
        # would zero the batch that was just accepted.
        batch.events.append(
            BatchEvent(
                type=BatchEventType.WASTED,
                occurred_at=occurred_at,
                location=location or batch.current_location,
                actor=to_party,
                actor_role=to_role,
                qty_kg=round(shortfall, 2),
                payload={"reason": "rejected_at_handoff"},
                from_status=BatchLifecycle(batch.status),
                to_status=BatchLifecycle(batch.status),
            )
        )

    session.flush()
    return handoff


def custody_chain(batch: Consignment) -> list[dict]:
    """The ordered list of holders, origin first. Read-only projection."""
    chain: list[dict] = []
    first = batch.handoffs[0] if batch.handoffs else None
    origin_party = first.from_party if first else batch.current_owner
    origin_role = first.from_role if first else batch.current_owner_role
    if origin_party:
        chain.append(
            {
                "party": origin_party,
                "role": str(origin_role) if origin_role else None,
                "since": batch.harvested_at.isoformat(),
                "location": batch.origin,
                "qty_kg": batch.qty_kg,
            }
        )
    for h in batch.handoffs:
        chain.append(
            {
                "party": h.to_party,
                "role": str(h.to_role),
                "since": h.occurred_at.isoformat(),
                "location": h.location,
                "qty_kg": h.qty_kg,
            }
        )
    return chain


# --------------------------------------------------------------------------
# Splitting
# --------------------------------------------------------------------------


def _inherit_history(
    session: Session, parent: Consignment, child: Consignment, *, until: datetime
) -> None:
    """Copy the parent's journey and timeline onto a freshly split child.

    Copied, not shared by reference. The child's history diverges from this
    moment on — it gets its own onward dispatch, its own delays — and a shared
    row would rewrite the parent's past every time a child moved.

    Events are stamped `inherited: true` in their payload so a passport can
    render "this is what happened before the split" differently from what the
    holder of this child did themselves. Both belong on the timeline; only one
    of them is theirs.
    """
    from foodos.schema.tables import ShipmentJourney, WeatherExposure

    if parent.journey is not None and child.journey is None:
        j = parent.journey
        child.journey = ShipmentJourney(
            transport=j.transport,
            packaging=j.packaging,
            depart_at=j.depart_at,
            distance_km=j.distance_km,
            transit_hours=j.transit_hours,
            road_quality=j.road_quality,
            vibration_index=j.vibration_index,
            route_source=j.route_source,
        )

    if parent.weather and not child.weather:
        for w in parent.weather:
            child.weather.append(
                WeatherExposure(
                    hour_offset=w.hour_offset,
                    temp_c=w.temp_c,
                    rh=w.rh,
                    solar=w.solar,
                    source=w.source,
                )
            )

    for event in sorted(parent.events, key=lambda e: (e.occurred_at, e.id or 0)):
        if event.occurred_at > until:
            continue
        # The parent's SPLIT event names every sibling. Copying it onto one
        # child would have that child's passport claim it was split into its
        # own siblings, which is nonsense — the split is recorded once, on the
        # parent, and the child's link back is `parent_id`.
        if BatchEventType(event.type) is BatchEventType.SPLIT:
            continue
        child.events.append(
            BatchEvent(
                type=event.type,
                occurred_at=event.occurred_at,
                location=event.location,
                actor=event.actor,
                actor_role=event.actor_role,
                # Quantities on an inherited event describe the parent's mass,
                # not this child's share. Dropping the figure is honest;
                # rescaling it would invent a per-child history that never
                # happened.
                qty_kg=None,
                payload={**(event.payload or {}), "inherited": True},
                from_status=event.from_status,
                to_status=event.to_status,
            )
        )


@dataclass(frozen=True)
class Allocation:
    """One destination for part of a batch."""

    qty_kg: float
    destination: str
    owner: str | None = None
    owner_role: PartyRole | None = None


def split(
    session: Session,
    parent: Consignment,
    allocations: Sequence[Allocation],
    *,
    occurred_at: datetime,
) -> list[Consignment]:
    """Divide a batch into children. The parent keeps its identity.

    The children inherit the parent's origin, harvest time and commodity
    verbatim, because those are facts about the produce and do not change when
    it is divided. They also inherit its **history** — the journey record and
    every event up to the split — because three tonnes that have already spent
    forty hours on an open truck are not fresh produce, and a child scored
    without that past would come out looking better than the parent it was cut
    from. That is not a cosmetic difference: it is the whole loss story
    disappearing at the moment the batch is divided.

    What they do not inherit is the risk *score*. Three tonnes going to a
    processor two hours away and four tonnes going to a retailer in Delhi have
    different futures from the moment they part, so each child is re-scored
    against its own onward journey by `batch_intelligence.rescore`.

    Quantities must sum to what the parent has left. A tolerance of 1 g absorbs
    float noise from a percentage split; anything larger is a real mismatch and
    is refused rather than silently rescaled, because a split that quietly
    loses 40 kg is the exact failure this layer is supposed to make impossible.
    """
    if not allocations:
        raise ValueError("a split needs at least one allocation")
    if parent.parent_id is not None:
        raise ValueError(
            f"{parent.code} is already a child batch — split the parent instead"
        )

    total = sum(a.qty_kg for a in allocations)
    if abs(total - parent.qty_kg_remaining) > 1e-3:
        raise ValueError(
            f"allocations sum to {total:g} kg but {parent.code} has "
            f"{parent.qty_kg_remaining:g} kg remaining"
        )
    if any(a.qty_kg <= 0 for a in allocations):
        raise ValueError("every allocation must be a positive quantity")

    existing = len(parent.children)
    children: list[Consignment] = []

    for offset, alloc in enumerate(allocations):
        child = Consignment(
            code=child_code(parent.code, existing + offset),
            org_id=parent.org_id,
            commodity=parent.commodity,
            qty_kg=alloc.qty_kg,
            qty_kg_remaining=alloc.qty_kg,
            origin=parent.origin,
            destination=alloc.destination,
            harvested_at=parent.harvested_at,
            status=parent.status,
            current_owner=alloc.owner or parent.current_owner,
            current_owner_role=alloc.owner_role or parent.current_owner_role,
            current_location=parent.current_location,
            # The child starts from the parent's assessed condition — same
            # field heat, same maturity, same damage. Only the journey ahead
            # differs, which is what the re-score picks up.
            quality_score=parent.quality_score,
            grade=parent.grade,
            maturity=parent.maturity,
            damage_factor=parent.damage_factor,
            field_heat_hours_over_30c=parent.field_heat_hours_over_30c,
        )
        parent.children.append(child)
        children.append(child)

    session.flush()

    for child in children:
        _inherit_history(session, parent, child, until=occurred_at)

    session.flush()

    apply_event(
        session,
        parent,
        BatchEventType.SPLIT,
        occurred_at=occurred_at,
        qty_kg=total,
        payload={
            "children": [
                {"code": c.code, "qty_kg": c.qty_kg, "destination": c.destination}
                for c in children
            ]
        },
    )

    # The mass now lives in the children. The parent row stays queryable — it
    # is what the whole chain rolls up to — but it no longer holds anything.
    parent.qty_kg_remaining = 0.0
    session.flush()
    return children


# --------------------------------------------------------------------------
# FEFO
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class FefoRow:
    """One line of a First-Expire-First-Out queue."""

    code: str
    commodity: str
    qty_kg: float
    rul_hours: float | None
    expires_at: datetime | None
    level: str | None
    rank: int
    #: True when FIFO and FEFO disagree on this row. The interesting case, and
    #: the one worth showing: it is precisely where received-order picking
    #: throws away food that a life-ordered pick would have sold.
    beats_fifo: bool


def fefo_order(
    batches: Iterable[Consignment], *, now: datetime
) -> list[FefoRow]:
    """Order inventory by remaining life, soonest first.

    Not received-date order. A batch that arrived this morning after a
    thirty-six hour open-truck haul in August has less life left than one that
    arrived yesterday in a reefer, and FIFO will pick the wrong one every time.

    Batches with no score sort last rather than first. An unscored row is an
    unknown, and putting unknowns at the head of the queue would have the
    system confidently telling a retailer to sell the one thing it knows
    nothing about.
    """
    rows = [b for b in batches if b.qty_kg_remaining > 0]

    # FIFO reference order: oldest harvest first, which is what a receiving
    # clerk does today.
    fifo = {b.code: i for i, b in enumerate(sorted(rows, key=lambda b: b.harvested_at))}

    def life(b: Consignment) -> float:
        risk = b.risk
        if risk is None or risk.rul_hours is None:
            return float("inf")
        # RUL was computed as of the newest snapshot; burn down the clock since.
        latest = b.snapshots[-1] if b.snapshots else None
        as_of = latest.as_of if latest else b.harvested_at
        elapsed = max((now - as_of).total_seconds() / 3600.0, 0.0)
        return max(risk.rul_hours - elapsed, 0.0)

    ordered = sorted(rows, key=lambda b: (life(b), b.harvested_at))

    out: list[FefoRow] = []
    for rank, b in enumerate(ordered):
        remaining = life(b)
        finite = remaining != float("inf")
        out.append(
            FefoRow(
                code=b.code,
                commodity=b.commodity,
                qty_kg=b.qty_kg_remaining,
                rul_hours=round(remaining, 1) if finite else None,
                expires_at=now + timedelta(hours=remaining) if finite else None,
                level=str(b.risk.level) if b.risk else None,
                rank=rank,
                beats_fifo=fifo[b.code] != rank,
            )
        )
    return out
