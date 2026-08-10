"""Pydantic 2 response models — the frozen contract, in code.

`contracts/api-contract.md` is the human-readable version of this file. If they
ever disagree, this file wins and the contract doc is stale.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

# ---------------------------------------------------------------- shared


class SiteOut(BaseModel):
    id: int
    name: str
    type: str
    #: AgStack Asset Registry GeoID, when the source data carries one.
    geo_id: str | None = None


class HealthOut(BaseModel):
    status: str = "ok"
    version: str
    demo_today: date
    default_site_id: int | None
    sites: list[SiteOut]
    seeded: bool


class Money(BaseModel):
    kg: float = 0.0
    money: float = 0.0
    co2e: float = 0.0


class ActionOut(BaseModel):
    """One scored option. Excluded options carry their reason and are never
    hidden from the UI."""

    label: str
    action_type: str
    horizon: str
    qty: float
    qty_kg: float
    recovered_value: float
    cost: float
    net_recovery: float
    kg_food_saved: float
    co2e_saved_kg: float
    score: float
    feasible: bool
    exclusion_reason: str | None = None
    terms: dict[str, float] = Field(default_factory=dict)
    channel_id: int | None = None
    # Cascading-waterfall vocabulary. A label on the exit, not a gate on it —
    # `score` still decides the order. Null on the do-nothing baseline.
    waterfall_tier: str | None = None
    waterfall_tier_rank: int | None = None


class RecommendationOut(BaseModel):
    id: int
    horizon: str
    subject_type: str
    subject_id: int
    subject_label: str
    action_type: str
    action_params: dict = Field(default_factory=dict)
    baseline_value: float
    recommended_value: float
    saves: Money
    confidence: str
    rationale_text: str
    rationale_facts: dict = Field(default_factory=dict)
    status: str
    override_reason: str | None = None
    override_value: float | None = None
    expires_at: str | None = None


# ------------------------------------------------------------------ today


class KpiOut(BaseModel):
    kg_at_risk: float
    value_at_risk: float
    recoverable_today: float
    preventable_share: float | None = None
    produce_share_of_weight: float | None = None


class TodayOut(BaseModel):
    site_id: int
    site_name: str
    business_date: date
    lam: float
    kpis: KpiOut
    waste_drivers: list[dict]
    recommendations: list[RecommendationOut]


# ------------------------------------------------------------ attribution


class AttributionOut(BaseModel):
    site_id: int
    window_start: date
    window_end: date
    total_kg: float
    total_value: float
    produce_kg: float
    produce_value: float
    produce_share_of_weight: float
    by_reason: list[dict]
    by_product: list[dict]
    daily: list[dict]
    avoidable_trim: list[dict]
    headline: str


# ------------------------------------------------------------------- plan


class PlanLineOut(BaseModel):
    product_id: int
    label: str
    uom: str
    baseline_qty: float
    recommended_qty: float
    delta: float
    q_star: float
    forecast_median: float
    forecast_low: float
    forecast_high: float
    expected_waste_baseline_kg: float
    expected_waste_recommended_kg: float
    saving_kg: float
    saving_money: float
    saving_co2e: float
    confidence: str
    economics: dict = Field(default_factory=dict)


class PlanOut(BaseModel):
    site_id: int
    target_date: date
    lam: float
    lines: list[PlanLineOut]
    totals: Money
    ingredient_requirement: list[dict]


class FrontierOut(BaseModel):
    site_id: int
    target_date: date
    points: list[dict]
    note: str


# ----------------------------------------------------------------- ledger


class LedgerRowOut(BaseModel):
    batch_id: int
    product_id: int
    product: str
    category: str
    uom: str
    qty_on_hand: float
    qty_kg: float
    rsl_days: float
    rsl_explanation: str
    expected_consumption: float
    qty_at_risk: float
    waste_probability: float
    value_at_risk: float
    severity: str
    storage_zone: str | None = None

    # Additive, post-freeze. Provenance for lots that arrived on a tracked
    # consignment: the upstream code and where it was grown. Both null for
    # stock with no passport, and a client that ignores them renders exactly
    # the Ledger it rendered before.
    batch_code: str | None = None
    origin: str | None = None


class LedgerOut(BaseModel):
    site_id: int
    as_of: date
    rows: list[LedgerRowOut]
    total_value_at_risk: float


# ----------------------------------------------------------------- rescue


class RescueItemOut(BaseModel):
    batch_id: int
    product: str
    qty_at_risk: float
    uom: str
    rsl_days: float
    value_at_risk: float
    severity: str
    ranked: list[ActionOut]
    excluded: list[ActionOut]
    best_recovery: float
    uplift_vs_doing_nothing: float
    # What a fixed remaining-life ladder would have picked, versus what the
    # objective function did pick. Where they differ, the difference is the
    # argument for the optimiser.
    ladder_tier: str
    engine_tier: str | None = None
    tier_agrees: bool = True
    # Mandi modal price for this commodity, when AGMARKNET data is loaded.
    market_reference: dict | None = None


class RescueOut(BaseModel):
    site_id: int
    as_of: date
    lam: float
    items: list[RescueItemOut]
    total_recoverable: float


# ----------------------------------------------------------------- impact


class BacktestOut(BaseModel):
    train_start: date
    train_end: date
    eval_start: date
    eval_end: date
    days_evaluated: int
    products_evaluated: int
    actual_waste_kg: float
    modelled_waste_kg: float
    saving_kg: float
    saving_money: float
    median_abs_error: float
    naive_abs_error: float
    improvement_vs_naive: float | None
    interval_coverage: float
    daily: list[dict]
    note: str


class ImpactOut(BaseModel):
    site_id: int
    acceptance: dict
    realised_vs_projected: dict
    backtest: BacktestOut
    monthly_projection: Money


# ----------------------------------------------------------------- tracks


class TrackOut(BaseModel):
    track: str
    site_id: int
    site_name: str
    rows: list[dict]
    note: str


# ----------------------------------------------------------------- ingest


class IngestOut(BaseModel):
    accepted_files: list[str]
    report: dict
    recommendations_generated: int


class OverrideIn(BaseModel):
    reason: str = Field(min_length=1, max_length=400)
    value: float | None = None
