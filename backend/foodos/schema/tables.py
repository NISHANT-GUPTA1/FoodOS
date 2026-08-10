"""Canonical schema — design doc §5.

One schema for every track. A restaurant dish, a retail SKU and a manufactured
product are all `Product`; a prep container, a crate and a production lot are
all `Batch`. That is what lets one engine serve three tracks.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from foodos.schema.base import Base, TimestampMixin
from foodos.schema.enums import (
    BatchEventType,
    BatchLifecycle,
    BatchState,
    ChannelType,
    Confidence,
    Horizon,
    InventoryEventType,
    MaturityStage,
    PackagingType,
    PartyRole,
    RecommendationStatus,
    RescueOfferStatus,
    RiskLevel,
    SiteType,
    Track,
    TransportMode,
    WasteReason,
    WasteStage,
)

# --------------------------------------------------------------------------
# ORGANISATION
# --------------------------------------------------------------------------


class Organization(Base):
    __tablename__ = "organization"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    track: Mapped[Track] = mapped_column(String(20), default=Track.KITCHEN)
    timezone: Mapped[str] = mapped_column(String(40), default="Asia/Kolkata")
    currency: Mapped[str] = mapped_column(String(8), default="INR")

    sites: Mapped[list["Site"]] = relationship(back_populates="org")


class Site(Base):
    __tablename__ = "site"

    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organization.id"))
    name: Mapped[str] = mapped_column(String(120))
    type: Mapped[SiteType] = mapped_column(String(20), default=SiteType.KITCHEN)
    # AgStack Asset Registry GeoID — a 16-character geohash-derived key for a
    # registered field or facility boundary. Carried, never computed: B stores
    # whatever the source data supplies and nothing else depends on it yet.
    geo_id: Mapped[str | None] = mapped_column(String(32), nullable=True)

    org: Mapped[Organization] = relationship(back_populates="sites")


# --------------------------------------------------------------------------
# CATALOGUE
# --------------------------------------------------------------------------


class Product(Base):
    __tablename__ = "product"
    __table_args__ = (UniqueConstraint("org_id", "sku", name="uq_product_org_sku"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organization.id"))
    sku: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(120))
    category: Mapped[str] = mapped_column(String(64), default="general")
    uom: Mapped[str] = mapped_column(String(16), default="kg")

    unit_cost: Mapped[float] = mapped_column(Float, default=0.0)
    unit_price: Mapped[float] = mapped_column(Float, default=0.0)
    # A's `portion_kg`. Converts a quantity in portions into kilograms.
    unit_weight_kg: Mapped[float] = mapped_column(Float, default=1.0)

    is_dish: Mapped[bool] = mapped_column(Boolean, default=False)
    perishable: Mapped[bool] = mapped_column(Boolean, default=True)
    # Fruit and veg flag, straight from A. Authoritative for the produce share
    # headline — never infer it from the category string.
    is_produce: Mapped[bool] = mapped_column(Boolean, default=False)
    # Per-product CO2e intensity from A, in kg CO2e per unit of measure.
    # Falls back to the global default only when A has not supplied one.
    co2e_kg_per_uom: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Does this product get a PREVENT quantity recommendation? A decides.
    plannable: Mapped[bool] = mapped_column(Boolean, default=False)
    shelf_life_profile_id: Mapped[int | None] = mapped_column(
        ForeignKey("shelf_life_profile.id"), nullable=True
    )

    shelf_life_profile: Mapped["ShelfLifeProfile | None"] = relationship()
    recipe: Mapped["Recipe | None"] = relationship(
        back_populates="product", uselist=False
    )

    @property
    def margin(self) -> float:
        """Contribution margin per unit — the underage cost C_u."""
        return max(self.unit_price - self.unit_cost, 0.0)


class Recipe(Base):
    __tablename__ = "recipe"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("product.id"), unique=True)
    yield_qty: Mapped[float] = mapped_column(Float, default=1.0)
    yield_uom: Mapped[str] = mapped_column(String(16), default="portion")

    product: Mapped[Product] = relationship(back_populates="recipe")
    lines: Mapped[list["RecipeLine"]] = relationship(
        back_populates="recipe", cascade="all, delete-orphan"
    )


class RecipeLine(Base):
    __tablename__ = "recipe_line"

    id: Mapped[int] = mapped_column(primary_key=True)
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipe.id"))
    ingredient_product_id: Mapped[int] = mapped_column(ForeignKey("product.id"))
    qty: Mapped[float] = mapped_column(Float)
    uom: Mapped[str] = mapped_column(String(16), default="kg")
    # Standard culinary yield, e.g. cauliflower 0.58. Actual below this is
    # avoidable trim, which is the most produce-specific signal in the product.
    standard_yield_pct: Mapped[float] = mapped_column(Float, default=1.0)

    recipe: Mapped[Recipe] = relationship(back_populates="lines")
    ingredient: Mapped[Product] = relationship(foreign_keys=[ingredient_product_id])


class ShelfLifeProfile(Base):
    __tablename__ = "shelf_life_profile"

    id: Mapped[int] = mapped_column(primary_key=True)
    category: Mapped[str] = mapped_column(String(64), unique=True)
    base_shelf_life_days: Mapped[float] = mapped_column(Float)
    ref_temp_c: Mapped[float] = mapped_column(Float, default=4.0)
    q10: Mapped[float] = mapped_column(Float, default=2.5)
    cut_life_factor: Mapped[float] = mapped_column(Float, default=0.35)
    ethylene_sensitive: Mapped[bool] = mapped_column(Boolean, default=False)
    ethylene_emitter: Mapped[bool] = mapped_column(Boolean, default=False)


class StorageZone(Base):
    __tablename__ = "storage_zone"

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("site.id"))
    name: Mapped[str] = mapped_column(String(64))
    mean_temp_c: Mapped[float] = mapped_column(Float, default=4.0)
    # 'declared' | 'logged' | 'simulated' — never a physical sensor.
    temp_source: Mapped[str] = mapped_column(String(20), default="declared")


# --------------------------------------------------------------------------
# INVENTORY
# --------------------------------------------------------------------------


class Batch(Base):
    __tablename__ = "batch"
    __table_args__ = (Index("ix_batch_site_product", "site_id", "product_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("site.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("product.id"))
    lot_code: Mapped[str] = mapped_column(String(64))

    received_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    produced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    printed_expiry: Mapped[date | None] = mapped_column(Date, nullable=True)

    qty_received: Mapped[float] = mapped_column(Float)
    qty_remaining: Mapped[float] = mapped_column(Float)
    uom: Mapped[str] = mapped_column(String(16), default="kg")

    storage_zone_id: Mapped[int | None] = mapped_column(
        ForeignKey("storage_zone.id"), nullable=True
    )
    intake_grade: Mapped[float] = mapped_column(Float, default=1.0)  # 0..1
    state: Mapped[BatchState] = mapped_column(String(16), default=BatchState.WHOLE)
    unit_cost: Mapped[float] = mapped_column(Float, default=0.0)

    # Written by A's RSL model (open_batches.csv). B ships a deterministic Q10
    # fallback for rows A has not scored. Never computed inside the engine.
    rsl_days: Mapped[float | None] = mapped_column(Float, nullable=True)
    life_used: Mapped[float | None] = mapped_column(Float, nullable=True)
    rsl_explanation: Mapped[str | None] = mapped_column(String(400), nullable=True)

    product: Mapped[Product] = relationship()
    storage_zone: Mapped[StorageZone | None] = relationship()


class InventoryEvent(Base):
    __tablename__ = "inventory_event"

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("batch.id"))
    ts: Mapped[datetime] = mapped_column(DateTime)
    type: Mapped[InventoryEventType] = mapped_column(String(20))
    qty: Mapped[float] = mapped_column(Float)
    ref: Mapped[str | None] = mapped_column(String(120), nullable=True)


class StorageReading(Base):
    """Digital storage-condition input. Declared, uploaded or simulated —
    never read from a physical sensor."""

    __tablename__ = "storage_reading"

    id: Mapped[int] = mapped_column(primary_key=True)
    storage_zone_id: Mapped[int] = mapped_column(ForeignKey("storage_zone.id"))
    ts: Mapped[datetime] = mapped_column(DateTime)
    temp_c: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(20), default="simulated")


# --------------------------------------------------------------------------
# DEMAND & PRODUCTION
# --------------------------------------------------------------------------


class SalesRecord(Base):
    __tablename__ = "sales_record"
    __table_args__ = (
        Index("ix_sales_site_product_date", "site_id", "product_id", "business_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("site.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("product.id"))
    business_date: Mapped[date] = mapped_column(Date)
    qty: Mapped[float] = mapped_column(Float)
    revenue: Mapped[float] = mapped_column(Float, default=0.0)
    channel: Mapped[str] = mapped_column(String(32), default="dine_in")


class ProductionRecord(Base):
    __tablename__ = "production_record"
    __table_args__ = (
        Index("ix_prod_site_product_date", "site_id", "product_id", "business_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("site.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("product.id"))
    business_date: Mapped[date] = mapped_column(Date)
    planned_qty: Mapped[float] = mapped_column(Float, default=0.0)
    actual_qty: Mapped[float] = mapped_column(Float, default=0.0)
    uom: Mapped[str] = mapped_column(String(16), default="portion")


class DemandContext(Base):
    __tablename__ = "demand_context"
    __table_args__ = (
        UniqueConstraint("site_id", "business_date", name="uq_demand_ctx"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("site.id"))
    business_date: Mapped[date] = mapped_column(Date)
    dow: Mapped[int] = mapped_column(Integer)
    is_holiday: Mapped[bool] = mapped_column(Boolean, default=False)
    festival: Mapped[str | None] = mapped_column(String(64), nullable=True)
    weather_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    temp_max_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    promo_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    covers: Mapped[int | None] = mapped_column(Integer, nullable=True)
    footfall: Mapped[int | None] = mapped_column(Integer, nullable=True)


# --------------------------------------------------------------------------
# WASTE
# --------------------------------------------------------------------------


class WasteEvent(Base):
    __tablename__ = "waste_event"
    __table_args__ = (Index("ix_waste_site_date", "site_id", "business_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("site.id"))
    business_date: Mapped[date] = mapped_column(Date)
    product_id: Mapped[int | None] = mapped_column(
        ForeignKey("product.id"), nullable=True
    )
    batch_id: Mapped[int | None] = mapped_column(ForeignKey("batch.id"), nullable=True)

    qty: Mapped[float] = mapped_column(Float)
    uom: Mapped[str] = mapped_column(String(16), default="kg")
    qty_kg: Mapped[float] = mapped_column(Float, default=0.0)
    value: Mapped[float] = mapped_column(Float, default=0.0)

    reason: Mapped[WasteReason] = mapped_column(String(32))
    stage: Mapped[WasteStage] = mapped_column(String(24), default=WasteStage.SERVICE)
    capture_method: Mapped[str] = mapped_column(String(20), default="manual")
    note: Mapped[str | None] = mapped_column(String(240), nullable=True)

    product: Mapped[Product | None] = relationship()


# --------------------------------------------------------------------------
# INTELLIGENCE OUTPUT  (written by A, read by B)
# --------------------------------------------------------------------------


class ModelRun(Base):
    __tablename__ = "model_run"

    id: Mapped[int] = mapped_column(primary_key=True)
    model_name: Mapped[str] = mapped_column(String(64))
    version: Mapped[str] = mapped_column(String(32), default="0.1.0")
    trained_at: Mapped[datetime] = mapped_column(DateTime)
    window_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    window_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    metrics_json: Mapped[dict] = mapped_column(JSON, default=dict)


class Forecast(Base):
    """Demand *distribution*, never a point estimate."""

    __tablename__ = "forecast"
    __table_args__ = (
        UniqueConstraint(
            "site_id", "product_id", "target_date", name="uq_forecast_key"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("site.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("product.id"))
    target_date: Mapped[date] = mapped_column(Date)
    model_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("model_run.id"), nullable=True
    )

    q10: Mapped[float] = mapped_column(Float)
    q25: Mapped[float] = mapped_column(Float)
    q50: Mapped[float] = mapped_column(Float)
    q66: Mapped[float] = mapped_column(Float)
    q75: Mapped[float] = mapped_column(Float)
    q90: Mapped[float] = mapped_column(Float)
    expected: Mapped[float] = mapped_column(Float)


class RiskScore(Base):
    """Derived, not modelled — falls out of the forecast distribution + RSL."""

    __tablename__ = "risk_score"

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("batch.id"))
    as_of: Mapped[date] = mapped_column(Date)
    rsl_days: Mapped[float] = mapped_column(Float)
    expected_consumption_before_expiry: Mapped[float] = mapped_column(Float)
    qty_at_risk: Mapped[float] = mapped_column(Float)
    waste_probability: Mapped[float] = mapped_column(Float)
    value_at_risk: Mapped[float] = mapped_column(Float)


# --------------------------------------------------------------------------
# DECISION
# --------------------------------------------------------------------------


class Recommendation(Base, TimestampMixin):
    """The first-class output object.

    `baseline_value` is stored alongside `recommended_value` because that is
    the only way the saving can be honestly computed and later verified.
    """

    __tablename__ = "recommendation"
    __table_args__ = (Index("ix_rec_site_status", "site_id", "status"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("site.id"))
    business_date: Mapped[date] = mapped_column(Date)
    horizon: Mapped[Horizon] = mapped_column(String(12))

    subject_type: Mapped[str] = mapped_column(String(24))  # dish|batch|sku|run
    subject_id: Mapped[int] = mapped_column(Integer)
    subject_label: Mapped[str] = mapped_column(String(120), default="")

    action_type: Mapped[str] = mapped_column(String(32))
    action_params: Mapped[dict] = mapped_column(JSON, default=dict)

    baseline_value: Mapped[float] = mapped_column(Float, default=0.0)
    recommended_value: Mapped[float] = mapped_column(Float, default=0.0)

    expected_saving_kg: Mapped[float] = mapped_column(Float, default=0.0)
    expected_saving_money: Mapped[float] = mapped_column(Float, default=0.0)
    expected_co2e: Mapped[float] = mapped_column(Float, default=0.0)

    confidence: Mapped[Confidence] = mapped_column(String(8), default=Confidence.MEDIUM)
    rationale_facts: Mapped[dict] = mapped_column(JSON, default=dict)
    rationale_text: Mapped[str] = mapped_column(String(1000), default="")

    status: Mapped[RecommendationStatus] = mapped_column(
        String(16), default=RecommendationStatus.PENDING
    )
    override_reason: Mapped[str | None] = mapped_column(String(400), nullable=True)
    override_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    model_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("model_run.id"), nullable=True
    )

    outcome: Mapped["RecommendationOutcome | None"] = relationship(
        back_populates="recommendation", uselist=False, cascade="all, delete-orphan"
    )


class RecommendationOutcome(Base):
    __tablename__ = "recommendation_outcome"

    id: Mapped[int] = mapped_column(primary_key=True)
    recommendation_id: Mapped[int] = mapped_column(
        ForeignKey("recommendation.id"), unique=True
    )
    measured_at: Mapped[datetime] = mapped_column(DateTime)
    actual_value: Mapped[float] = mapped_column(Float, default=0.0)
    actual_saving_kg: Mapped[float] = mapped_column(Float, default=0.0)
    actual_saving_money: Mapped[float] = mapped_column(Float, default=0.0)

    recommendation: Mapped[Recommendation] = relationship(back_populates="outcome")


# --------------------------------------------------------------------------
# RECOVER
# --------------------------------------------------------------------------


class Channel(Base):
    __tablename__ = "channel"

    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organization.id"))
    type: Mapped[ChannelType] = mapped_column(String(24))
    name: Mapped[str] = mapped_column(String(120))
    contact: Mapped[str | None] = mapped_column(String(120), nullable=True)
    distance_km: Mapped[float] = mapped_column(Float, default=0.0)
    lead_time_hours: Mapped[float] = mapped_column(Float, default=0.0)
    min_qty: Mapped[float] = mapped_column(Float, default=0.0)
    max_qty: Mapped[float | None] = mapped_column(Float, nullable=True)
    accepted_categories: Mapped[list] = mapped_column(JSON, default=list)
    # Fraction of unit_price recovered through this channel.
    price_factor: Mapped[float] = mapped_column(Float, default=0.0)
    fixed_cost: Mapped[float] = mapped_column(Float, default=0.0)
    cost_per_km: Mapped[float] = mapped_column(Float, default=0.0)
    # e.g. {"min_intake_grade": 0.6, "requires_whole": true}
    eligibility_rules: Mapped[dict] = mapped_column(JSON, default=dict)
    social_value_per_kg: Mapped[float] = mapped_column(Float, default=0.0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class RescueOffer(Base):
    __tablename__ = "rescue_offer"

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("batch.id"))
    channel_id: Mapped[int] = mapped_column(ForeignKey("channel.id"))
    qty: Mapped[float] = mapped_column(Float)
    expected_recovery: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[RescueOfferStatus] = mapped_column(
        String(16), default=RescueOfferStatus.DRAFT
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


# --------------------------------------------------------------------------
# EXTERNAL REFERENCE DATA
# --------------------------------------------------------------------------


class MarketPrice(Base):
    """A wholesale mandi quotation, as published by AGMARKNET / e-NAM.

    Reference data about the outside world, not an observation of this
    customer's stock, so it hangs off nothing. Prices arrive per quintal and
    are stored per kilogram — see `external/agmarknet.py`.
    """

    __tablename__ = "market_price"
    __table_args__ = (
        Index("ix_market_price_commodity_date", "commodity", "arrival_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    commodity: Mapped[str] = mapped_column(String(64))
    variety: Mapped[str | None] = mapped_column(String(64), nullable=True)
    grade: Mapped[str | None] = mapped_column(String(32), nullable=True)
    state: Mapped[str | None] = mapped_column(String(64), nullable=True)
    district: Mapped[str | None] = mapped_column(String(64), nullable=True)
    market: Mapped[str] = mapped_column(String(120))
    arrival_date: Mapped[date] = mapped_column(Date)
    min_price_per_kg: Mapped[float] = mapped_column(Float, default=0.0)
    max_price_per_kg: Mapped[float] = mapped_column(Float, default=0.0)
    modal_price_per_kg: Mapped[float] = mapped_column(Float, default=0.0)
    source: Mapped[str] = mapped_column(String(32), default="agmarknet")


# --------------------------------------------------------------------------
# AGRI BATCH — added at H2-3 per FoodOS-Team-Split-v2.md §4.
#
# Ruling 1: additive. Nothing above this line is altered, and none of these
# tables duplicates one that already exists. `Batch` above is a kitchen lot
# sitting in a storage zone; a `Consignment` is a farm-gate shipment in transit
# between two places. Different subjects on the same engine — which is the
# platform claim — so they are separate tables rather than one overloaded one.
#
# Shape follows the Batch Profile frozen in Contract 2 §2. Field names match
# the wire, so the API layer is a projection rather than a translation.
# --------------------------------------------------------------------------


class Consignment(Base, TimestampMixin):
    """A shipment of one commodity from an origin to a destination.

    `code` is the public identifier the demo says out loud ("T1024"); `id` is
    the surrogate key everything joins on. Two columns because a judge reads
    T1024 off the screen and a foreign key should not carry meaning.

    The `state` block of the Batch Profile is stored flat here rather than as
    JSON: quality_score and field_heat_hours are filtered and sorted on Screen
    1, and a JSON blob cannot be indexed for that.
    """

    __tablename__ = "consignment"
    __table_args__ = (
        UniqueConstraint("code", name="uq_consignment_code"),
        Index("ix_consignment_commodity_status", "commodity", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32))
    org_id: Mapped[int] = mapped_column(ForeignKey("organization.id"))

    commodity: Mapped[str] = mapped_column(String(64))
    qty_kg: Mapped[float] = mapped_column(Float)
    origin: Mapped[str] = mapped_column(String(120))
    destination: Mapped[str] = mapped_column(String(120))
    harvested_at: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[BatchLifecycle] = mapped_column(
        String(24), default=BatchLifecycle.CREATED
    )

    # --- identity: the parts that survive a change of hands -----------------
    # Added with the passport layer. `status` above now carries a
    # `BatchLifecycle` value rather than a free string; the four Contract 2b
    # spellings are still what goes on the wire, via
    # `BatchLifecycle.contract_status`.

    #: Set on a child produced by a split. The code keeps the parent's stem
    #: (`TOM-KLR-00124-A`), so traceability survives even if this column is
    #: ever lost — but the join is what queries use.
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("consignment.id"), nullable=True
    )

    #: What is still under this identity. Splitting moves mass to the children
    #: and drops this; a WASTED event drops it too. `qty_kg` stays as
    #: registered at the farm gate, because the loss story is the difference
    #: between the two and overwriting `qty_kg` would erase it.
    qty_kg_remaining: Mapped[float] = mapped_column(Float, default=0.0)

    #: Current custody. Denormalised from the last `BatchHandoff` on purpose:
    #: the Command Center filters on it, and walking the handoff chain for
    #: every row of a list screen is a join per row for a value that only
    #: changes a handful of times in a batch's life.
    current_owner: Mapped[str | None] = mapped_column(String(120), nullable=True)
    current_owner_role: Mapped[PartyRole | None] = mapped_column(
        String(24), nullable=True
    )
    current_location: Mapped[str | None] = mapped_column(String(120), nullable=True)

    children: Mapped[list[Consignment]] = relationship(
        back_populates="parent", cascade="all, delete-orphan"
    )
    parent: Mapped[Consignment | None] = relationship(
        back_populates="children", remote_side=[id]
    )
    events: Mapped[list[BatchEvent]] = relationship(
        back_populates="consignment",
        cascade="all, delete-orphan",
        order_by="BatchEvent.occurred_at, BatchEvent.id",
    )
    handoffs: Mapped[list[BatchHandoff]] = relationship(
        back_populates="consignment",
        cascade="all, delete-orphan",
        order_by="BatchHandoff.occurred_at, BatchHandoff.id",
    )
    snapshots: Mapped[list[BatchStateSnapshot]] = relationship(
        back_populates="consignment",
        cascade="all, delete-orphan",
        order_by="BatchStateSnapshot.sequence",
    )

    # --- the `state` block of the Batch Profile -----------------------------
    # Written by A's quality_score() and the questionnaire. B ships a
    # deterministic placeholder for rows A has not scored yet (§4, H21-26):
    # an A outage degrades the number, it never 500s the screen.
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    grade: Mapped[str | None] = mapped_column(String(8), nullable=True)
    maturity: Mapped[MaturityStage | None] = mapped_column(String(8), nullable=True)
    damage_factor: Mapped[str | None] = mapped_column(String(16), nullable=True)
    field_heat_hours_over_30c: Mapped[float | None] = mapped_column(Float, nullable=True)

    assessment: Mapped[BatchAssessment | None] = relationship(
        back_populates="consignment", uselist=False, cascade="all, delete-orphan"
    )
    journey: Mapped[ShipmentJourney | None] = relationship(
        back_populates="consignment", uselist=False, cascade="all, delete-orphan"
    )
    weather: Mapped[list[WeatherExposure]] = relationship(
        back_populates="consignment", cascade="all, delete-orphan"
    )
    risk: Mapped[LossRiskScore | None] = relationship(
        back_populates="consignment", uselist=False, cascade="all, delete-orphan"
    )


class BatchAssessment(Base, TimestampMixin):
    """What the farmer answered and what the photos showed. 1:1 with a consignment.

    Both sides are JSON on purpose. `answers` is keyed by D's `feature_key`
    from content/questionnaire/*.yaml, and adding a question there must not
    need a migration here — that is the whole point of the tree being data.
    `photo_features` is A's `extract_photo_features()` verbatim.

    `photo_paths` points at files under backend/data/photos/, which §8 does NOT
    commit. A fresh clone will not have them, and a batch with no photos still
    has to score, so nothing may treat an empty list as an error.
    """

    __tablename__ = "batch_assessment"

    id: Mapped[int] = mapped_column(primary_key=True)
    consignment_id: Mapped[int] = mapped_column(
        ForeignKey("consignment.id"), unique=True
    )

    answers: Mapped[dict] = mapped_column(JSON, default=dict)
    photo_paths: Mapped[list] = mapped_column(JSON, default=list)
    photo_features: Mapped[dict] = mapped_column(JSON, default=dict)
    photo_confidence: Mapped[Confidence | None] = mapped_column(String(8), nullable=True)

    consignment: Mapped[Consignment] = relationship(back_populates="assessment")


class ShipmentJourney(Base, TimestampMixin):
    """How it travels, and the route snapshot it was scored against. 1:1.

    `route_source` carries D's `source` stamp ("snapshot" | "live") straight
    through to the UI. Ruling 3 says that field is never hidden, so it is a
    stored column rather than something reconstructed at render time.
    """

    __tablename__ = "shipment_journey"

    id: Mapped[int] = mapped_column(primary_key=True)
    consignment_id: Mapped[int] = mapped_column(
        ForeignKey("consignment.id"), unique=True
    )

    transport: Mapped[TransportMode] = mapped_column(
        String(24), default=TransportMode.OPEN_TRUCK
    )
    packaging: Mapped[PackagingType] = mapped_column(
        String(32), default=PackagingType.VENTILATED_PLASTIC_CRATE
    )
    depart_at: Mapped[datetime] = mapped_column(DateTime)

    # --- snapshot from D's external/routes.py::route_profile() --------------
    distance_km: Mapped[float] = mapped_column(Float, default=0.0)
    transit_hours: Mapped[float] = mapped_column(Float, default=0.0)
    road_quality: Mapped[str | None] = mapped_column(String(16), nullable=True)
    vibration_index: Mapped[float | None] = mapped_column(Float, nullable=True)
    route_source: Mapped[str] = mapped_column(String(16), default="snapshot")

    consignment: Mapped[Consignment] = relationship(back_populates="journey")


class WeatherExposure(Base):
    """One hour of the route weather the batch was scored against. 1:N.

    Stored per hour rather than as a min/max pair because the Q10 decay
    integrates over the curve. A 38 degC spike in hour three and a flat 33 degC
    are not the same journey, and collapsing them to a mean loses exactly the
    signal the loss model is reading.
    """

    __tablename__ = "weather_exposure"
    __table_args__ = (
        Index("ix_weather_exposure_consignment_hour", "consignment_id", "hour_offset"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    consignment_id: Mapped[int] = mapped_column(ForeignKey("consignment.id"))

    hour_offset: Mapped[int] = mapped_column(Integer)
    temp_c: Mapped[float] = mapped_column(Float)
    rh: Mapped[float | None] = mapped_column(Float, nullable=True)
    solar: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(16), default="snapshot")

    consignment: Mapped[Consignment] = relationship(back_populates="weather")


class LossRiskScore(Base, TimestampMixin):
    """A's loss and RUL prediction for one consignment. 1:1.

    `low`/`high` are the quantile band, kept beside the point estimate because
    Screen 3 renders a band and not a point (§5, H14-20). Dropping them here
    would force the frontend to invent one.

    `model_run_id` is what makes every figure on screen traceable to a model
    run — A's H30-36 rule. A row scored by B's deterministic placeholder
    carries null here, which is how the two are told apart.
    """

    __tablename__ = "loss_risk_score"

    id: Mapped[int] = mapped_column(primary_key=True)
    consignment_id: Mapped[int] = mapped_column(
        ForeignKey("consignment.id"), unique=True
    )
    model_run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    loss_pct: Mapped[float] = mapped_column(Float)
    loss_kg: Mapped[float] = mapped_column(Float)
    low: Mapped[float | None] = mapped_column(Float, nullable=True)
    high: Mapped[float | None] = mapped_column(Float, nullable=True)
    rul_hours: Mapped[float] = mapped_column(Float)

    level: Mapped[RiskLevel] = mapped_column(String(8), default=RiskLevel.LOW)
    confidence: Mapped[Confidence] = mapped_column(String(8), default=Confidence.MEDIUM)

    # A's ranked contributions: [{"name": ..., "contribution": 0.31, "text": ...}]
    drivers: Mapped[list] = mapped_column(JSON, default=list)

    # Points at one of `plans` below. use_alter because the two tables
    # reference each other and SQLite needs the constraint added after both
    # exist rather than inline in CREATE TABLE.
    best_plan_id: Mapped[int | None] = mapped_column(
        ForeignKey("candidate_plan.id", use_alter=True, name="fk_risk_best_plan"),
        nullable=True,
    )

    consignment: Mapped[Consignment] = relationship(back_populates="risk")
    plans: Mapped[list[CandidatePlan]] = relationship(
        back_populates="risk_score",
        cascade="all, delete-orphan",
        foreign_keys="CandidatePlan.loss_risk_score_id",
    )


class CandidatePlan(Base, TimestampMixin):
    """One row of the Action Evaluation Matrix. 1:N off the risk score.

    Every numeric column here is an output of `engine/optimiser.py::score()`.
    None is computed in the API layer — Ruling 1, and B's hard rule: one
    `score()`, many action spaces.

    `terms` carries the full breakdown of V(a) so no figure in the matrix is
    unattributable when a judge asks where it came from. `action_params` is the
    parameter dict A's orchestrator proposed, kept so an accepted plan can be
    replayed exactly rather than re-derived.

    Infeasible plans are rows too, carrying `exclusion_reason`. §4 H13-17:
    every excluded plan is returned with its reason, never hidden.
    """

    __tablename__ = "candidate_plan"
    __table_args__ = (
        Index("ix_candidate_plan_risk", "loss_risk_score_id", "net_value"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    loss_risk_score_id: Mapped[int] = mapped_column(ForeignKey("loss_risk_score.id"))

    label: Mapped[str] = mapped_column(String(200))
    action_type: Mapped[str] = mapped_column(String(32))
    horizon: Mapped[Horizon] = mapped_column(String(16), default=Horizon.PREVENT)
    action_params: Mapped[dict] = mapped_column(JSON, default=dict)

    loss_pct: Mapped[float] = mapped_column(Float, default=0.0)
    loss_kg: Mapped[float] = mapped_column(Float, default=0.0)
    logistics_cost: Mapped[float] = mapped_column(Float, default=0.0)
    gross_revenue: Mapped[float] = mapped_column(Float, default=0.0)
    net_value: Mapped[float] = mapped_column(Float, default=0.0)
    delta_vs_baseline: Mapped[float] = mapped_column(Float, default=0.0)

    is_baseline: Mapped[bool] = mapped_column(Boolean, default=False)
    is_best: Mapped[bool] = mapped_column(Boolean, default=False)
    feasible: Mapped[bool] = mapped_column(Boolean, default=True)
    exclusion_reason: Mapped[str | None] = mapped_column(String(240), nullable=True)

    terms: Mapped[dict] = mapped_column(JSON, default=dict)

    risk_score: Mapped[LossRiskScore] = relationship(
        back_populates="plans", foreign_keys=[loss_risk_score_id]
    )


# --------------------------------------------------------------------------
# BATCH IDENTITY — the digital passport.
#
# `Consignment` above answers "what is this batch and how bad is it right
# now?". These three answer "what has happened to it, who has held it, and
# what did we believe at each of those moments?" — which is what makes it an
# identity rather than a row that gets overwritten.
#
# The rule the three enforce together: **nothing mutates a batch silently.**
# Every change is an append to `batch_event`; every change of hands is an
# append to `batch_handoff`; every re-score is an append to
# `batch_state_snapshot`. The columns on `Consignment` are a cache of the
# latest of each, and could be rebuilt from these tables if they were lost.
# --------------------------------------------------------------------------


class BatchEvent(Base, TimestampMixin):
    """One thing that happened to a batch. Append-only. 1:N.

    `occurred_at` is when it happened in the world; `created_at` (from the
    mixin) is when we were told. They differ whenever a transporter reports a
    delay two hours after being stuck in it, and a timeline that conflates the
    two shows the batch reacting before the cause.

    `payload` is JSON because the event alphabet is heterogeneous by nature —
    a DELAY carries `{"duration_hours": 6}` and a TEMPERATURE_EXPOSURE carries
    `{"temp_c": 41, "hours": 3}`. Giving each a typed column would be a dozen
    mostly-null columns, and giving them a shared one would mean
    `duration_hours` sometimes held degrees.
    """

    __tablename__ = "batch_event"
    __table_args__ = (
        Index("ix_batch_event_consignment_time", "consignment_id", "occurred_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    consignment_id: Mapped[int] = mapped_column(ForeignKey("consignment.id"))

    type: Mapped[BatchEventType] = mapped_column(String(28))
    occurred_at: Mapped[datetime] = mapped_column(DateTime)
    location: Mapped[str | None] = mapped_column(String(120), nullable=True)

    #: Who reported it. Free text and nullable — an FPO clerk is not a user
    #: account in this system, and demanding one would mean the events that
    #: matter most never get recorded.
    actor: Mapped[str | None] = mapped_column(String(120), nullable=True)
    actor_role: Mapped[PartyRole | None] = mapped_column(String(24), nullable=True)

    #: Mass this event concerns, when it concerns one — a partial diversion or
    #: a spoilage write-off. Null for events that touch the whole batch.
    qty_kg: Mapped[float | None] = mapped_column(Float, nullable=True)

    payload: Mapped[dict] = mapped_column(JSON, default=dict)

    #: The lifecycle move this event caused, recorded on the event so the
    #: timeline can show the transition without re-deriving it.
    from_status: Mapped[BatchLifecycle | None] = mapped_column(
        String(24), nullable=True
    )
    to_status: Mapped[BatchLifecycle | None] = mapped_column(String(24), nullable=True)

    #: The snapshot this event produced, when it triggered a re-score. Null for
    #: events that do not change the physics — see `BatchEventType.rescores`.
    #:
    #: `ondelete="SET NULL"` because events and snapshots are siblings, both
    #: cascaded from the consignment, and nothing orders one before the other.
    #: Without it, deleting a batch can remove a snapshot while an event still
    #: points at it and the foreign key fails — which makes a batch
    #: undeletable, arbitrarily, depending on collection ordering.
    snapshot_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "batch_state_snapshot.id",
            use_alter=True,
            name="fk_event_snapshot",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    consignment: Mapped[Consignment] = relationship(back_populates="events")


class BatchHandoff(Base, TimestampMixin):
    """A change of custody. Append-only. 1:N.

    A separate table rather than a HANDOFF event's payload because custody is
    queried as a chain — "who has held this batch, in order" — and a chain of
    JSON blobs cannot be joined against parties or filtered on a role.
    The HANDOFF `BatchEvent` is still written alongside, so the timeline stays
    complete; this table is the structured view of the same fact.

    Note what is *not* here: a new batch id. The transporter does not create a
    batch. `TOM-KLR-00124` at the farm gate and `TOM-KLR-00124` at the mandi
    are the same identity, and that is the entire point of the layer.
    """

    __tablename__ = "batch_handoff"
    __table_args__ = (
        Index("ix_batch_handoff_consignment_time", "consignment_id", "occurred_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    consignment_id: Mapped[int] = mapped_column(ForeignKey("consignment.id"))

    from_party: Mapped[str | None] = mapped_column(String(120), nullable=True)
    from_role: Mapped[PartyRole | None] = mapped_column(String(24), nullable=True)
    to_party: Mapped[str] = mapped_column(String(120))
    to_role: Mapped[PartyRole] = mapped_column(String(24))

    occurred_at: Mapped[datetime] = mapped_column(DateTime)
    location: Mapped[str | None] = mapped_column(String(120), nullable=True)

    #: Mass accepted. Equal to the batch's remaining mass in the ordinary case;
    #: less when a receiver rejects part of a load, which is a real and common
    #: event at a mandi gate and one the loss ledger has to be able to express.
    qty_kg: Mapped[float] = mapped_column(Float)

    note: Mapped[str | None] = mapped_column(String(400), nullable=True)

    consignment: Mapped[Consignment] = relationship(back_populates="handoffs")


class BatchStateSnapshot(Base, TimestampMixin):
    """What we believed about the batch at one moment. Append-only. 1:N.

    `LossRiskScore` is 1:1 and holds the *current* belief; this is the history
    of it. Both exist because the two questions are different: Screen 3 asks
    "what is the risk now", and the passport asks "what did the model say at
    dispatch, and what does it say after the delay" — which is the before/after
    the whole demo turns on, and which a 1:1 row overwrites.

    Nothing ever updates a row of this table. A correction is a new snapshot.

    `sequence` is a per-batch counter rather than a global one so that
    "snapshot 1" means "the state it was registered in" for every batch, which
    is how the passport labels it.
    """

    __tablename__ = "batch_state_snapshot"
    __table_args__ = (
        UniqueConstraint(
            "consignment_id", "sequence", name="uq_batch_snapshot_sequence"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    consignment_id: Mapped[int] = mapped_column(ForeignKey("consignment.id"))
    sequence: Mapped[int] = mapped_column(Integer)

    #: World-time this belief describes, not wall-clock time it was computed.
    as_of: Mapped[datetime] = mapped_column(DateTime)
    reason: Mapped[str] = mapped_column(String(120), default="created")
    status: Mapped[BatchLifecycle] = mapped_column(String(24))
    location: Mapped[str | None] = mapped_column(String(120), nullable=True)
    qty_kg: Mapped[float] = mapped_column(Float)

    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    loss_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    loss_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    low: Mapped[float | None] = mapped_column(Float, nullable=True)
    high: Mapped[float | None] = mapped_column(Float, nullable=True)
    rul_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    level: Mapped[RiskLevel | None] = mapped_column(String(8), nullable=True)
    confidence: Mapped[Confidence | None] = mapped_column(String(8), nullable=True)

    #: Null when the row came from B's deterministic fallback rather than A's
    #: model — the same tell as on `LossRiskScore`, kept per snapshot so a
    #: passport can say which of its own entries were modelled.
    model_run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    #: The `base` dict handed to `agri.predict()`. Kept verbatim so any
    #: snapshot can be replayed and audited rather than taken on trust.
    inputs: Mapped[dict] = mapped_column(JSON, default=dict)
    drivers: Mapped[list] = mapped_column(JSON, default=list)

    consignment: Mapped[Consignment] = relationship(back_populates="snapshots")
