"""Deterministic Q10 shelf-life kinetics.

**Boundary with A:** this is the physics half only — arithmetic, no fitting, no
training data. A owns the learned residual correction and overwrites
`Batch.rsl_days` with the calibrated value. B ships this so the Ledger is never
empty and the engine is never blocked.

    k(T)   = k_ref * Q10 ^ ((T - T_ref) / 10)
    dLife  = (dt / base_shelf_life) * Q10 ^ ((T - T_ref) / 10)
    RSL    = base_shelf_life * (1 - sum(dLife)) * g_intake * g_handling * g_cut

Never described as "AI freshness detection". Every factor is a stated
assumption a chef can argue with, which is the point.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

CUT_STATE_FACTOR = {"whole": 1.0, "cut": 0.35, "prepared": 0.25}


@dataclass(frozen=True)
class ShelfLifeInputs:
    base_shelf_life_days: float
    ref_temp_c: float
    q10: float
    received_at: datetime
    as_of: datetime
    storage_temp_c: float
    intake_grade: float = 1.0
    state: str = "whole"
    handling_factor: float = 1.0
    # Optional temperature excursion: (hours, temperature).
    excursion_hours: float = 0.0
    excursion_temp_c: float | None = None


def decay_rate(temp_c: float, ref_temp_c: float, q10: float) -> float:
    """How many days of reference-temperature life one real day consumes."""
    return float(q10 ** ((temp_c - ref_temp_c) / 10.0))


def estimate(inp: ShelfLifeInputs) -> tuple[float, str]:
    """Return (remaining shelf life in days, a sentence explaining it)."""
    total_hours = max(
        (inp.as_of - inp.received_at).total_seconds() / 3600.0, 0.0
    )
    excursion_hours = min(inp.excursion_hours, total_hours)
    normal_hours = total_hours - excursion_hours

    base = max(inp.base_shelf_life_days, 1e-6)
    rate_normal = decay_rate(inp.storage_temp_c, inp.ref_temp_c, inp.q10)
    life_used = (normal_hours / 24.0 / base) * rate_normal

    excursion_note = ""
    if excursion_hours > 0 and inp.excursion_temp_c is not None:
        rate_exc = decay_rate(inp.excursion_temp_c, inp.ref_temp_c, inp.q10)
        used_exc = (excursion_hours / 24.0 / base) * rate_exc
        life_used += used_exc
        excursion_note = (
            f" {excursion_hours:.0f} h at {inp.excursion_temp_c:.0f} C cost "
            f"{used_exc * base:.1f} days of life."
        )

    remaining_fraction = max(1.0 - life_used, 0.0)
    g_cut = CUT_STATE_FACTOR.get(str(inp.state), 1.0)
    rsl = base * remaining_fraction * inp.intake_grade * inp.handling_factor * g_cut

    explanation = (
        f"Base shelf life {base:.1f} d at {inp.ref_temp_c:.0f} C. "
        f"Held at {inp.storage_temp_c:.0f} C for {normal_hours / 24.0:.1f} d "
        f"(Q10 {inp.q10:.1f}, decay x{rate_normal:.2f})."
        f"{excursion_note}"
        f" Intake grade {inp.intake_grade:.2f}, state '{inp.state}' (x{g_cut:.2f})."
        f" Remaining: {rsl:.1f} days."
    )
    return round(max(rsl, 0.0), 2), explanation


def printed_expiry_days(printed: date | None, as_of: date) -> float | None:
    """What the label claims — kept alongside RSL so the gap is visible."""
    return None if printed is None else float((printed - as_of).days)
