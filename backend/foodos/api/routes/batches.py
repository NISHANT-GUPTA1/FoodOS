"""The agri batch surface — Contract 2b, all eleven endpoints.

FoodOS-Team-Split-v2.md §4, H17-26. Additive: the eleven kitchen endpoints are
untouched and `tests/test_engine/` proves it on every run.

Field names here match `frontend/src/api/batchContract.ts` exactly. C
transcribed the contract into TypeScript and built four screens against it, so
this module is a projection onto that shape rather than a fresh opinion about
it. Where D's content and C's contract disagree on a key, the adaptation
happens here — not in the frontend, and not by editing D's YAML.

Everything A owns is wrapped: an A outage degrades a number, it never 500s a
screen (§4, H21-26).
"""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select

from foodos import content
from foodos.api.deps import ContextDep, SessionDep
from foodos.config import DATA_DIR
from foodos.engine import agriplan
from foodos.schema import (
    BatchAssessment,
    CandidatePlan,
    Confidence,
    Consignment,
    LossRiskScore,
    Organization,
    RiskLevel,
    ShipmentJourney,
)

router = APIRouter(prefix="/api", tags=["batches"])

PHOTO_DIR = DATA_DIR / "photos"

#: Contract 2b: 3-5 photos. Not required — a batch with none still scores.
PHOTOS_EXPECTED = 3


# --------------------------------------------------------------------------
# request bodies
# --------------------------------------------------------------------------


class CreateBatchRequest(BaseModel):
    commodity: str = "tomato"
    qty_kg: float
    origin: str
    destination: str
    transport: str = "open_truck"
    packaging: str = "ventilated_plastic_crate"
    depart_at: datetime | None = None
    answers: dict = Field(default_factory=dict)


class SplitAllocation(BaseModel):
    mandi: str
    qty_kg: float


class SimulateRequest(BaseModel):
    departure_shift_hours: float = 0.0
    transport: str | None = None
    destinations: list[SplitAllocation] = Field(default_factory=list)


class OverrideRequest(BaseModel):
    reason: str = ""


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------


def _get(session, code: str) -> Consignment:
    row = session.scalar(select(Consignment).where(Consignment.code == code))
    if row is None:
        raise HTTPException(status_code=404, detail=f"no consignment {code}")
    return row


def _risk_level(loss_pct: float) -> RiskLevel:
    """Bands drive Screen 1's grouping and C's colour tokens."""
    if loss_pct >= 15.0:
        return RiskLevel.HIGH
    if loss_pct >= 7.0:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


def _subject_for(row: Consignment) -> agriplan.TransitSubject:
    answers = row.assessment.answers if row.assessment else {}
    journey = row.journey
    return agriplan.subject_from(
        consignment_id=row.id,
        code=row.code,
        commodity=row.commodity,
        qty_kg=row.qty_kg,
        origin=row.origin,
        destination=row.destination,
        transport=journey.transport if journey else "open_truck",
        packaging=journey.packaging if journey else "ventilated_plastic_crate",
        answers=answers,
    )


