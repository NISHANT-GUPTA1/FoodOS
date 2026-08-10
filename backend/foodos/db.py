"""Database engine and session handling."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from foodos.config import settings
from foodos.schema import Base

_connect_args = (
    {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
)

engine: Engine = create_engine(
    settings.database_url, connect_args=_connect_args, future=True
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@event.listens_for(Engine, "connect")
def _enable_sqlite_fk(dbapi_connection, _record) -> None:
    """SQLite ignores foreign keys unless asked nicely."""
    if settings.database_url.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def create_all() -> None:
    Base.metadata.create_all(engine)


def drop_all() -> None:
    """Drop every table, cycles included.

    `loss_risk_score.best_plan_id` and `candidate_plan.loss_risk_score_id`
    reference each other, so there is no ordering that satisfies both. Postgres
    would take a DROP CONSTRAINT; SQLite has no ALTER for that, so the only way
    through is to stop enforcing keys for the duration of the drop. Re-enabled
    immediately after, and scoped to one connection — nothing else sees it.
    """
    with engine.begin() as connection:
        is_sqlite = connection.dialect.name == "sqlite"
        if is_sqlite:
            connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
        Base.metadata.drop_all(connection)
        if is_sqlite:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional scope for scripts and tests."""
    session = SessionLocal()
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
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
