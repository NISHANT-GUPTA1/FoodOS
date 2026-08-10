"""The eleven endpoints.

Thin by design. Each one parses a query parameter, calls
:class:`~foodos.engine.service.FoodosService`, and serialises a DTO. If logic starts
appearing in this file it belongs in engine/ instead.

The agent-written sentences on /api/why and /api/rescue are best-effort: if the model is
unreachable or the Verifier blocks the output, the field comes back null and the flag next
to it says so. A screen never fails because a sentence could not be written, and a
sentence is never shown unless it was checked against the computed figures.

Owner: Person B.
"""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..engine import recommendation as rec
from ..engine.optimiser import Objective
from ..engine.service import FoodosService
from ..engine.tracks import production_recommendations, retail_recommendations
from ..schema import Recommendation as RecommendationRow
from ..schema import dto
from .deps import db, lambda_param, service

router = APIRouter(prefix="/api", tags=["foodos"])


# --- serialisation helpers ---------------------------------------------------

def _rec_dto(row: RecommendationRow) -> dto.RecommendationDto:
    return dto.RecommendationDto(
        id=row.id,
        horizon=row.horizon,
        action_kind=row.action_kind,
        title=row.title,
        subject_id=row.subject_id,
        subject_name=row.subject_name,
        current_qty=row.current_qty,
        recommended_qty=row.recommended_qty,
        qty_unit=row.qty_unit,
        saves=dto.Saving(kg=row.saving_kg, inr=row.saving_inr, co2e_kg=row.saving_co2e_kg),
        confidence=row.confidence,
        why=[dto.WhyLine(**line) for line in (row.why or [])],
        expires_at=row.expires_at,
        status=row.status,
        channel_id=row.channel_id,
        lambda_used=row.lambda_used,
    )


def _agent_sentence(agent_name: str, facts) -> tuple[str | None, bool]:
    """Run an agent, or fail quietly. Returns (text, verified).

    Never raises. A blocked or unavailable agent costs us a sentence, not a screen.
    """
    try:
        from ..agents.communicator import Communicator
        from ..agents.diagnostician import Diagnostician
        from ..agents.planner import Planner

        agent = {"diagnostician": Diagnostician, "planner": Planner, "communicator": Communicator}[
            agent_name
        ]()
        output = agent.run(facts)
        return (None, False) if output.blocked else (output.text, True)
    except Exception:
        return None, False


# --- 1. today ----------------------------------------------------------------

@router.get("/today", response_model=dto.TodayResponse)
def today(svc: FoodosService = Depends(service), lam: float = Depends(lambda_param)):
    payload = svc.today(lam)
    return dto.TodayResponse(
        date=payload["date"],
        outlet_name=payload["outlet_name"],
        lambda_used=payload["lambda_used"],
        kpis=dto.TodayKpis(**payload["kpis"]),
        recommendations=[_rec_dto(r) for r in payload["recommendations"]],
    )


# --- 2. why ------------------------------------------------------------------

@router.get("/why", response_model=dto.WhyResponse)
def why(svc: FoodosService = Depends(service)):
    result = svc.attribution()

    root_cause, verified = None, True
    if result.top:
        from ..agents.facts import UNIT_PCT, UNIT_TEXT, Fact, FactSet

        facts = FactSet(
            [
                Fact("top_contributor_name", result.top["name"], UNIT_TEXT, "largest contributor",
                     source="engine:/api/why"),
                Fact("top_contributor_share", result.top["share"], UNIT_PCT,
                     "its share of value at risk", source="engine:/api/why"),
            ]
        )
        root_cause, verified = _agent_sentence("diagnostician", facts)

    return dto.WhyResponse(
        date=result.date,
        value_at_risk_inr=result.value_at_risk_inr,
        kg_at_risk=result.kg_at_risk,
        worst_dish=result.worst_dish,
        worst_dish_name=result.worst_dish_name,
        contributors=[dto.Contributor(**c) for c in result.contributors],
        trim=dto.TrimCallout(
            trim_kg=result.trim_kg,
            trim_value_inr=result.trim_value_inr,
            worst_ingredient=result.worst_ingredient.replace("_", " ").title(),
            worst_ingredient_yield=result.worst_ingredient_yield,
        ),
        root_cause=root_cause,
        root_cause_verified=verified,
    )


# --- 3. plan -----------------------------------------------------------------

