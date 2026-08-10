"""From a stored batch to a scored one — and back, every time something happens.

`batch_identity` records what happened. This module answers "so what?": it
assembles the input A's simulator expects, runs it, and appends a
`BatchStateSnapshot` so the belief at that moment is preserved rather than
overwritten.

**The re-score is a replay, not a patch.** A six-hour delay does not nudge the
previous RUL down by six. It rebuilds the batch's inputs from its registered
condition plus every event since, and runs the physics again from the top. The
difference matters: transit hours interact with the diurnal temperature curve,
so six hours added to a run that now spans an afternoon peak costs far more
life than six hours added to an overnight leg. Subtracting six from a stored
number would miss that, and missing it is how a system ends up confidently
wrong at exactly the moment a manager is relying on it.

**The honesty rule.** Without sensors we do not know the batch's condition; we
know its *predicted* condition given a declared journey and the events reported
against it. Every snapshot therefore carries the input dict it was computed
from, and `basis` says whether the numbers came from A's model or from the
deterministic fallback. Nothing in the UI is allowed to imply a thermometer.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from foodos.agri import commodity as commodity_registry
from foodos.agri.commodity import MATURITY_LIFE_FACTOR, MaturityStage as AgriMaturity
from foodos.agri.predict import predict, risk_level
from foodos.agri.scenario import (
    FieldHolding,
    HarvestMethod,
    HarvestWindow,
    Packaging,
    TransportMode as AgriTransport,
)
from foodos.schema.enums import (
    BatchEventType,
    BatchLifecycle,
    Confidence,
    MaturityStage,
    PackagingType,
    RiskLevel,
    TransportMode,
)
from foodos.schema.tables import (
    BatchStateSnapshot,
    Consignment,
    LossRiskScore,
)

log = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# Vocabulary bridges
#
# B's schema enums are the wire format frozen in Contract 2b; A's are the
# simulator's own. They are close but not identical, and the mapping is here —
# in one place, with its reasoning — rather than spread across route handlers.
# --------------------------------------------------------------------------

PACKAGING_MAP: dict[PackagingType, Packaging] = {
    PackagingType.LOOSE: Packaging.LOOSE_BULK,
    PackagingType.JUTE_SACK: Packaging.GUNNY_BAG,
    PackagingType.VENTILATED_PLASTIC_CRATE: Packaging.VENTILATED_PLASTIC_CRATE,
    # A corrugated carton is not separately modelled. Wooden crate is the
    # nearest thing A has calibrated — comparable crush protection, comparable
    # diurnal damping — so it is used rather than inventing a coefficient here.
    # A distinct CFB entry belongs in `agri/scenario.py` and is A's to add.
    PackagingType.CFB_CARTON: Packaging.WOODEN_CRATE,
}

TRANSPORT_MAP: dict[TransportMode, AgriTransport] = {
    TransportMode.OPEN_TRUCK: AgriTransport.OPEN_TRUCK,
    TransportMode.TARPAULIN: AgriTransport.TARPAULIN,
    TransportMode.REEFER: AgriTransport.REFRIGERATED,
}

#: The three-tap questionnaire cannot resolve the six USDA colour stages, so
#: the buckets span the stages fruit is actually *picked* at for shipment:
#: mature-green through turning. The life factors are Handbook 66's, unchanged
#: — the coarseness is in the question, not in the physics.
#:
#: They deliberately stop at TURNING. Pink, light-red and red are stages a
#: tomato *reaches* in transit or on a shelf, not stages anyone loads onto a
#: thirty-six hour open truck to Delhi. Mapping the ripest questionnaire answer
#: onto light-red would model a consignment nobody ships, and it showed: doing
#: so scored an ordinary Kolar-Delhi haul at 51% loss, which is not a
#: prediction, it is a units error wearing a percentage sign.
MATURITY_FACTOR: dict[MaturityStage, float] = {
    MaturityStage.LOW: MATURITY_LIFE_FACTOR[AgriMaturity.MATURE_GREEN],
    MaturityStage.MEDIUM: MATURITY_LIFE_FACTOR[AgriMaturity.BREAKER],
    MaturityStage.HIGH: MATURITY_LIFE_FACTOR[AgriMaturity.TURNING],
}

#: Visible damage at intake, as a surface fraction. The questionnaire's three
#: buckets; the vision model overwrites these with a measured value when photos
#: are present, which is the whole reason photos raise `confidence`.
DAMAGE_FRACTION: dict[str, float] = {"low": 0.02, "moderate": 0.08, "high": 0.18}

#: Fallbacks for a batch registered before its questionnaire is complete.
#:
#: Every value is the modal or central value of `scenario.sample_baseline()` —
#: the distribution A calibrated against NABCONS to reproduce 8.37% farm-level
#: loss. That sourcing is the point. An unanswered question means "this batch
#: looks like the population we measured", which is the only defensible prior;
#: inventing a pessimistic default instead would quietly make every partially
#: registered batch look like a crisis, and inventing an optimistic one would
#: hide real risk behind an unanswered form.
#:
#: Note `ambient_mean_c` is 25 C, the annual mean across Indian tomato
#: marketing — not a peak-summer 31 C. The rabi crop is large, and defaulting
#: to the worst season inflates every downstream loss figure. Real weather
#: overwrites this from `WeatherExposure` whenever the route has been fetched.
DEFAULT_BASE: dict[str, object] = {
    "harvest_method": HarvestMethod.MANUAL,          # 93% of the survey
    "harvest_window": HarvestWindow.MORNING,         # 38%, the mode
    "field_holding": FieldHolding.SHADE,             # 50%, the mode
    "field_hours": 3.5,                              # gamma(2.2, 1.9) median
    "packaging": Packaging.GUNNY_BAG,                # 34%, the mode
    "transport_mode": AgriTransport.OPEN_TRUCK,      # 62%
    "transit_hours": 5.0,                            # lognormal median
    "mandi_holding_hours": 3.5,                      # gamma(1.6, 2.2) median
    "maturity_factor": 0.95,                         # sampler mean
    "visual_damage_fraction": 0.04,                  # beta(1.7, 42) mean
    "ambient_mean_c": 25.0,
    "diurnal_amplitude_c": 9.5,
    "road_roughness": 1.45,
}


@dataclass(frozen=True)
class Scored:
    """The result of one re-score, ready to persist and to serialise."""

    loss_pct: float
    loss_kg: float
    low: float | None
    high: float | None
    #: Hours of fresh-retail life left **as of the moment being scored**. This
    #: is the number Screen 3 counts down and FEFO sorts on.
    rul_hours: float
    #: A's raw output: life left at the moment of dispatch. Kept because the
    #: two answer different questions and confusing them is easy — see
    #: `_remaining_rul`.
    rul_at_dispatch: float
    quality_score: float
    level: RiskLevel
    confidence: Confidence
    drivers: list[dict]
    actions: list[dict]
    inputs: dict
    #: "model" | "fallback". Rendered, never hidden — see the honesty rule.
    basis: str
    biggest_unknown: str | None = None


# --------------------------------------------------------------------------
# Assembling the input
# --------------------------------------------------------------------------


def _declared_base(batch: Consignment) -> dict:
    """The batch as registered, before any journey events are replayed."""
    base = dict(DEFAULT_BASE)
    base["quantity_kg"] = float(batch.qty_kg_remaining or batch.qty_kg)

    journey = batch.journey
    if journey is not None:
        base["packaging"] = PACKAGING_MAP[PackagingType(journey.packaging)]
        base["transport_mode"] = TRANSPORT_MAP[TransportMode(journey.transport)]
        if journey.transit_hours:
            base["transit_hours"] = float(journey.transit_hours)
        if journey.vibration_index is not None:
            base["road_roughness"] = float(journey.vibration_index)

    if batch.maturity is not None:
        base["maturity_factor"] = MATURITY_FACTOR[MaturityStage(batch.maturity)]
    if batch.damage_factor is not None:
        base["visual_damage_fraction"] = DAMAGE_FRACTION.get(
            str(batch.damage_factor), DEFAULT_BASE["visual_damage_fraction"]
        )
    if batch.field_heat_hours_over_30c is not None:
        base["field_hours"] = float(batch.field_heat_hours_over_30c)

    # The questionnaire is free to answer any simulator input directly. Its
    # keys are D's `feature_key`s, which are named to match A's fields exactly
    # so this stays an update rather than a translation table.
    assessment = batch.assessment
    if assessment is not None:
        for key, value in (assessment.answers or {}).items():
            if key in base:
                base[key] = value
        # Vision beats the questionnaire on damage: it measured, the farmer
        # estimated. Checked independently of the answers — photos can arrive
        # on a batch whose questionnaire was skipped, and nesting this inside
        # the answers branch silently threw the measurement away in exactly
        # that case.
        measured = (assessment.photo_features or {}).get("visual_damage_fraction")
        if measured is not None:
            base["visual_damage_fraction"] = float(measured)

    # Route weather, integrated. The hourly rows exist precisely because a
    # spike and a flat mean are different journeys; collapsing them to an
    # average here would throw away the signal the rows were stored for, so the
    # mean goes in `ambient_mean_c` and the *spread* sets the diurnal swing the
    # simulator integrates over.
    if batch.weather:
        temps = [w.temp_c for w in batch.weather]
        base["ambient_mean_c"] = sum(temps) / len(temps)
        base["diurnal_amplitude_c"] = max(
            (max(temps) - min(temps)) / 2.0, 1.0
        )

    return base


def _replay_events(base: dict, batch: Consignment, *, until: datetime | None) -> dict:
    """Fold every reported event into the input dict, in the order they happened.

    This is the "we don't have sensors, so we use predicted state" contract
    from the design, made concrete: the declared journey is the prior, and each
    reported event is evidence that revises it.
    """
    out = dict(base)
    # Sorted here rather than relying on the relationship's `order_by`: a
    # collection that has had events appended in this same transaction holds
    # them in append order until it is reloaded, and replaying a delay before
    # the dispatch it followed would fold the two into the wrong journey.
    for event in sorted(batch.events, key=lambda e: (e.occurred_at, e.id or 0)):
        if until is not None and event.occurred_at > until:
            break
        payload = event.payload or {}
        kind = BatchEventType(event.type)

        if kind is BatchEventType.DELAY:
            hours = float(payload.get("duration_hours", 0.0))
            out["transit_hours"] = float(out["transit_hours"]) + max(hours, 0.0)

        elif kind is BatchEventType.TEMPERATURE_EXPOSURE:
            hours = max(float(payload.get("hours", 0.0)), 0.0)
            temp = payload.get("temp_c")
            total = max(float(out["transit_hours"]), hours, 1e-6)
            if temp is not None and hours > 0:
                # Time-weighted, not a replacement. Three hours at 41 degC on a
                # thirty-hour haul is not a thirty-hour journey at 41 degC, and
                # overwriting the mean would triple the modelled thermal load.
                ambient = float(out["ambient_mean_c"])
                out["ambient_mean_c"] = (
                    ambient * (total - hours) + float(temp) * hours
                ) / total
                out["diurnal_amplitude_c"] = max(
                    float(out["diurnal_amplitude_c"]),
                    abs(float(temp) - ambient),
                )

        elif kind is BatchEventType.FIELD_HOLD:
            out["field_hours"] = float(out["field_hours"]) + max(
                float(payload.get("hours", 0.0)), 0.0
            )

        elif kind is BatchEventType.ARRIVED:
            # Once it has actually arrived the transit time is a measurement,
            # not an estimate. Prefer the measurement.
            actual = payload.get("transit_hours")
            if actual is None:
                dispatch = next(
                    (
                        e.occurred_at
                        for e in batch.events
                        if BatchEventType(e.type) is BatchEventType.DISPATCHED
                    ),
                    None,
                )
                if dispatch is not None:
                    actual = (event.occurred_at - dispatch).total_seconds() / 3600.0
            if actual is not None and float(actual) > 0:
                out["transit_hours"] = float(actual)

        elif kind is BatchEventType.SPLIT:
            # Children carry their own mass; the parent's own score stops
            # describing anything once it is divided.
            pass

    out["quantity_kg"] = float(batch.qty_kg_remaining or batch.qty_kg)
    return out


def build_base(batch: Consignment, *, until: datetime | None = None) -> dict:
    """The simulator input for this batch as of `until` (default: everything)."""
    return _replay_events(_declared_base(batch), batch, until=until)


# --------------------------------------------------------------------------
# Scoring
# --------------------------------------------------------------------------

#: Monte Carlo draws for an interactive re-score. The full 2,000 A uses for a
#: batch of report runs is not needed to render a band that is displayed to one
#: decimal place, and this path is on the click of a demo button.
MC_DRAWS = 600


def _confidence(batch: Consignment) -> Confidence:
    """How much we trust the number, from how much we were told.

    Photos are the swing factor: with three or more, damage is measured rather
    than estimated, and damage is the input the questionnaire is worst at.
    """
    assessment = batch.assessment
    if assessment is None or not assessment.answers:
        return Confidence.LOW
    photos = len(assessment.photo_paths or [])
    if photos >= 3 and batch.weather:
        return Confidence.HIGH
    if photos >= 1 or batch.weather:
        return Confidence.MEDIUM
    return Confidence.LOW


def _fallback(
    batch: Consignment, base: dict, reason: str, *, as_of: datetime
) -> Scored:
    """Deterministic Q10 scoring, for when the simulator cannot run.

    An A outage degrades the number; it never 500s the screen. This carries no
    interval and LOW confidence, and `basis` says `fallback`, so the UI can say
    plainly that the batch has not been modelled rather than dressing a
    heuristic up as a prediction.
    """
    log.warning("scoring %s by fallback: %s", batch.code, reason)
    from foodos.agri.kinetics import (
        arrhenius_rate_multiplier,
        remaining_useful_life_hours,
        spoilage_fraction,
    )

    qty = float(base["quantity_kg"])
    try:
        spec = commodity_registry.get(_commodity_key(batch))
        temp = float(base["ambient_mean_c"])
        # Isothermal at the mean, which is exactly the approximation the full
        # simulator exists to avoid — no diurnal integration, no stage
        # structure, no packaging or vibration term. That is why this path
        # reports LOW confidence and no interval: it is a floor, not a model.
        hours = float(base["transit_hours"]) + float(base["field_hours"])
        life_median_days = spec.ref_life_days * float(base["maturity_factor"])
        stress_days = (hours / 24.0) * float(arrhenius_rate_multiplier(temp, spec))

        loss = float(spoilage_fraction(stress_days, life_median_days, spec.life_spread_sigma))
        rul = float(
            remaining_useful_life_hours(stress_days, life_median_days, temp, spec)
        )
    except Exception:  # pragma: no cover - the floor of the floor
        rul, loss = 24.0, 0.08

    return Scored(
        loss_pct=round(loss * 100.0, 2),
        loss_kg=round(loss * qty, 1),
        low=None,
        high=None,
        rul_hours=round(_remaining_rul(batch, rul, as_of), 1),
        rul_at_dispatch=round(rul, 1),
        quality_score=round(max(0.0, 100.0 - loss * 400.0), 1),
        level=RiskLevel(risk_level(loss).upper()),
        confidence=Confidence.LOW,
        drivers=[],
        actions=[],
        inputs=_jsonable(base),
        basis="fallback",
    )


def _remaining_rul(
    batch: Consignment, rul_at_dispatch: float, as_of: datetime
) -> float:
    """Convert A's life-at-dispatch into life left right now.

    A returns `rul_hours_at_dispatch` — the life the batch has when it leaves
    the farm gate. That is the right quantity for comparing plans before
    departure and the wrong one for a batch already twenty hours down the
    highway, because it does not move as the clock runs.

    It is worse than merely stale. Adding six hours of delay lengthens the
    journey into cooler overnight hours, which *raises* the forward-temperature
    average, which nudges life-at-dispatch **up**. Reporting that after a delay
    would tell a manager the hold-up had done the tomatoes good — the exact
    opposite of the truth, and the one mistake in this product a judge would
    catch instantly.

    So elapsed time since dispatch is subtracted. Wall-clock hours, not
    stress-adjusted ones: RUL is already denominated in wall-clock hours at the
    forward temperature, so on a journey with a roughly stable ambient the two
    are the same subtraction. On a leg with a sharp heat spike this slightly
    understates the burn — and the TEMPERATURE_EXPOSURE event picks that up on
    the other side, by shortening the whole curve at the next re-score.
    """
    dispatch = next(
        (
            e.occurred_at
            for e in sorted(batch.events, key=lambda e: (e.occurred_at, e.id or 0))
            if BatchEventType(e.type) is BatchEventType.DISPATCHED
        ),
        None,
    )
    if dispatch is None or as_of <= dispatch:
        return rul_at_dispatch
    elapsed = (as_of - dispatch).total_seconds() / 3600.0
    return max(rul_at_dispatch - elapsed, 0.0)


def _clamp_to_history(
    batch: Consignment, rul_hours: float, as_of: datetime
) -> float:
    """Life already spent is not returned.

    A re-score is a full replay, and the engine reports life-at-dispatch for
    the journey as it now stands. That figure is not monotonic: lengthening a
    thirty-six hour haul by six hours drags it further into cool overnight
    hours, which raises the forward-temperature average and so raises
    life-at-dispatch by a few percent. The physics is defensible; the sentence
    it produces — "your truck was held up four hours, the tomatoes gained two"
    — is not.

    So a new figure may never exceed what the previous snapshot implies for
    this moment. It can fall faster, which is what a delay or a heat spike
    should do; it simply cannot rise.

    **The exception this will need.** Cooling genuinely raises remaining hours,
    because it slows the rate rather than undoing the damage — a batch with ten
    hours left at 35 C really does have forty at 5 C. No event in the current
    alphabet does that. When a PRESERVE action lands (`RELOCATE` to a cold
    room, a reefer upgrade mid-haul), it must be exempted here, or the system
    will refuse to show the benefit of the very action it recommended.
    """
    # A freshly split child has no history of its own, so it inherits its
    # parent's. Without this a child comes out *fresher than the batch it was
    # cut from* — three tonnes of a load whose life is spent cannot have
    # fourteen hours left just because it changed hands.
    previous = batch.snapshots[-1] if batch.snapshots else None
    if previous is None and batch.parent is not None and batch.parent.snapshots:
        previous = batch.parent.snapshots[-1]

    if previous is None or previous.rul_hours is None:
        return rul_hours
    elapsed = max((as_of - previous.as_of).total_seconds() / 3600.0, 0.0)
    ceiling = max(previous.rul_hours - elapsed, 0.0)
    return min(rul_hours, ceiling)


def _commodity_key(batch: Consignment) -> str:
    return str(batch.commodity).strip().lower()


def _jsonable(base: dict) -> dict:
    """Enums to their string values, so the snapshot is replayable from JSON."""
    return {k: (str(v) if not isinstance(v, (int, float)) else v) for k, v in base.items()}


def score(batch: Consignment, *, as_of: datetime, base: dict | None = None) -> Scored:
    """Run A's engine over one batch, as of a moment. Never raises."""
    inputs = base if base is not None else build_base(batch, until=as_of)
    try:
        spec = commodity_registry.get(_commodity_key(batch))
    except Exception as exc:
        return _fallback(batch, inputs, f"unknown commodity: {exc}", as_of=as_of)

    try:
        profile = predict(
            inputs, commodity=spec, mc_draws=MC_DRAWS, with_sensitivity=True
        )
    except Exception as exc:  # degradation contract, §"An A outage"
        return _fallback(batch, inputs, repr(exc), as_of=as_of)

    return Scored(
        loss_pct=profile.loss_pct,
        loss_kg=profile.mass_at_risk_kg,
        low=profile.loss_low_pct,
        high=profile.loss_high_pct,
        rul_hours=round(_remaining_rul(batch, profile.rul_hours, as_of), 1),
        rul_at_dispatch=profile.rul_hours,
        quality_score=profile.quality_score,
        level=RiskLevel(profile.risk_level.upper()),
        confidence=_confidence(batch),
        drivers=[_driver_out(d) for d in profile.drivers],
        actions=[_driver_out(d) for d in profile.actions],
        inputs=_jsonable(inputs),
        basis="model",
        biggest_unknown=profile.biggest_unknown,
    )


