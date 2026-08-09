"""SQLAlchemy tables — the canonical schema.

Sixteen entities. This is the shape every other module agrees on, so it is the one file
worth reading before writing anything else.

Design notes worth knowing:

* Product covers ingredients and dishes both, discriminated by ``kind``. A recipe line
  points at an ingredient Product; a sales record points at a dish Product. Keeping them
  in one table is what lets an ingredient shortage and a dish over-production be compared
  by the same optimiser.
* Money is REAL, not integer paise. This is a demo, and the rounding error over a 36-hour
  dataset is smaller than the rounding on the menu prices themselves.
* Nothing here stores a derived figure that the engine can recompute, with two exceptions:
  Forecast and RiskScore, which cache expensive model output per day.

Owner: Person B.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# --- reference data ---------------------------------------------------------

class ShelfLifeProfile(Base):
    """One per category in content/shelf_life.yaml. The constants behind the RSL model."""

    __tablename__ = "shelf_life_profile"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)  # e.g. "dairy_fresh"
    base_shelf_life_days: Mapped[float] = mapped_column(Float)
    ref_temp_c: Mapped[float] = mapped_column(Float)
    q10: Mapped[float] = mapped_column(Float)
    cut_life_factor: Mapped[float] = mapped_column(Float)
    ethylene_producer: Mapped[bool] = mapped_column(Boolean, default=False)
    ethylene_sensitive: Mapped[bool] = mapped_column(Boolean, default=False)
    freeze_tolerant: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class StorageZone(Base):
    """A fridge. ``typical_temp_c`` is what it actually runs at, which is the whole point."""

    __tablename__ = "storage_zone"

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    set_temp_c: Mapped[float] = mapped_column(Float)
    typical_temp_c: Mapped[float] = mapped_column(Float)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    @property
    def is_running_warm(self) -> bool:
        return self.typical_temp_c - self.set_temp_c >= 1.5


class Product(Base):
    """An ingredient or a dish."""

    __tablename__ = "product"

    id: Mapped[str] = mapped_column(String(60), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(12))  # "ingredient" | "dish"
    category: Mapped[str | None] = mapped_column(String(40), nullable=True)

    # ingredient economics
    unit_cost_per_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    co2e_kg_per_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    disposal_cost_per_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    prep_yield: Mapped[float] = mapped_column(Float, default=1.0)
    shelf_life_profile_id: Mapped[str | None] = mapped_column(
        ForeignKey("shelf_life_profile.id"), nullable=True
    )

    # dish economics — derived at seed time from the bill of materials, never hand-entered
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    portion_g: Mapped[float | None] = mapped_column(Float, nullable=True)
    station: Mapped[str | None] = mapped_column(String(40), nullable=True)
    prep_ahead_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_veg: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    food_cost_per_portion: Mapped[float | None] = mapped_column(Float, nullable=True)
    contribution_margin: Mapped[float | None] = mapped_column(Float, nullable=True)
    co2e_kg_per_portion: Mapped[float | None] = mapped_column(Float, nullable=True)
    input_kg_per_portion: Mapped[float | None] = mapped_column(Float, nullable=True)
    disposal_cost_per_portion: Mapped[float | None] = mapped_column(Float, nullable=True)

    shelf_life: Mapped[ShelfLifeProfile | None] = relationship(lazy="joined")
    recipe: Mapped["Recipe | None"] = relationship(back_populates="dish", uselist=False)


class Recipe(Base):
    __tablename__ = "recipe"

    id: Mapped[str] = mapped_column(String(60), primary_key=True)
    dish_id: Mapped[str] = mapped_column(ForeignKey("product.id"), unique=True)
    portion_g: Mapped[float] = mapped_column(Float)
    station: Mapped[str | None] = mapped_column(String(40), nullable=True)

    dish: Mapped[Product] = relationship(back_populates="recipe")
    lines: Mapped[list["RecipeLine"]] = relationship(
        back_populates="recipe", cascade="all, delete-orphan", lazy="selectin"
    )


class RecipeLine(Base):
    """One ingredient in one dish, in PREPPED weight.

    Purchase quantity is ``qty_kg / product.prep_yield``. That division is the bill of
    materials explosion, and it is the only place it happens.
    """

    __tablename__ = "recipe_line"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recipe_id: Mapped[str] = mapped_column(ForeignKey("recipe.id"))
    ingredient_id: Mapped[str] = mapped_column(ForeignKey("product.id"))
    qty_kg: Mapped[float] = mapped_column(Float)

    recipe: Mapped[Recipe] = relationship(back_populates="lines")
    ingredient: Mapped[Product] = relationship(lazy="joined")

    __table_args__ = (UniqueConstraint("recipe_id", "ingredient_id", name="uq_recipe_ingredient"),)


class Channel(Base):
    """A recovery route, with the feasibility gate stored as data rather than as code."""

    __tablename__ = "channel"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    type: Mapped[str] = mapped_column(String(30))
    basis: Mapped[str] = mapped_column(String(20))  # "menu_price" | "food_cost"
    recovery_factor: Mapped[float] = mapped_column(Float)
    lead_time_hours: Mapped[float] = mapped_column(Float)
    min_residual_life_hours: Mapped[float] = mapped_column(Float)
    min_qty_kg: Mapped[float] = mapped_column(Float, default=0.0)
    max_qty_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    states: Mapped[list] = mapped_column(JSON)
    allowed_categories: Mapped[list | str] = mapped_column(JSON)
    available_days: Mapped[list] = mapped_column(JSON)
    cutoff_hour: Mapped[int] = mapped_column(Integer)
    requires: Mapped[list] = mapped_column(JSON)
    co2e_avoided_factor: Mapped[float] = mapped_column(Float, default=1.0)
    is_baseline: Mapped[bool] = mapped_column(Boolean, default=False)
    counterparty: Mapped[str | None] = mapped_column(String(80), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


# --- transactional data -----------------------------------------------------

class Batch(Base):
    """A physical lot of one product, in one zone, with an age."""

    __tablename__ = "batch"

    id: Mapped[str] = mapped_column(String(30), primary_key=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("product.id"))
    zone_id: Mapped[str] = mapped_column(ForeignKey("storage_zone.id"))
    qty_kg: Mapped[float] = mapped_column(Float)
    received_at: Mapped[dt.datetime] = mapped_column(DateTime)
    state: Mapped[str] = mapped_column(String(20), default="raw")  # raw|prepped|cooked|trim
    is_cut: Mapped[bool] = mapped_column(Boolean, default=False)
    unit_cost_per_kg: Mapped[float] = mapped_column(Float)
    is_open: Mapped[bool] = mapped_column(Boolean, default=True)
    ethylene_exposed: Mapped[bool] = mapped_column(Boolean, default=False)
    cold_chain_available: Mapped[bool] = mapped_column(Boolean, default=True)
    unopened_packaging: Mapped[bool] = mapped_column(Boolean, default=False)

    product: Mapped[Product] = relationship(lazy="joined")
    zone: Mapped[StorageZone] = relationship(lazy="joined")

    def age_days(self, at: dt.datetime) -> float:
        return max(0.0, (at - self.received_at).total_seconds() / 86400.0)


class InventoryEvent(Base):
    __tablename__ = "inventory_event"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[str] = mapped_column(ForeignKey("batch.id"))
    ts: Mapped[dt.datetime] = mapped_column(DateTime)
    event_type: Mapped[str] = mapped_column(String(20))  # receive|consume|waste|transfer|adjust
    qty_kg: Mapped[float] = mapped_column(Float)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class SalesRecord(Base):
    __tablename__ = "sales_record"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[dt.date] = mapped_column(Date, index=True)
    dish_id: Mapped[str] = mapped_column(ForeignKey("product.id"), index=True)
    qty_portions: Mapped[float] = mapped_column(Float)
    revenue_inr: Mapped[float] = mapped_column(Float)

    __table_args__ = (UniqueConstraint("date", "dish_id", name="uq_sales_date_dish"),)


class ProductionRecord(Base):
    """What the prep sheet said, and what the kitchen actually made.

    The gap between ``planned_portions`` and the forecast is plan drift — pathology one.
    """

    __tablename__ = "production_record"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[dt.date] = mapped_column(Date, index=True)
    dish_id: Mapped[str] = mapped_column(ForeignKey("product.id"), index=True)
    planned_portions: Mapped[float] = mapped_column(Float)
    produced_portions: Mapped[float] = mapped_column(Float)

    __table_args__ = (UniqueConstraint("date", "dish_id", name="uq_production_date_dish"),)


class DemandContext(Base):
    """The exogenous features the forecaster is allowed to see."""

    __tablename__ = "demand_context"

    date: Mapped[dt.date] = mapped_column(Date, primary_key=True)
    dow: Mapped[int] = mapped_column(Integer)  # 0 = Monday
    is_weekend: Mapped[bool] = mapped_column(Boolean)
    is_holiday: Mapped[bool] = mapped_column(Boolean, default=False)
    rain_mm: Mapped[float] = mapped_column(Float, default=0.0)
    temp_c: Mapped[float] = mapped_column(Float, default=28.0)
    promo: Mapped[bool] = mapped_column(Boolean, default=False)
    local_event: Mapped[bool] = mapped_column(Boolean, default=False)


class WasteEvent(Base):
    __tablename__ = "waste_event"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[dt.date] = mapped_column(Date, index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("product.id"))
    qty_kg: Mapped[float] = mapped_column(Float)
    #: overproduction | spoilage | trim | plate_waste | supplier
    reason: Mapped[str] = mapped_column(String(30), index=True)
    value_inr: Mapped[float] = mapped_column(Float)
    co2e_kg: Mapped[float] = mapped_column(Float)
    zone_id: Mapped[str | None] = mapped_column(ForeignKey("storage_zone.id"), nullable=True)

    product: Mapped[Product] = relationship(lazy="joined")


class ZoneTemperature(Base):
    """Daily mean service-hours temperature per zone. The evidence for pathology two."""

    __tablename__ = "zone_temperature"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[dt.date] = mapped_column(Date, index=True)
    zone_id: Mapped[str] = mapped_column(ForeignKey("storage_zone.id"), index=True)
    mean_temp_c: Mapped[float] = mapped_column(Float)
    service_temp_c: Mapped[float] = mapped_column(Float)

    __table_args__ = (UniqueConstraint("date", "zone_id", name="uq_zone_temp"),)


# --- model output -----------------------------------------------------------

class Forecast(Base):
    __tablename__ = "forecast"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[dt.date] = mapped_column(Date, index=True)
    dish_id: Mapped[str] = mapped_column(ForeignKey("product.id"), index=True)
    quantile: Mapped[float] = mapped_column(Float)
    value: Mapped[float] = mapped_column(Float)
    model_version: Mapped[str] = mapped_column(String(40), default="lgbm-q1")
    is_backtest: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (
        UniqueConstraint("date", "dish_id", "quantile", "is_backtest", name="uq_forecast"),
    )


class RiskScore(Base):
    __tablename__ = "risk_score"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[dt.date] = mapped_column(Date, index=True)
    batch_id: Mapped[str] = mapped_column(ForeignKey("batch.id"), index=True)
    rsl_days: Mapped[float] = mapped_column(Float)
    risk_pct: Mapped[float] = mapped_column(Float)
    value_at_risk_inr: Mapped[float] = mapped_column(Float)
    co2e_at_risk_kg: Mapped[float] = mapped_column(Float)

    batch: Mapped[Batch] = relationship(lazy="joined")

    __table_args__ = (UniqueConstraint("date", "batch_id", name="uq_risk_date_batch"),)


class Recommendation(Base):
    """One card on a screen. Everything the UI renders comes from here."""

    __tablename__ = "recommendation"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    date: Mapped[dt.date] = mapped_column(Date, index=True)
    horizon: Mapped[str] = mapped_column(String(10), index=True)  # PREVENT|PRESERVE|RECOVER
    action_kind: Mapped[str] = mapped_column(String(30))
    title: Mapped[str] = mapped_column(String(160))
    subject_id: Mapped[str] = mapped_column(String(60))  # dish id or batch id
    subject_name: Mapped[str] = mapped_column(String(120))

    current_qty: Mapped[float | None] = mapped_column(Float, nullable=True)
    recommended_qty: Mapped[float | None] = mapped_column(Float, nullable=True)
    qty_unit: Mapped[str] = mapped_column(String(20), default="portions")

    saving_inr: Mapped[float] = mapped_column(Float, default=0.0)
    saving_kg: Mapped[float] = mapped_column(Float, default=0.0)
    saving_co2e_kg: Mapped[float] = mapped_column(Float, default=0.0)

    confidence: Mapped[float] = mapped_column(Float, default=0.7)
    why: Mapped[list] = mapped_column(JSON, default=list)
    lambda_used: Mapped[float] = mapped_column(Float)
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(20), default="open")  # open|accepted|overridden
    channel_id: Mapped[str | None] = mapped_column(ForeignKey("channel.id"), nullable=True)

    outcomes: Mapped[list["RecommendationOutcome"]] = relationship(
        back_populates="recommendation", cascade="all, delete-orphan", lazy="selectin"
    )


class RecommendationOutcome(Base):
    """Accept or override. An override is information, not a failure."""

    __tablename__ = "recommendation_outcome"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recommendation_id: Mapped[str] = mapped_column(ForeignKey("recommendation.id"))
    status: Mapped[str] = mapped_column(String(20))  # accepted|overridden
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    override_qty: Mapped[float | None] = mapped_column(Float, nullable=True)
    ts: Mapped[dt.datetime] = mapped_column(DateTime)

    recommendation: Mapped[Recommendation] = relationship(back_populates="outcomes")


ALL_TABLES = (
    ShelfLifeProfile, StorageZone, Product, Recipe, RecipeLine, Channel,
    Batch, InventoryEvent, SalesRecord, ProductionRecord, DemandContext,
    WasteEvent, ZoneTemperature, Forecast, RiskScore, Recommendation,
    RecommendationOutcome,
)