@router.get("/plan", response_model=dto.PlanResponse)
def plan(svc: FoodosService = Depends(service), lam: float = Depends(lambda_param)):
    result = svc.plan(lam)
    return dto.PlanResponse(
        date=result.date,
        lambda_used=result.lambda_used,
        lines=[
            dto.PlanLine(
                dish_id=line.dish_id,
                dish_name=line.dish_name,
                station=line.station,
                current_qty=line.current_qty,
                recommended_qty=line.recommended_qty,
                delta=line.delta,
                service_level=line.service_level,
                saving_inr=line.saving_inr,
                saving_kg=line.saving_kg,
                saving_co2e_kg=line.saving_co2e_kg,
            )
            for line in result.lines
        ],
        totals=dto.PlanTotals(
            portions_delta=result.portions_delta,
            saving_inr=result.saving_inr,
            saving_kg=result.saving_kg,
            saving_co2e_kg=result.saving_co2e_kg,
        ),
    )


# --- 4. ledger ---------------------------------------------------------------

@router.get("/ledger", response_model=dto.LedgerResponse)
def ledger(svc: FoodosService = Depends(service)):
    return dto.LedgerResponse(date=svc.date, rows=[dto.LedgerRow(**row) for row in svc.ledger()])


# --- 5. rescue ---------------------------------------------------------------

@router.get("/rescue", response_model=dto.RescueResponse)
def rescue(
    svc: FoodosService = Depends(service),
    lam: float = Depends(lambda_param),
    batch_id: str | None = Query(None, description="Omitted picks the batch most at risk."),
):
    try:
        result = svc.rescue(batch_id, lam)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"no open batch {batch_id!r}") from None

    batch = result.batch
    message, verified = None, True
    best = result.best

    if best is not None and best.channel_id == "b2b_transfer":
        from ..agents.facts import UNIT_DAYS, UNIT_INR, UNIT_KG, UNIT_TEXT, Fact, FactSet

        facts = FactSet(
            [
                Fact("outlet_name", best.counterparty or "the other outlet", UNIT_TEXT,
                     "receiving outlet", source="engine:/api/rescue"),
                Fact("batch_ingredient_name", batch.product.name, UNIT_TEXT,
                     "ingredient being transferred", source="engine:/api/rescue"),
                Fact("batch_qty_kg", round(batch.qty_kg, 1), UNIT_KG, "quantity to transfer",
                     precision=1, source="engine:/api/rescue"),
                Fact("batch_rsl_days", round(result.rsl_days, 1), UNIT_DAYS, "remaining shelf life",
                     precision=1, source="model:rsl"),
                Fact("transfer_value_inr", round(best.value_inr), UNIT_INR,
                     "value recovered by the transfer", source="engine:/api/rescue"),
                Fact("pickup_by", best.pickup_by or "the cut-off", UNIT_TEXT,
                     "collection deadline", source="engine:/api/rescue"),
            ]
        )
        message, verified = _agent_sentence("communicator", facts)

    def _option(o) -> dto.ChannelOption:
        return dto.ChannelOption(
            channel_id=o.channel_id, name=o.name, type=o.type, eligible=o.eligible,
            value_inr=o.value_inr, vs_baseline_inr=o.vs_baseline_inr,
            co2e_avoided_kg=o.co2e_avoided_kg, lead_time_hours=o.lead_time_hours,
            max_qty_kg=o.max_qty_kg, counterparty=o.counterparty, pickup_by=o.pickup_by,
            exclusion_reason_code=o.exclusion_reason_code,
            exclusion_reason=o.exclusion_reason, exclusion_detail=o.exclusion_detail,
        )

    return dto.RescueResponse(
        date=svc.date,
        lambda_used=svc.objective(lam).lambda_,
        batch=dto.RescueBatch(
            id=batch.id,
            product_id=batch.product_id,
            ingredient_name=batch.product.name,
            zone_id=batch.zone_id,
            zone_name=batch.zone.name,
            qty_kg=round(batch.qty_kg, 2),
            rsl_days=round(result.rsl_days, 2),
            state=batch.state,
            value_inr=result.batch_value_inr,
        ),
        channels=[_option(o) for o in result.eligible],
        excluded=[_option(o) for o in result.excluded],
        special=dto.RescueSpecial(**result.special) if result.special else None,
        message=message,
        message_verified=verified,
    )


# --- 6. impact ---------------------------------------------------------------

