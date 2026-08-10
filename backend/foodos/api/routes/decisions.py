"""Recommendation lifecycle endpoints.

An override is a signal, not a failure — the reason is stored and handed back
to A as a feature the model missed.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from foodos.api.deps import ContextDep, SessionDep
from foodos.api.schemas import Money, OverrideIn, RecommendationOut
from foodos.engine import recommendation
from foodos.schema.tables import Recommendation

router = APIRouter(prefix="/api/recommendations", tags=["decisions"])


def _out(rec: Recommendation) -> RecommendationOut:
    return RecommendationOut(
        id=rec.id,
        horizon=str(rec.horizon),
        subject_type=rec.subject_type,
        subject_id=rec.subject_id,
        subject_label=rec.subject_label,
        action_type=rec.action_type,
        action_params=rec.action_params or {},
        baseline_value=rec.baseline_value,
        recommended_value=rec.recommended_value,
        saves=Money(
            kg=rec.expected_saving_kg,
            money=rec.expected_saving_money,
            co2e=rec.expected_co2e,
        ),
        confidence=str(rec.confidence),
        rationale_text=rec.rationale_text,
        rationale_facts=rec.rationale_facts or {},
        status=str(rec.status),
        override_reason=rec.override_reason,
        override_value=rec.override_value,
        expires_at=rec.expires_at.isoformat() if rec.expires_at else None,
    )


# 8 ----------------------------------------------------------------- ACCEPT
@router.post("/{recommendation_id}/accept", response_model=RecommendationOut)
def accept(recommendation_id: int, session: SessionDep) -> RecommendationOut:
    try:
        rec = recommendation.accept(session, recommendation_id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    session.commit()
    return _out(rec)


# 9 --------------------------------------------------------------- OVERRIDE
@router.post("/{recommendation_id}/override", response_model=RecommendationOut)
def override(
    recommendation_id: int, payload: OverrideIn, session: SessionDep
) -> RecommendationOut:
    try:
        rec = recommendation.override(
            session, recommendation_id, payload.reason, payload.value
        )
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    session.commit()
    return _out(rec)


# ------------------------------------------------------------- regenerate
@router.post("/regenerate", response_model=list[RecommendationOut])
def regenerate(session: SessionDep, ctx: ContextDep) -> list[RecommendationOut]:
    """Rebuild the pending set — used after an upload or a lambda change."""
    rows = recommendation.generate(session, ctx)
    session.commit()
    return [_out(r) for r in rows]
