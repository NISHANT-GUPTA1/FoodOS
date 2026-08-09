"""Shared FastAPI dependencies."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from foodos.config import settings
from foodos.db import get_session
from foodos.engine.context import DecisionContext, default_context
from foodos.schema.tables import Site

SessionDep = Annotated[Session, Depends(get_session)]


def resolve_site(session: Session, site_id: int | None) -> Site:
    if site_id is not None:
        site = session.get(Site, site_id)
        if site is None:
            raise HTTPException(404, f"site {site_id} not found")
        return site
    site = session.scalars(select(Site).order_by(Site.id).limit(1)).first()
    if site is None:
        raise HTTPException(
            503, "database is empty — run `python -m foodos.ingest.seed`"
        )
    return site


def get_context(
    session: SessionDep,
    site_id: Annotated[int | None, Query(description="defaults to the first site")] = None,
    lam: Annotated[
        float | None,
        Query(
            ge=0.0,
            le=5.0,
            alias="lambda",
            description=(
                "Sustainability weight. 0 = pure profit. Moves C_o, which moves "
                "q*, which moves every quantity in the plan."
            ),
        ),
    ] = None,
    today: Annotated[date | None, Query(description="override the demo clock")] = None,
) -> DecisionContext:
    site = resolve_site(session, site_id)
    ctx = default_context(site.id, today or settings.demo_today)
    return ctx.with_lambda(lam)


ContextDep = Annotated[DecisionContext, Depends(get_context)]
