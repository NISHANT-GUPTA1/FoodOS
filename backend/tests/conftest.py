"""Test fixtures.

The database URL is set *before* `foodos.db` is imported, so tests never touch
the developer's foodos.db.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

_TMP = Path(tempfile.mkdtemp(prefix="foodos-tests-"))
os.environ.setdefault("FOODOS_DATABASE_URL", f"sqlite:///{(_TMP / 'test.db').as_posix()}")
os.environ.setdefault("FOODOS_DEMO_TODAY", "2026-02-12")

from sqlalchemy import select  # noqa: E402

from foodos.config import settings  # noqa: E402
from foodos.db import SessionLocal, create_all, drop_all  # noqa: E402
from foodos.engine.context import default_context  # noqa: E402
from foodos.ingest import channels, sample_data  # noqa: E402
from foodos.schema.enums import SiteType  # noqa: E402
from foodos.schema.tables import Organization, Site  # noqa: E402


@pytest.fixture(scope="session")
def seeded_db():
    """B's own fixture, not A's data — so the engine tests stay green even
    while A is mid-regeneration."""
    drop_all()
    create_all()
    session = SessionLocal()
    try:
        sample_data.build(session, settings.demo_today)
        org = session.scalars(select(Organization).limit(1)).first()
        channels.load(session, org.id)
        session.commit()
    finally:
        session.close()
    yield
    drop_all()


@pytest.fixture
def session(seeded_db):
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


def _site(session, site_type: SiteType) -> Site:
    return (
        session.query(Site).filter(Site.type == site_type).order_by(Site.id).first()
    )


@pytest.fixture
def kitchen(session) -> Site:
    return _site(session, SiteType.KITCHEN)


@pytest.fixture
def store(session) -> Site:
    return _site(session, SiteType.STORE)


@pytest.fixture
def plant(session) -> Site:
    return _site(session, SiteType.PLANT)


@pytest.fixture
def ctx(kitchen):
    return default_context(kitchen.id, settings.demo_today)