def _score_batch(session, row: Consignment, ctx) -> tuple[LossRiskScore, list[dict]]:
    """Run A's model, rank the plans, persist both. Idempotent per call.

    Everything A owns sits behind `agriplan`, which already falls back to a
    deterministic estimate. `model_run_id` stays null on a fallback, which is
    how the UI tells a prediction from a placeholder.
    """
    subject = _subject_for(row)
    ranked = agriplan.plan(subject, ctx)
    rows = agriplan.as_rows(ranked, subject)

    loss_pct = subject.baseline_loss_pct
    best = next((r for r in rows if r["is_best"]), None)
    degraded = any(r.get("degraded") for r in rows)

    score = row.risk or LossRiskScore(consignment_id=row.id)
    score.loss_pct = round(loss_pct, 2)
    score.loss_kg = round(row.qty_kg * loss_pct / 100.0, 1)
    score.rul_hours = _rul_hours(subject)
    score.level = _risk_level(loss_pct)
    score.confidence = Confidence.LOW if degraded else Confidence.HIGH
    score.model_run_id = None if degraded else "agri.predict"
    score.drivers = _drivers(subject)
    low, high = _band(subject)
    score.low, score.high = low, high

    if row.risk is None:
        session.add(score)
    # Drop the pointer before the rows it points at. LossRiskScore.best_plan_id
    # is a real FK into candidate_plan, so deleting the old plans while it still
    # references one of them fails the constraint — which is what a re-score
    # after a photo upload does.
    score.best_plan_id = None
    session.flush()

    session.query(CandidatePlan).filter(
        CandidatePlan.loss_risk_score_id == score.id
    ).delete()
    session.flush()

    persisted = []
    for item in rows:
        plan = CandidatePlan(
            loss_risk_score_id=score.id,
            label=item["label"],
            action_type=item["action_type"],
            horizon=item["horizon"],
            action_params=item["action_params"],
            loss_pct=item["loss_pct"],
            loss_kg=item["loss_kg"],
            logistics_cost=item["logistics_cost"],
            gross_revenue=item["gross_revenue"],
            net_value=item["net_value"],
            delta_vs_baseline=item["delta_vs_baseline"],
            is_baseline=item["is_baseline"],
            is_best=item["is_best"],
            feasible=item["feasible"],
            exclusion_reason=item["exclusion_reason"],
            terms=item["terms"],
        )
        session.add(plan)
        persisted.append(plan)
    session.flush()

    for plan, item in zip(persisted, rows, strict=True):
        item["id"] = plan.id
        if item["is_best"]:
            score.best_plan_id = plan.id

    row.quality_score = _quality(subject)
    row.status = "assessed"
    session.flush()
    return score, rows


def _rul_hours(subject) -> float:
    try:
        from foodos.agri.predict import run  # noqa: PLC0415
        from foodos.agri.commodity import TOMATO  # noqa: PLC0415

        return round(float(run(dict(subject.base), TOMATO)["rul_hours_at_dispatch"]), 1)
    except Exception:
        return 31.0


def _quality(subject) -> float | None:
    try:
        from foodos.agri.predict import run  # noqa: PLC0415
        from foodos.agri.commodity import TOMATO  # noqa: PLC0415

        return round(float(run(dict(subject.base), TOMATO)["quality_score"]), 1)
    except Exception:
        return None


def _band(subject) -> tuple[float | None, float | None]:
    """A's quantile band. Null when A is unreachable — Contract 2b is explicit
    that a missing band means a fallback scored the row, and the UI must not
    fabricate an interval around a point estimate."""
    try:
        from foodos.agri.predict import predict  # noqa: PLC0415
        from foodos.agri.commodity import TOMATO  # noqa: PLC0415

        bi = predict(dict(subject.base), TOMATO, mc_draws=300, with_sensitivity=False)
        return round(bi.loss_low_pct, 2), round(bi.loss_high_pct, 2)
    except Exception:
        return None, None


def _drivers(subject) -> list[dict]:
    """A's ranked contributions. May be [] — Screen 3 hides the block."""
    try:
        from foodos.agri.predict import predict  # noqa: PLC0415
        from foodos.agri.commodity import TOMATO  # noqa: PLC0415

        bi = predict(dict(subject.base), TOMATO, mc_draws=200, with_sensitivity=False)
        total = sum(abs(d.loss_reduction_pp) for d in bi.drivers) or 1.0
        return [
            {
                "name": d.field,
                "contribution": round(abs(d.loss_reduction_pp) / total, 3),
                "text": d.label,
            }
            for d in bi.drivers
        ]
    except Exception:
        return []


def _profile(row: Consignment) -> dict:
    score, journey = row.risk, row.journey
    assessment = row.assessment
    return {
        "id": row.code,
        "commodity": row.commodity,
        "qty_kg": row.qty_kg,
        "origin": row.origin,
        "destination": row.destination,
        "harvested_at": row.harvested_at.isoformat() if row.harvested_at else None,
        "transport": journey.transport if journey else "open_truck",
        "packaging": journey.packaging if journey else "ventilated_plastic_crate",
        "state": {
            "quality_score": row.quality_score,
            "grade": row.grade,
            "maturity": row.maturity,
            "damage_factor": row.damage_factor,
            "field_heat_hours_over_30c": row.field_heat_hours_over_30c,
        },
        "risk": {
            "loss_pct": score.loss_pct if score else 0.0,
            "loss_kg": score.loss_kg if score else 0.0,
            "low": score.low if score else None,
            "high": score.high if score else None,
            "rul_hours": score.rul_hours if score else 0.0,
            "level": (score.level if score else RiskLevel.LOW),
            "confidence": (score.confidence if score else Confidence.LOW),
        },
        "drivers": score.drivers if score else [],
        "best_plan_id": score.best_plan_id if score else None,
        "recommendation": None,
        "model_run_id": score.model_run_id if score else None,
        "source": "snapshot",
        "vision_confidence": (
            assessment.photo_confidence if assessment and assessment.photo_confidence else "LOW"
        ),
    }


