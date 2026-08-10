"""Pydantic models for the batch identity surface.

A separate module from `api/schemas.py` because that file is the frozen
kitchen contract and this is additive to it. Contract 2b's `GET /api/batches`
and `GET /api/batches/{id}` shapes are reproduced here field for field — C is
already building against them — and everything the passport adds is a *new*
key alongside, never a change to an existing one.

The `status` / `lifecycle` pair is the one place worth reading carefully.
`status` is Contract 2b's four frozen values and keeps its exact old meaning;
`lifecycle` is the full eleven-state ladder. A client that ignores `lifecycle`
sees precisely what it saw before.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------- shared


class BatchStateOut(BaseModel):
    """Contract 2b `state`. Any field may be null before assessment."""

    quality_score: float | None = None
    grade: str | None = None
    maturity: str | None = None
    damage_factor: str | None = None
    field_heat_hours_over_30c: float | None = None


class BatchRiskOut(BaseModel):
    """Contract 2b `risk`.

    `low`/`high` null means the row was scored by the deterministic fallback
    rather than by A's model — render the point estimate and say so, never
    fabricate a band around it.
    """

    loss_pct: float
    loss_kg: float
    low: float | None = None
    high: float | None = None
    rul_hours: float
    level: str
    confidence: str
    #: Life the batch had when it left the farm gate. `rul_hours` is what is
    #: left now; the two differ by the time already spent on the road.
    rul_at_dispatch: float | None = None


class DriverOut(BaseModel):
    name: str
    label: str = ""
    contribution: float = 0.0
    loss_reduction_pp: float = 0.0
    mass_saved_kg: float = 0.0
    controllable: bool = False
    current: str = ""
    counterfactual: str = ""
    text: str = ""


# ---------------------------------------------------------------- identity


class PartyOut(BaseModel):
    party: str
    role: str | None = None
    since: str
    location: str | None = None
    qty_kg: float | None = None


class EventOut(BaseModel):
    id: int
    type: str
    #: When it happened in the world.
    occurred_at: datetime
    #: When FoodOS was told. Later than `occurred_at` whenever a delay is
    #: reported from inside the delay; a timeline that conflates them shows the
    #: batch reacting before its cause.
    recorded_at: datetime
    location: str | None = None
    actor: str | None = None
    actor_role: str | None = None
    qty_kg: float | None = None
    payload: dict = Field(default_factory=dict)
    from_status: str | None = None
    to_status: str | None = None
    #: True when this event was copied from the parent at a split — history the
    #: current holder inherited rather than caused.
    inherited: bool = False


class SnapshotOut(BaseModel):
    sequence: int
    as_of: datetime
    reason: str
    status: str
    location: str | None = None
    qty_kg: float
    quality_score: float | None = None
    loss_pct: float | None = None
    loss_kg: float | None = None
    low: float | None = None
    high: float | None = None
    rul_hours: float | None = None
    level: str | None = None
    confidence: str | None = None
    #: Null on a fallback-scored snapshot. The tell, kept per snapshot so a
    #: passport can say which of its own entries were modelled.
    model_run_id: str | None = None
    #: The exact input dict handed to the simulator, so any figure on the
    #: timeline can be replayed rather than taken on trust.
    inputs: dict = Field(default_factory=dict)


class ChildOut(BaseModel):
    id: str
    qty_kg: float
    destination: str
    status: str
    lifecycle: str
    rul_hours: float | None = None
    level: str | None = None


# ---------------------------------------------------------------- profile


class BatchProfileOut(BaseModel):
    """`GET /api/batches/{id}` — Contract 2b's Batch Profile, plus identity."""

    id: str
    commodity: str
    qty_kg: float
    #: What is still under this identity. Below `qty_kg` after a rejection at a
    #: gate, and zero once the batch has been split into children.
    qty_kg_remaining: float
    origin: str
    destination: str
    harvested_at: datetime
    transport: str | None = None
    packaging: str | None = None

    state: BatchStateOut
    risk: BatchRiskOut | None = None
    drivers: list[DriverOut] = Field(default_factory=list)
    best_plan_id: int | None = None

    # --- identity, all additive ------------------------------------------
    status: str          # Contract 2b's four values, unchanged
    lifecycle: str       # the full ladder
    is_terminal: bool
    current_owner: str | None = None
    current_owner_role: str | None = None
    current_location: str | None = None
    parent_id: str | None = None
    children: list[ChildOut] = Field(default_factory=list)
    custody: list[PartyOut] = Field(default_factory=list)
    #: Absolute URL the QR code resolves to.
    passport_url: str
    qr_url: str


