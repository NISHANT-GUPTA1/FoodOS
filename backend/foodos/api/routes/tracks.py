"""Track 2 and Track 3 — the proof that the platform claim is real.

Both endpoints call the same optimiser the kitchen uses. If either one ever
needs its own scoring logic, the "one engine, three tracks" claim has stopped
being true and the pitch has to change.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from foodos.api.deps import SessionDep
from foodos.api.schemas import TrackOut
from foodos.engine import tracks as track_engine
from foodos.engine.context import default_context
from foodos.config import settings
from foodos.schema.enums import SiteType
from foodos.schema.tables import Site

router = APIRouter(prefix="/api/tracks", tags=["tracks"])


def _site_of_type(session, site_type: SiteType) -> tuple[Site, bool]:
    """Return (site, is_exact).

    A's dataset is a single kitchen, so a store or plant site often does not
    exist. Rather than 404 and break C's screen mid-demo, fall back to the
    first site and say so — the point of these endpoints is that the same
    engine runs a different action space, and that holds whatever the site is
    labelled.
    """
    site = session.scalars(
        select(Site).where(Site.type == site_type).order_by(Site.id).limit(1)
    ).first()
    if site is not None:
        return site, True

    fallback = session.scalars(select(Site).order_by(Site.id).limit(1)).first()
    if fallback is None:
        raise HTTPException(
            503, "database is empty — run `python -m foodos.ingest.seed`"
        )
    return fallback, False


# 10 ---------------------------------------------------------------- RETAIL
@router.get("/retail", response_model=TrackOut, summary="Track 2 — shelf life")
def retail(session: SessionDep) -> TrackOut:
    site, exact = _site_of_type(session, SiteType.STORE)
    ctx = default_context(site.id, settings.demo_today)
    note = (
        "Identical build_batch_decisions() as the kitchen, pointed at a store "
        "site. No new decision logic."
    )
    if not exact:
        note += (
            f" This dataset has no store site, so the retail action space is "
            f"running against '{site.name}'."
        )
    return TrackOut(
        track="retail",
        site_id=site.id,
        site_name=site.name,
        rows=track_engine.retail_view(session, ctx),
        note=note,
    )


# 11 ------------------------------------------------------------ PRODUCTION
@router.get("/production", response_model=TrackOut, summary="Track 3 — production")
def production(session: SessionDep) -> TrackOut:
    site, exact = _site_of_type(session, SiteType.PLANT)
    ctx = default_context(site.id, settings.demo_today)
    note = (
        "Same newsvendor as the kitchen. The only addition is that candidate "
        "quantities are restricted to whole lots, each carrying a changeover "
        "cost."
    )
    if not exact:
        note += (
            f" This dataset has no plant site, so the production action space "
            f"is running against '{site.name}'."
        )
    return TrackOut(
        track="production",
        site_id=site.id,
        site_name=site.name,
        rows=track_engine.production_view(session, ctx),
        note=note,
    )