# --------------------------------------------------------------------------
# 1 — questionnaire
# --------------------------------------------------------------------------


@router.get("/questionnaire")
def questionnaire(commodity: str = Query("tomato")) -> dict:
    """D's adaptive tree, projected into the step/question shape C renders.

    D's YAML keeps the questions in one flat list and the steps reference them
    by id in a `fields` array. C's contract wants each step to carry its own
    `questions`. Joining the two is this layer's job — C never hardcodes a
    question, and D's file stays the single source.
    """
    try:
        tree = content.questionnaire(commodity)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"no questionnaire for {commodity}") from exc

    by_id = {q["id"]: q for q in tree.get("questions", [])}
    steps = []
    for step in tree.get("steps", []):
        questions = []
        for field_id in step.get("fields", []):
            q = by_id.get(field_id)
            if not q:
                continue
            questions.append(
                {
                    "id": q["id"],
                    "prompt": q.get("prompt", ""),
                    "help": q.get("help"),
                    # D says "choice"; C's QuestionKind says "single".
                    "kind": {"choice": "single"}.get(q.get("type"), q.get("type", "text")),
                    "feature_key": q.get("feature_key", q["id"]),
                    "options": q.get("options"),
                    "unit": q.get("unit"),
                    "min": q.get("min"),
                    "max": q.get("max"),
                    "step": q.get("step"),
                    "default": q.get("default"),
                    "required": q.get("required", False),
                    "show_if": q.get("show_if"),
                }
            )
        steps.append(
            {
                "id": step["id"],
                "title": step.get("title", ""),
                "subtitle": step.get("subtitle", ""),
                "questions": questions,
            }
        )

    return {
        "commodity": commodity,
        "version": str(tree.get("version", "1")),
        "target_seconds": int(tree.get("estimated_seconds", 30)),
        "steps": steps,
        "source": "snapshot",
    }


# --------------------------------------------------------------------------
# 2 / 3 — create, photos
# --------------------------------------------------------------------------


@router.post("/batches", status_code=201)
def create_batch(body: CreateBatchRequest, session: SessionDep, ctx: ContextDep) -> dict:
    org = session.scalar(select(Organization))
    code = _next_code(session, body.commodity)

    row = Consignment(
        code=code,
        org_id=org.id if org else 1,
        commodity=body.commodity,
        qty_kg=body.qty_kg,
        origin=body.origin,
        destination=body.destination,
        harvested_at=datetime.now(timezone.utc),
        status="registered",
        field_heat_hours_over_30c=_as_float(body.answers.get("field_heat_hours_over_30c")),
        maturity=_maturity_band(body.answers.get("maturity_stage")),
        damage_factor=body.answers.get("damage_level"),
    )
    session.add(row)
    session.flush()

    session.add(BatchAssessment(consignment_id=row.id, answers=body.answers))
    session.add(
        ShipmentJourney(
            consignment_id=row.id,
            transport=body.transport,
            packaging=body.packaging,
            depart_at=body.depart_at or datetime.now(timezone.utc),
        )
    )
    session.flush()
    session.refresh(row)

    _score_batch(session, row, ctx)
    session.commit()
    return {"id": row.code, "status": row.status, "photos_expected": PHOTOS_EXPECTED}


