"""Candidate plan assembly for a consignment — §4, H13-17.

Order of assembly, and it matters:

  1. the baseline, always, so every delta has something to be measured against
  2. A's agent proposals, when the orchestrator has landed
  3. a deterministic sweep — departure shifts, transport upgrades, the nearest
     mandis, one split

Then `optimiser.rank()` scores the lot. **Excluded plans are returned with their
reason, never filtered** (§4): a hidden option looks like the engine never
considered it, which is the opposite of what the matrix is for.

There is no scoring in this file. Building candidates and ranking them are
different jobs, and `rank()` already exists.
"""

from __future__ import annotations

from foodos import content
from foodos.engine import transit
from foodos.engine.actions import Action
from foodos.engine.context import DecisionContext
from foodos.engine.optimiser import RankedActions, rank
from foodos.engine.transit import TransitSubject

#: Departure shifts offered by the sweep, in hours. Negative is earlier.
DEPARTURE_SHIFTS = (-6.0, -12.0)

#: How many alternative mandis the sweep reroutes to.
REROUTE_CANDIDATES = 3


def _mandi_key_for(destination: str) -> str | None:
    """Match a free-text destination back to a key in D's mandis.yaml."""
    for key, row in content.mandis().items():
        if destination in (key, row.get("display_name")):
            return key
    return None


def subject_from(
    *,
    consignment_id: int,
    code: str,
    commodity: str,
    qty_kg: float,
    origin: str,
    destination: str,
    transport: str,
    packaging: str,
    answers: dict | None = None,
    price_per_kg: float = transit.DEFAULT_PRICE_PER_KG,
) -> TransitSubject:
    """Assemble the value object both the planner and the simulator run on.

    `base` is A's ScenarioBatch input. Answers from D's questionnaire are mapped
    onto it by `feature_key`; anything the farmer did not answer falls back to
    the commodity defaults, because §3 is explicit that a batch with no photos
    and no weather must still score.
    """
    answers = answers or {}
    mandi_key = _mandi_key_for(destination)
    mandi = content.mandis().get(mandi_key or "", {})
    transit_hours = float(mandi.get("typical_transit_hours", 24.0))
    distance_km = float(mandi.get("distance_km", 0.0))

    def answer(key: str, default):
        value = answers.get(key, default)
        return default if value in (None, "") else value

    base = {
        "quantity_kg": float(qty_kg),
        "harvest_method": str(answer("harvest_method", "manual")),
        "harvest_window": str(answer("harvest_window", "early_morning")),
        "field_holding": str(answer("post_harvest_shade", "shade")),
        "field_hours": float(answer("field_heat_hours_over_30c", 4.0)),
        "packaging": str(answer("packaging_type", packaging)),
        "transport_mode": str(answer("transport_mode", transport)),
        "transit_hours": transit_hours,
        "mandi_holding_hours": float(answer("yard_hold_hours", 6.0)),
        "maturity_factor": float(answer("maturity_factor", 1.0)),
        "visual_damage_fraction": float(answer("visual_damage_fraction", 0.03)),
        "ambient_mean_c": float(answer("ambient_mean_c", 29.0)),
        "diurnal_amplitude_c": float(answer("diurnal_amplitude_c", 9.0)),
        "road_roughness": float(answer("road_roughness", 1.4)),
    }

    return TransitSubject(
        consignment_id=consignment_id,
        code=code,
        commodity=commodity,
        qty_kg=float(qty_kg),
        origin=origin,
        destination=destination,
        transport=transport,
        packaging=packaging,
        transit_hours=transit_hours,
        distance_km=distance_km,
        price_per_kg=price_per_kg,
        base=base,
        baseline_loss_pct=baseline_loss_pct(base),
    )


def baseline_loss_pct(base: dict) -> float:
    """What A's model says happens if nothing changes.

    Every action's saving is measured against this one number, so it is computed
    once and carried on the subject rather than recomputed per builder. Falls
    back to a flat estimate when A is unreachable — degraded, never absent.
    """
    try:
        from foodos.agri.predict import run  # noqa: PLC0415 — optional at import
        from foodos.agri.commodity import TOMATO  # noqa: PLC0415

        return float(run(dict(base), TOMATO)["total_loss"]) * 100.0
    except Exception:
        return 8.4


