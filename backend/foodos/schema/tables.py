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
    BatchState,
    ChannelType,
    Confidence,
    Horizon,
    InventoryEventType,
    RecommendationStatus,
    RescueOfferStatus,
    SiteType,
    Track,
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