@router.post("/batches/{code}/photos")
def upload_photos(
    code: str, session: SessionDep, ctx: ContextDep, files: list[UploadFile] = File(default=[])
) -> dict:
    """Store 3-5 photos and re-score with A's vision features.

    Photos are optional at every step. Zero photos returns LOW confidence and a
    scored batch, never an error — the upload endpoint existing is not the same
    as the upload being required.
    """
    row = _get(session, code)
    PHOTO_DIR.mkdir(parents=True, exist_ok=True)

    paths = []
    for index, upload in enumerate(files):
        target = PHOTO_DIR / f"{code}_{index}{Path(upload.filename or '').suffix or '.jpg'}"
        with target.open("wb") as handle:
            shutil.copyfileobj(upload.file, handle)
        paths.append(str(target))

    assessment = row.assessment or BatchAssessment(consignment_id=row.id)
    assessment.photo_paths = paths
    assessment.photo_features, confidence = _photo_features(paths, row.commodity)
    assessment.photo_confidence = confidence
    if row.assessment is None:
        session.add(assessment)
    session.flush()
    session.refresh(row)

    _score_batch(session, row, ctx)
    session.commit()
    return {"batch_id": code, "accepted": len(paths), "vision_confidence": confidence}


def _photo_features(paths: list[str], commodity: str) -> tuple[dict, str]:
    """A's CV layer, behind a fallback. Contract 1 puts this in cv/inference.py."""
    if not paths:
        return {}, Confidence.LOW
    try:
        from foodos.cv.inference import extract_photo_features  # noqa: PLC0415

        out = extract_photo_features(paths, commodity)
        return out, out.get("confidence", Confidence.MEDIUM)
    except Exception:
        return {}, Confidence.LOW


# --------------------------------------------------------------------------
# 4 / 5 / 6 — list, profile, plans
# --------------------------------------------------------------------------