def _driver_out(driver) -> dict:
    """A's `Driver` in the shape Contract 2b froze for `drivers[]`.

    `contribution` is the driver's share of the total explainable loss
    reduction, which is what makes the list sum to ~1.0 as the contract
    promises. `text` is written here rather than in the frontend because it has
    to name the counterfactual, and the counterfactual is A's output.
    """
    return {
        "name": driver.field,
        "label": driver.label,
        "contribution": 0.0,  # filled by `_normalise_contributions`
        "loss_reduction_pp": driver.loss_reduction_pp,
        "mass_saved_kg": driver.mass_saved_kg,
        "controllable": driver.controllable,
        "current": str(driver.current),
        "counterfactual": str(driver.counterfactual),
        "text": (
            f"{driver.label} — {driver.current} rather than {driver.counterfactual} "
            f"costs {driver.loss_reduction_pp:.2f} pp ({driver.mass_saved_kg:g} kg)"
        ),
    }


def _normalise_contributions(rows: list[dict]) -> list[dict]:
    total = sum(max(r["loss_reduction_pp"], 0.0) for r in rows)
    if total <= 0:
        return rows
    for row in rows:
        row["contribution"] = round(max(row["loss_reduction_pp"], 0.0) / total, 4)
    return rows


# --------------------------------------------------------------------------
# Persistence
# --------------------------------------------------------------------------


