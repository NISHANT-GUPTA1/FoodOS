"""Pydantic DTOs — the wire format.

These are the frozen contract. contracts/api-contract.md is generated from this file and
the routers, so the two cannot drift. If a field name changes here, the frontend breaks
loudly at the fixture diff rather than quietly at runtime.

Owner: Person B.
"""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict, Field


class Dto(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


# --- shared -----------------------------------------------------------------

class Saving(Dto):
    """What an action is worth, in the three units that appear on every card."""

    kg: float = Field(description="kilograms of food not wasted")
    inr: float = Field(description="rupees kept, net of the disposal baseline")
    co2e_kg: float = Field(description="kilograms of CO2e avoided")


class WhyLine(Dto):
    """One line of the WHY block. Always a fact, never a sentence the model invented."""

    label: str
    value: str
    kind: str = "fact"  # fact | evidence | tradeoff


class RecommendationDto(Dto):
    id: str
    horizon: str
    action_kind: str
    title: str
    subject_id: str
    subject_name: str
    current_qty: float | None = None
    recommended_qty: float | None = None
    qty_unit: str = "portions"
    saves: Saving
    confidence: float
    why: list[WhyLine]
    expires_at: dt.datetime
    status: str
    channel_id: str | None = None
    lambda_used: float


# --- /api/today -------------------------------------------------------------

class TodayKpis(Dto):
    kg_at_risk: float
    value_at_risk_inr: float
    preventable_pct: float


class TodayResponse(Dto):
    date: dt.date
    outlet_name: str
    lambda_used: float
    kpis: TodayKpis
    recommendations: list[RecommendationDto]


# --- /api/why ---------------------------------------------------------------

class Contributor(Dto):
    key: str
    name: str
    share: float = Field(description="percent of value at risk, 0-100")
    value_inr: float
    kg: float
    evidence: str


class TrimCallout(Dto):
    trim_kg: float
    trim_value_inr: float
    worst_ingredient: str
    worst_ingredient_yield: float


class WhyResponse(Dto):
    date: dt.date
    value_at_risk_inr: float
    kg_at_risk: float
    worst_dish: str
    worst_dish_name: str
    contributors: list[Contributor]
    trim: TrimCallout
    root_cause: str | None = Field(
        default=None,
        description="One sentence from the Diagnostician agent. Null when the Verifier blocked it.",
    )
    root_cause_verified: bool = True


# --- /api/plan --------------------------------------------------------------

class PlanLine(Dto):
    dish_id: str
    dish_name: str
    station: str | None = None
    current_qty: float
    recommended_qty: float
    delta: float
    service_level: float = Field(description="the newsvendor critical ratio q* used")
    saving_inr: float
    saving_kg: float
    saving_co2e_kg: float


class PlanTotals(Dto):
    portions_delta: float
    saving_inr: float
    saving_kg: float
    saving_co2e_kg: float


class PlanResponse(Dto):
    date: dt.date
    lambda_used: float
    lines: list[PlanLine]
    totals: PlanTotals


# --- /api/ledger ------------------------------------------------------------

class LedgerRow(Dto):
    batch_id: str
    product_id: str
    product_name: str
    zone_id: str
    zone_name: str
    zone_running_warm: bool
    qty_kg: float
    state: str
    rsl_days: float
    risk_pct: float
    value_at_risk_inr: float
    recommended_action: str
    severity: str  # critical | warning | fine


class LedgerResponse(Dto):
    date: dt.date
    rows: list[LedgerRow]


# --- /api/rescue ------------------------------------------------------------

class ChannelOption(Dto):
    channel_id: str
    name: str
    type: str
    eligible: bool
    value_inr: float
    vs_baseline_inr: float
    co2e_avoided_kg: float
    lead_time_hours: float
    max_qty_kg: float | None = None
    counterparty: str | None = None
    pickup_by: str | None = None
    exclusion_reason_code: str | None = None
    exclusion_reason: str | None = None
    exclusion_detail: str | None = None


class RescueBatch(Dto):
    id: str
    product_id: str
    ingredient_name: str
    zone_id: str
    zone_name: str
    qty_kg: float
    rsl_days: float
    state: str
    value_inr: float


class RescueSpecial(Dto):
    dish_id: str
    dish_name: str
    portions: float
    value_inr: float
    station: str | None = None


class RescueResponse(Dto):
    date: dt.date
    lambda_used: float
    batch: RescueBatch
    channels: list[ChannelOption]
    excluded: list[ChannelOption]
    special: RescueSpecial | None = None
    message: str | None = Field(
        default=None, description="Communicator draft. Null when the Verifier blocked it."
    )
    message_verified: bool = True


# --- /api/impact ------------------------------------------------------------

class BacktestPoint(Dto):
    date: dt.date
    actual: float
    forecast: float
    baseline: float
    held_out: bool


class ImpactResponse(Dto):
    date: dt.date
    series: list[BacktestPoint]
    mae: float
    baseline_mae: float
    improvement_pct: float
    acceptance_rate: float
    recommendations_shown: int
    recommendations_accepted: int
    saving_to_date_inr: float


# --- /api/simulate ----------------------------------------------------------

class SimulationPoint(Dto):
    lambda_value: float
    saving_inr: float
    saving_kg: float
    saving_co2e_kg: float
    portions_delta: float


class SimulateResponse(Dto):
    date: dt.date
    points: list[SimulationPoint]
    recommended_lambda: float


# --- lifecycle --------------------------------------------------------------

class AcceptRequest(Dto):
    note: str | None = None


class OverrideRequest(Dto):
    reason: str
    override_qty: float | None = None


class OutcomeResponse(Dto):
    id: str
    status: str
    acceptance_rate: float


# --- tracks -----------------------------------------------------------------

class TrackResponse(Dto):
    track: str
    title: str
    description: str
    lambda_used: float
    recommendations: list[RecommendationDto]
