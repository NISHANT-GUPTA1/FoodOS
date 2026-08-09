"""Canonical schema: SQLAlchemy tables, Pydantic DTOs, and the session factory.

Owner: Person B.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from ..config import DATA_DIR, get_config
from .tables import (
    ALL_TABLES,
    Base,
    Batch,
    Channel,
    DemandContext,
    Forecast,
    InventoryEvent,
    Product,
    ProductionRecord,
    Recipe,
    RecipeLine,
    Recommendation,
    RecommendationOutcome,
    RiskScore,
    SalesRecord,
    ShelfLifeProfile,
    StorageZone,
    WasteEvent,
    ZoneTemperature,
)

_engine = None
_Session: sessionmaker[Session] | None = None


def get_engine():
    global _engine, _Session
    if _engine is None:
        config = get_config()
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(config.db_url, future=True)
        _Session = sessionmaker(bind=_engine, expire_on_commit=False, future=True)
    return _engine


def get_sessionmaker() -> sessionmaker[Session]:
    get_engine()
    assert _Session is not None
    return _Session


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transaction boundary. Commits on success, rolls back on anything else."""
    factory = get_sessionmaker()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_session() -> Iterator[Session]:
    """FastAPI dependency."""
    factory = get_sessionmaker()
    session = factory()
    try:
        yield session
    finally:
        session.close()


def create_all() -> None:
    Base.metadata.create_all(get_engine())


def drop_all() -> None:
    Base.metadata.drop_all(get_engine())


def reset_engine() -> None:
    """Force the next call to rebuild the engine. Used by the seed and by tests."""
    global _engine, _Session
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _Session = None


__all__ = [
    "ALL_TABLES", "Base", "Batch", "Channel", "DemandContext", "Forecast",
    "InventoryEvent", "Product", "ProductionRecord", "Recipe", "RecipeLine",
    "Recommendation", "RecommendationOutcome", "RiskScore", "SalesRecord",
    "ShelfLifeProfile", "StorageZone", "WasteEvent", "ZoneTemperature",
    "create_all", "drop_all", "get_engine", "get_session", "get_sessionmaker",
    "reset_engine", "session_scope",
]