@router.get("/impact", response_model=dto.ImpactResponse)
def impact(svc: FoodosService = Depends(service)):
    payload = svc.impact()
    return dto.ImpactResponse(
        date=payload["date"],
        series=[dto.BacktestPoint(**point) for point in payload["series"]],
        mae=payload["mae"],
        baseline_mae=payload["baseline_mae"],
        improvement_pct=payload["improvement_pct"],
        acceptance_rate=payload["acceptance_rate"],
        recommendations_shown=payload["recommendations_shown"],
        recommendations_accepted=payload["recommendations_accepted"],
        saving_to_date_inr=payload["saving_to_date_inr"],
    )


# --- 7. simulate -------------------------------------------------------------

@router.get("/simulate", response_model=dto.SimulateResponse)
def simulate(svc: FoodosService = Depends(service), steps: int = Query(11, ge=3, le=21)):
    points, best = svc.simulate(steps)
    return dto.SimulateResponse(
        date=svc.date,
        points=[
            dto.SimulationPoint(
                lambda_value=p.lambda_value,
                saving_inr=p.saving_inr,
                saving_kg=p.saving_kg,
                saving_co2e_kg=p.saving_co2e_kg,
                portions_delta=p.portions_delta,
            )
            for p in points
        ],
        recommended_lambda=best,
    )


# --- 8 and 9. lifecycle ------------------------------------------------------

@router.post("/recommendations/{rec_id}/accept", response_model=dto.OutcomeResponse)
def accept(rec_id: str, body: dto.AcceptRequest | None = None, session: Session = Depends(db)):
    try:
        row = rec.accept(session, rec_id, note=body.note if body else None)
    except rec.RecommendationNotFound:
        raise HTTPException(status_code=404, detail=f"no recommendation {rec_id!r}") from None
    session.commit()
    return dto.OutcomeResponse(id=row.id, status=row.status, acceptance_rate=rec.acceptance_rate(session))


@router.post("/recommendations/{rec_id}/override", response_model=dto.OutcomeResponse)
def override(rec_id: str, body: dto.OverrideRequest, session: Session = Depends(db)):
    try:
        row = rec.override(session, rec_id, reason=body.reason, override_qty=body.override_qty)
    except rec.RecommendationNotFound:
        raise HTTPException(status_code=404, detail=f"no recommendation {rec_id!r}") from None
    session.commit()
    return dto.OutcomeResponse(id=row.id, status=row.status, acceptance_rate=rec.acceptance_rate(session))


# --- 10 and 11. the other two tracks -----------------------------------------

def _track_response(track: str, title: str, description: str, rows: list[dict], lam: float):
    now = dt.datetime.now()
    return dto.TrackResponse(
        track=track,
        title=title,
        description=description,
        lambda_used=lam,
        recommendations=[
            dto.RecommendationDto(
                id=f"{track}_{row['subject_id']}",
                horizon="PREVENT" if track == "production" else "RECOVER",
                action_kind=f"{track}_action",
                title=row["title"],
                subject_id=row["subject_id"],
                subject_name=row["subject_name"],
                current_qty=row["current_qty"],
                recommended_qty=row["recommended_qty"],
                qty_unit=row["qty_unit"],
                saves=dto.Saving(
                    kg=row["saving_kg"], inr=row["saving_inr"], co2e_kg=row["saving_co2e_kg"]
                ),
                confidence=0.8,
                why=[dto.WhyLine(**line) for line in row["why"]],
                expires_at=now + dt.timedelta(hours=12),
                status="open",
                lambda_used=lam,
            )
            for row in rows
        ],
    )


@router.get("/tracks/retail", response_model=dto.TrackResponse)
def track_retail(svc: FoodosService = Depends(service), lam: float = Depends(lambda_param)):
    rows = retail_recommendations(Objective(lam, svc.context.prices), svc.date)
    return _track_response(
        "retail",
        "Retail",
        "Same objective, different actions: markdown timing, shelf facing, store transfer.",
        rows,
        lam,
    )


@router.get("/tracks/production", response_model=dto.TrackResponse)
def track_production(svc: FoodosService = Depends(service), lam: float = Depends(lambda_param)):
    rows = production_recommendations(Objective(lam, svc.context.prices), svc.date)
    return _track_response(
        "production",
        "Production",
        "Same objective, different actions: batch sizing, run sequencing, changeover timing.",
        rows,
        lam,
    )
