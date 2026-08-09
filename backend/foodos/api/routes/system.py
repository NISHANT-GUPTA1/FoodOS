"""Health and ingestion."""

from __future__ import annotations

import shutil
import tempfile
from datetime import timedelta
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile
from sqlalchemy import func, select

from foodos import __version__
from foodos.api.deps import ContextDep, SessionDep
from foodos.api.schemas import HealthOut, IngestOut, SiteOut
from foodos.config import settings
from foodos.engine import recommendation
from foodos.ingest import loader
from foodos.schema.tables import Product, Site

router = APIRouter(prefix="/api", tags=["system"])

ALLOWED_SUFFIXES = {".csv"}


@router.get("/health", response_model=HealthOut, summary="Status and sites")
def health(session: SessionDep) -> HealthOut:
    sites = list(session.scalars(select(Site).order_by(Site.id)))
    seeded = bool(session.scalar(select(func.count(Product.id))))
    return HealthOut(
        version=__version__,
        demo_today=settings.demo_today,
        default_site_id=sites[0].id if sites else None,
        sites=[SiteOut(id=s.id, name=s.name, type=str(s.type)) for s in sites],
        seeded=seeded,
    )


@router.post("/ingest/upload", response_model=IngestOut, summary="Upload CSVs")
async def upload(
    session: SessionDep, ctx: ContextDep, files: list[UploadFile]
) -> IngestOut:
    """Ingest a set of CSVs into a **fresh** organisation.

    Demo note: this appends a new org and sites rather than wiping the
    database, so an upload during the demo can never destroy the seeded state.
    Use `python -m foodos.ingest.seed` to start clean.
    """
    accepted: list[str] = []
    tmp = Path(tempfile.mkdtemp(prefix="foodos-upload-"))
    try:
        for upload_file in files:
            name = Path(upload_file.filename or "").name
            if Path(name).suffix.lower() not in ALLOWED_SUFFIXES:
                continue
            target = tmp / name
            with target.open("wb") as fh:
                shutil.copyfileobj(upload_file.file, fh)
            accepted.append(name)

        if not accepted:
            raise HTTPException(400, "no .csv files in the upload")

        report = loader.load_all(session, tmp, settings.demo_today)
        site_id = report.get("default_site_id") or ctx.site_id
        rows = recommendation.generate(
            session,
            ctx.__class__(**{**ctx.__dict__, "site_id": site_id}),
            target=settings.demo_today + timedelta(days=1),
        )
        session.commit()
        return IngestOut(
            accepted_files=accepted,
            report=report,
            recommendations_generated=len(rows),
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
