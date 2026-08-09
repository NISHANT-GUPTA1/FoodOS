"""Recommendations: building them, and the accept/override lifecycle.

A Recommendation is the only thing the UI renders. Whatever horizon produced it, it has
the same shape — a title, a quantity change, what it saves in three units, why, and a
confidence. That uniformity is not cosmetic: it is what lets one card component show a
production cut, a tray move and a B2B transfer without the operator having to learn three
mental models.

An override is not a failure. It is the operator telling us something the model does not
know, and the acceptance rate on the Impact screen is only worth reporting because
overriding is a first-class action rather than a way of dismissing a nag.

Owner: Person B.
"""

from __future__ import annotations

import datetime as dt
import hashlib

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import get_config
from ..schema import Recommendation, RecommendationOutcome

HORIZON_PREVENT = "PREVENT"
HORIZON_PRESERVE = "PRESERVE"
HORIZON_RECOVER = "RECOVER"


def make_id(*parts: object) -> str:
    """Deterministic id, so reseeding does not invalidate a screenshot in the deck."""
    digest = hashlib.sha1("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()
    return f"rec_{digest[:12]}"


def confidence_from_spread(median: float, spread: float) -> float:
    """Wide forecast, low confidence. Reported next to the card, never inside the sentence.

    Coefficient of variation mapped onto a 0.45-0.95 band. A dish selling four portions a
    day is never going to earn high confidence, and pretending otherwise would be the most
    obvious lie in the product.
    """
    if median <= 0:
        return 0.45
    cv = spread / median
    return round(min(0.95, max(0.45, 0.95 - cv)), 2)


def build(
    *,
    date: dt.date,
    horizon: str,
    action_kind: str,
    title: str,
    subject_id: str,
    subject_name: str,
    saving_inr: float,
    saving_kg: float = 0.0,
    saving_co2e_kg: float = 0.0,
    lambda_used: float,
    why: list[dict],
    confidence: float = 0.7,
    current_qty: float | None = None,
    recommended_qty: float | None = None,
    qty_unit: str = "portions",
    channel_id: str | None = None,
    expires_at: dt.datetime | None = None,
) -> Recommendation:
    config = get_config()
    return Recommendation(
        id=make_id(date, horizon, subject_id, action_kind, round(lambda_used, 3)),
        date=date,
        horizon=horizon,
        action_kind=action_kind,
        title=title,
        subject_id=subject_id,
        subject_name=subject_name,
        current_qty=current_qty,
        recommended_qty=recommended_qty,
        qty_unit=qty_unit,
        saving_inr=round(saving_inr, 2),
        saving_kg=round(saving_kg, 3),
        saving_co2e_kg=round(saving_co2e_kg, 3),
        confidence=confidence,
        why=why,
        lambda_used=round(lambda_used, 3),
        expires_at=expires_at
        or dt.datetime.combine(date, dt.time(11, 30))
        + dt.timedelta(hours=config.recommendation_ttl_hours),
        status="open",
        channel_id=channel_id,
    )


def persist(session: Session, recommendations: list[Recommendation]) -> list[Recommendation]:
    """Upsert by id, preserving any accept/override already recorded against it.

    Reseeding or changing λ must not silently discard an operator's decision — that is how
    a system quietly loses the audit trail it is claiming to provide.
    """
    stored: list[Recommendation] = []
    for rec in recommendations:
        existing = session.get(Recommendation, rec.id)
        if existing is None:
            session.add(rec)
            stored.append(rec)
            continue
        for field in (
            "title", "saving_inr", "saving_kg", "saving_co2e_kg", "confidence",
            "why", "current_qty", "recommended_qty", "expires_at", "lambda_used",
        ):
            setattr(existing, field, getattr(rec, field))
        stored.append(existing)
    session.flush()
    return stored


# --- lifecycle ---------------------------------------------------------------

class RecommendationNotFound(Exception):
    pass


def accept(session: Session, rec_id: str, *, note: str | None = None, now: dt.datetime | None = None) -> Recommendation:
    rec = session.get(Recommendation, rec_id)
    if rec is None:
        raise RecommendationNotFound(rec_id)
    rec.status = "accepted"
    session.add(
        RecommendationOutcome(
            recommendation_id=rec.id,
            status="accepted",
            reason=note,
            ts=now or dt.datetime.now(),
        )
    )
    session.flush()
    return rec


def override(
    session: Session,
    rec_id: str,
    *,
    reason: str,
    override_qty: float | None = None,
    now: dt.datetime | None = None,
) -> Recommendation:
    rec = session.get(Recommendation, rec_id)
    if rec is None:
        raise RecommendationNotFound(rec_id)
    rec.status = "overridden"
    session.add(
        RecommendationOutcome(
            recommendation_id=rec.id,
            status="overridden",
            reason=reason,
            override_qty=override_qty,
            ts=now or dt.datetime.now(),
        )
    )
    session.flush()
    return rec


def acceptance_rate(session: Session) -> float:
    """Accepted as a share of everything decided. Open cards are not counted either way."""
    decided = session.scalar(
        select(func.count(Recommendation.id)).where(Recommendation.status != "open")
    ) or 0
    if decided == 0:
        return 0.0
    accepted = session.scalar(
        select(func.count(Recommendation.id)).where(Recommendation.status == "accepted")
    ) or 0
    return round(100.0 * accepted / decided, 1)


def counts(session: Session) -> tuple[int, int]:
    shown = session.scalar(select(func.count(Recommendation.id))) or 0
    accepted = session.scalar(
        select(func.count(Recommendation.id)).where(Recommendation.status == "accepted")
    ) or 0
    return shown, accepted


def realised_saving(session: Session) -> float:
    """Only what was accepted. A saving we recommended and the kitchen declined is not ours."""
    total = session.scalar(
        select(func.sum(Recommendation.saving_inr)).where(Recommendation.status == "accepted")
    )
    return round(float(total or 0.0), 2)