def candidates(
    subject: TransitSubject, proposals: list[dict] | None = None
) -> list[Action]:
    """Baseline, then A's proposals, then the deterministic sweep."""
    actions: list[Action] = [transit.do_nothing(subject)]

    # --- A's agent proposals ------------------------------------------------
    # Contract 1: the orchestrator returns action PARAMETERS only, never rupees.
    # B converts each into an Action and scores it; the agents never rank.
    for proposal in proposals or []:
        built = _from_proposal(subject, proposal)
        if built is not None:
            actions.append(built)

    # --- deterministic sweep ------------------------------------------------
    for hours in DEPARTURE_SHIFTS:
        actions.append(transit.depart_earlier(subject, hours))

    for mode in content.transport_modes():
        if mode != subject.transport:
            actions.append(transit.upgrade_transport(subject, mode))

    here = _mandi_key_for(subject.destination)
    nearer = sorted(
        (
            (key, row)
            for key, row in content.mandis().items()
            if key != here and row.get("typical_transit_hours")
        ),
        key=lambda kv: float(kv[1]["typical_transit_hours"]),
    )[:REROUTE_CANDIDATES]
    for key, _row in nearer:
        actions.append(transit.reroute(subject, key))

    if nearer and here:
        half = round(subject.qty_kg * 0.6)
        actions.append(
            transit.split_batch(
                subject,
                [
                    {"mandi": here, "qty_kg": half},
                    {"mandi": nearer[0][0], "qty_kg": subject.qty_kg - half},
                ],
            )
        )

    for channel in content.agri_channels():
        if channel.get("horizon") == "RECOVER" and channel.get("recovery_factor"):
            actions.append(transit.divert_to_channel(subject, channel))

    return actions


def _from_proposal(subject: TransitSubject, proposal: dict) -> Action | None:
    """Turn one of A's parameter dicts into a scored-able Action."""
    kind = proposal.get("kind")
    try:
        if kind == "depart_earlier":
            return transit.depart_earlier(subject, float(proposal["departure_shift_hours"]))
        if kind == "upgrade_transport":
            return transit.upgrade_transport(subject, str(proposal["transport"]))
        if kind == "reroute":
            return transit.reroute(subject, str(proposal["mandi"]))
        if kind == "split_batch":
            return transit.split_batch(subject, list(proposal["destinations"]))
    except (KeyError, TypeError, ValueError):
        return None
    return None


def plan(
    subject: TransitSubject, ctx: DecisionContext, proposals: list[dict] | None = None
) -> RankedActions:
    """The whole H13-17 job: assemble, then rank through the one `score()`."""
    return rank(candidates(subject, proposals), ctx)


def as_rows(ranked: RankedActions, subject: TransitSubject) -> list[dict]:
    """Project the ranked actions into Contract 2b's plan rows.

    Feasible first, best row flagged, excluded rows appended with their reason
    so the matrix greys them rather than dropping them. `id` is the row's index
    here and is replaced by the database key once the plans are persisted.
    """
    baseline = ranked.baseline
    baseline_value = baseline.value if baseline else 0.0
    rows: list[dict] = []

    for index, scored in enumerate(list(ranked.ranked) + list(ranked.excluded)):
        action = scored.action
        loss_pct = float(action.facts.get("loss_pct", 0.0))
        surviving_kg = float(action.facts.get("arriving_kg", 0.0))
        price = float(action.facts.get("price_per_kg", subject.price_per_kg))

        rows.append(
            {
                "id": index,
                "label": action.label,
                "action_type": action.action_type.value,
                "horizon": action.horizon.value,
                "action_params": action.params,
                "loss_pct": round(loss_pct, 2),
                "loss_kg": round(subject.qty_kg * loss_pct / 100.0, 1),
                "logistics_cost": round(action.cost, 2),
                "gross_revenue": round(action.recovered_value, 2),
                "net_value": round(scored.value, 2),
                "delta_vs_baseline": round(scored.value - baseline_value, 2),
                "is_baseline": action.is_baseline,
                "is_best": scored is ranked.best,
                "feasible": scored.feasible,
                "exclusion_reason": scored.exclusion_reason,
                "degraded": bool(action.facts.get("degraded", False)),
                # Every term of V(a), in the field names C's PlanTerms expects,
                # so no number in the matrix is unattributable.
                "terms": {
                    "expected_price_per_kg": round(price, 2),
                    "surviving_kg": round(surviving_kg, 1),
                    "gross_revenue": round(action.recovered_value, 2),
                    "logistics_cost": round(action.cost, 2),
                    "loss_cost": round(scored.terms.get("expected_loss", 0.0), 2),
                    "diversion_cost": round(
                        action.cost if action.channel_id else 0.0, 2
                    ),
                    "mass_penalty": round(scored.terms.get("sustainability", 0.0), 2),
                    "w_preserve": ctx_lam(scored),
                    "ranking_value": round(scored.value, 2),
                },
            }
        )
    return rows


def ctx_lam(scored) -> float:
    """The lambda actually used, read back off the scored terms.

    Taken from the score rather than the request so the response can never
    claim a weight the ranking did not use.
    """
    sustainability = scored.terms.get("sustainability", 0.0)
    kg = scored.action.kg_food_saved or 0.0
    if not kg:
        return 0.0
    return round(sustainability / kg, 4)