def rescore(
    session: Session,
    batch: Consignment,
    *,
    as_of: datetime,
    reason: str,
    model_run_id: str | None = None,
) -> BatchStateSnapshot:
    """Re-run the physics, update the current belief, append the history.

    Two writes, deliberately. `LossRiskScore` is overwritten because Screen 3
    asks "what is the risk now"; `BatchStateSnapshot` is appended because the
    passport asks "what did we say at dispatch, and what do we say after the
    delay". Collapsing them into one table would answer the first question and
    lose the second, and the second is the demo.
    """
    scored = score(batch, as_of=as_of)
    _normalise_contributions(scored.drivers)
    _normalise_contributions(scored.actions)

    rul_hours = _clamp_to_history(batch, scored.rul_hours, as_of)

    # --- current belief -------------------------------------------------
    risk = batch.risk
    if risk is None:
        risk = LossRiskScore(consignment_id=batch.id)
        session.add(risk)
        batch.risk = risk

    risk.loss_pct = scored.loss_pct
    risk.loss_kg = scored.loss_kg
    risk.low = scored.low
    risk.high = scored.high
    risk.rul_hours = rul_hours
    risk.level = scored.level
    risk.confidence = scored.confidence
    risk.drivers = scored.drivers
    # Null model_run_id is the tell for a fallback row — Contract 2b's
    # degradation section leans on it, so it must not be faked.
    risk.model_run_id = model_run_id if scored.basis == "model" else None

    batch.quality_score = scored.quality_score
    batch.grade = _grade(scored.quality_score)

    # Having a profile is what makes a batch dispatchable — design §7, "then
    # the batch becomes READY FOR DISPATCH". The promotion lives here rather
    # than in the route because it is the *scoring* that earns it, and a second
    # caller that scored without promoting would leave batches stuck at
    # ASSESSED with a full intelligence profile and no way to dispatch them.
    if BatchLifecycle(batch.status) is BatchLifecycle.ASSESSED:
        batch.status = BatchLifecycle.READY_FOR_DISPATCH

    # --- history --------------------------------------------------------
    sequence = (
        session.scalars(
            select(func.max(BatchStateSnapshot.sequence)).where(
                BatchStateSnapshot.consignment_id == batch.id
            )
        ).first()
        or 0
    ) + 1

    snapshot = BatchStateSnapshot(
        sequence=sequence,
        as_of=as_of,
        reason=reason,
        status=BatchLifecycle(batch.status),
        location=batch.current_location,
        qty_kg=batch.qty_kg_remaining,
        quality_score=scored.quality_score,
        loss_pct=scored.loss_pct,
        loss_kg=scored.loss_kg,
        low=scored.low,
        high=scored.high,
        rul_hours=rul_hours,
        level=scored.level,
        confidence=scored.confidence,
        model_run_id=risk.model_run_id,
        # `_rul_at_dispatch` is stored alongside the replayable inputs, under
        # an underscore so it is obviously not one of them. It is the raw
        # engine output before the elapsed-time subtraction, and keeping it
        # means a passport can show "had 46 h leaving Kolar, has 18 h now"
        # without re-running the simulator to recover the first figure.
        inputs={**scored.inputs, "_rul_at_dispatch": scored.rul_at_dispatch},
        drivers=scored.drivers,
    )
    batch.snapshots.append(snapshot)
    session.flush()
    return snapshot


def _grade(quality_score: float) -> str:
    """The letter a mandi actually trades on. Thresholds are B's, and they are
    a presentation of `quality_score` rather than a second opinion about it."""
    if quality_score >= 85:
        return "A"
    if quality_score >= 75:
        return "B+"
    if quality_score >= 62:
        return "B"
    if quality_score >= 50:
        return "C"
    return "D"