@router.get("/batches")
def list_batches(
    session: SessionDep,
    status: str | None = Query(None),
    risk: str | None = Query(None),
) -> dict:
    rows = session.scalars(select(Consignment).order_by(Consignment.id)).all()
    counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    out = []

    for row in rows:
        score = row.risk
        level = str(score.level) if score else "LOW"
        counts[level] = counts.get(level, 0) + 1
        if status and row.status != status:
            continue
        if risk and level != risk:
            continue

        best = None
        if score:
            best = next((p for p in score.plans if p.is_best), None)
        out.append(
            {
                "id": row.code,
                "commodity": row.commodity,
                "qty_kg": row.qty_kg,
                "origin": row.origin,
                "destination": row.destination,
                "rul_hours": score.rul_hours if score else 0.0,
                "loss_pct": score.loss_pct if score else 0.0,
                "loss_kg": score.loss_kg if score else 0.0,
                "level": level,
                "status": row.status,
                "best_action": best.label if best else "Not yet assessed",
                "best_plan_id": best.id if best else 0,
                "delta_vs_baseline": best.delta_vs_baseline if best else 0.0,
            }
        )

    return {
        "batches": out,
        "counts": counts,
        "source": "snapshot",
        "as_of": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/batches/{code}")
def get_batch(code: str, session: SessionDep) -> dict:
    return _profile(_get(session, code))


@router.get("/batches/{code}/plans")
def get_plans(code: str, session: SessionDep, ctx: ContextDep) -> dict:
    row = _get(session, code)
    if row.risk is None or not row.risk.plans:
        _score_batch(session, row, ctx)
        session.commit()
        session.refresh(row)

    score = row.risk
    plans = sorted(score.plans, key=lambda p: (not p.feasible, -p.net_value))
    baseline = next((p for p in plans if p.is_baseline), None)
    best = next((p for p in plans if p.is_best), None)

    return {
        "batch_id": code,
        "baseline_plan_id": baseline.id if baseline else 0,
        "best_plan_id": best.id if best else 0,
        "w_preserve": ctx.lam,
        "model_run_id": score.model_run_id,
        "plans": [_plan_row(p) for p in plans],
    }


def _plan_row(plan: CandidatePlan) -> dict:
    return {
        "id": plan.id,
        "label": plan.label,
        "loss_pct": plan.loss_pct,
        "loss_kg": plan.loss_kg,
        "logistics_cost": plan.logistics_cost,
        "gross_revenue": plan.gross_revenue,
        "net_value": plan.net_value,
        "delta_vs_baseline": plan.delta_vs_baseline,
        "is_baseline": plan.is_baseline,
        "is_best": plan.is_best,
        "feasible": plan.feasible,
        "exclusion_reason": plan.exclusion_reason,
        "terms": plan.terms,
        "horizon": plan.horizon,
    }


# --------------------------------------------------------------------------
# 7 — simulate
# --------------------------------------------------------------------------


@router.post("/batches/{code}/simulate")
def simulate(code: str, body: SimulateRequest, session: SessionDep, ctx: ContextDep) -> dict:
    """Screen 4. The same plan object, through the same `score()`.

    Not a similar code path — the identical one. If the simulator and the
    recommendation ever disagree on stage, one of them is a second objective
    function and the pitch is fiction.
    """
    row = _get(session, code)
    subject = _subject_for(row)

    allocations = [a.model_dump() for a in body.destinations]
    if allocations:
        total = sum(a["qty_kg"] for a in allocations)
        if abs(total - row.qty_kg) > 1.0:
            raise HTTPException(
                status_code=422,
                detail=f"allocations total {total:,.0f} kg against a {row.qty_kg:,.0f} kg load",
            )

    from foodos.engine import transit  # noqa: PLC0415
    from foodos.engine.optimiser import rank  # noqa: PLC0415

    if allocations and len(allocations) > 1:
        action = transit.split_batch(subject, allocations)
    elif body.transport and body.transport != subject.transport:
        action = transit.upgrade_transport(subject, body.transport)
    elif body.departure_shift_hours:
        action = transit.depart_earlier(subject, body.departure_shift_hours)
    else:
        action = transit.do_nothing(subject)

    ranked = rank([transit.do_nothing(subject), action], ctx)
    rows = agriplan.as_rows(ranked, subject)
    chosen = next(
        (r for r in rows if r["action_type"] == action.action_type.value), rows[0]
    )
    chosen["rul_hours"] = _rul_hours(subject)
    chosen["note"] = "Simulated — not persisted."
    return chosen


# --------------------------------------------------------------------------
# 8 / 9 — accept, override
# --------------------------------------------------------------------------


@router.post("/plans/{plan_id}/accept")
def accept_plan(plan_id: int, session: SessionDep) -> dict:
    return _outcome(session, plan_id, "accepted", "")


@router.post("/plans/{plan_id}/override")
def override_plan(plan_id: int, body: OverrideRequest, session: SessionDep) -> dict:
    return _outcome(session, plan_id, "overridden", body.reason)


def _outcome(session, plan_id: int, outcome: str, reason: str) -> dict:
    plan = session.get(CandidatePlan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail=f"no plan {plan_id}")
    plan.action_params = {**(plan.action_params or {}), "outcome": outcome, "reason": reason}
    session.commit()
    return {
        "plan_id": plan_id,
        "outcome": outcome,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "reason": reason or None,
    }


# --------------------------------------------------------------------------
# 10 — markets
# --------------------------------------------------------------------------


@router.get("/markets")
def markets(
    session: SessionDep, commodity: str = Query("tomato"), near: str = Query("")
) -> dict:
    """Destination price context. `source` is never hidden — Ruling 3."""
    from foodos.external import agmarknet  # noqa: PLC0415

    rows = []
    for key, mandi in content.mandis().items():
        price, trend = 0.0, "flat"
        try:
            ref = agmarknet.latest_for(session, mandi.get("agmarknet_key", ""), None)
            if ref:
                price = float(getattr(ref, "modal_price_per_kg", 0.0) or 0.0)
        except Exception:
            price = 0.0
        rows.append(
            {
                "mandi": key,
                "name": mandi.get("display_name", key),
                "distance_km": float(mandi.get("distance_km", 0.0)),
                "transit_hours": float(mandi.get("typical_transit_hours", 0.0)),
                "price_per_kg": round(price, 2),
                "daily_absorption_kg": float(mandi.get("daily_absorption_kg", 0.0)),
                "trend": trend,
            }
        )

    return {
        "commodity": commodity,
        "near": near,
        "as_of": datetime.now(timezone.utc).isoformat(),
        "source": "snapshot",
        "markets": rows,
    }


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------


def _next_code(session, commodity: str) -> str:
    prefix = (commodity[:1] or "B").upper()
    count = session.query(Consignment).count()
    return f"{prefix}{1024 + count + 1}"


def _as_float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _maturity_band(stage) -> str | None:
    """D's horticultural ladder onto Contract 2b's three-value wire band.

    A and D speak in ripening stages (mature_green ... red); the contract
    freezes low/medium/high. Mapped here rather than in either of their files.
    """
    if not stage:
        return None
    return {
        "mature_green": "low",
        "breaker": "low",
        "turning": "medium",
        "pink": "medium",
        "light_red": "high",
        "red": "high",
    }.get(str(stage))