class BatchListRowOut(BaseModel):
    """Contract 2b's Command Center row, plus lifecycle and custody."""

    id: str
    commodity: str
    qty_kg: float
    qty_kg_remaining: float
    origin: str
    destination: str
    rul_hours: float
    loss_pct: float
    loss_kg: float
    level: str
    status: str
    lifecycle: str
    current_owner: str | None = None
    parent_id: str | None = None
    best_action: str = ""
    best_plan_id: int | None = None
    delta_vs_baseline: float = 0.0


class BatchListOut(BaseModel):
    batches: list[BatchListRowOut]
    counts: dict[str, int]
    source: str = "snapshot"
    as_of: datetime


class TimelineOut(BaseModel):
    batch_id: str
    events: list[EventOut]
    snapshots: list[SnapshotOut]
    custody: list[PartyOut]


class PassportOut(BaseModel):
    """The scan view. Deliberately a subset — see the note on the route."""

    id: str
    commodity: str
    qty_kg: float
    origin: str
    destination: str
    harvested_at: datetime
    status: str
    lifecycle: str
    state: BatchStateOut
    risk: BatchRiskOut | None = None
    recommended_action: str
    handle_within_hours: float | None = None
    custody: list[PartyOut] = Field(default_factory=list)
    events: list[EventOut] = Field(default_factory=list)
    qr_url: str


# ---------------------------------------------------------------- requests


class CreateBatchIn(BaseModel):
    commodity: str = "tomato"
    qty_kg: float = Field(gt=0)
    origin: str
    destination: str
    harvested_at: datetime
    owner: str | None = None
    owner_role: str | None = None
    location: str | None = None

    maturity: str | None = None
    damage_factor: str | None = None
    field_heat_hours_over_30c: float | None = None

    transport: str | None = None
    packaging: str | None = None
    depart_at: datetime | None = None
    transit_hours: float | None = None
    distance_km: float | None = None

    #: D's questionnaire answers, keyed by `feature_key`. Free-form on purpose:
    #: adding a question is a content change, not a migration.
    answers: dict = Field(default_factory=dict)


class CreateBatchOut(BaseModel):
    id: str
    status: str
    lifecycle: str
    passport_url: str
    qr_url: str
    risk: BatchRiskOut | None = None


class EventIn(BaseModel):
    type: str
    occurred_at: datetime | None = None
    location: str | None = None
    actor: str | None = None
    actor_role: str | None = None
    qty_kg: float | None = None
    payload: dict = Field(default_factory=dict)

    @field_validator("type")
    @classmethod
    def _lower(cls, v: str) -> str:
        return v.strip().lower()


class EventOutcome(BaseModel):
    """What the event did. The before/after pair is the point of the endpoint.

    A client renders "46 h -> 18 h" straight from `previous` and `current`
    without arithmetic — rule 1 of the road, and the reason both are returned
    rather than just the new figure.
    """

    batch_id: str
    event: EventOut
    previous: BatchRiskOut | None = None
    current: BatchRiskOut | None = None
    lifecycle: str
    status: str
    rescored: bool
    snapshot: SnapshotOut | None = None


class HandoffIn(BaseModel):
    to_party: str
    to_role: str
    occurred_at: datetime | None = None
    location: str | None = None
    #: Less than the batch's remaining mass records a partial rejection at the
    #: gate; the shortfall is booked as waste against the batch.
    qty_kg: float | None = None
    note: str | None = None


class HandoffOut(BaseModel):
    batch_id: str
    from_party: str | None = None
    from_role: str | None = None
    to_party: str
    to_role: str
    occurred_at: datetime
    location: str | None = None
    qty_kg: float
    rejected_kg: float = 0.0
    custody: list[PartyOut] = Field(default_factory=list)


class AllocationIn(BaseModel):
    qty_kg: float = Field(gt=0)
    destination: str
    owner: str | None = None
    owner_role: str | None = None


class SplitIn(BaseModel):
    allocations: list[AllocationIn] = Field(min_length=1)
    occurred_at: datetime | None = None


class SplitOut(BaseModel):
    parent_id: str
    children: list[BatchProfileOut]


class FefoRowOut(BaseModel):
    rank: int
    id: str
    commodity: str
    qty_kg: float
    rul_hours: float | None = None
    expires_at: datetime | None = None
    level: str | None = None
    #: True where life-ordered picking disagrees with received-date ordering.
    #: The interesting rows: exactly where FIFO throws food away.
    beats_fifo: bool = False


class FefoOut(BaseModel):
    as_of: datetime
    rows: list[FefoRowOut]
    #: How many rows FEFO orders differently from FIFO. Zero is a legitimate
    #: answer and should be shown as such, not hidden.
    disagreements: int = 0
