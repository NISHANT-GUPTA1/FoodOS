"""Remaining Shelf Life.

RSL is not ``expiry_date - today``. The same paneer in a 4 degC walk-in and a 9 degC
under-counter chiller are two different assets, and only one of them survives service.

The model, in full:

    temp_factor = q10 ** ((actual_temp_c - ref_temp_c) / 10)
    life_days   = base_shelf_life_days / temp_factor
    life_days  *= cut_life_factor      if the batch has been cut or portioned
    life_days  *= ethylene_penalty     if sensitive and co-stored with a producer
    rsl_days    = life_days - age_days

Q10 is the standard rule from food microbiology: how many times faster spoilage runs per
10 degC rise. The constants live in content/shelf_life.yaml, not here — this file owns the
arithmetic and nothing else.

Owner: Person A.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class Profile(Protocol):
    """Structural type — satisfied by the ShelfLifeProfile table and by a plain object."""

    base_shelf_life_days: float
    ref_temp_c: float
    q10: float
    cut_life_factor: float
    ethylene_sensitive: bool


DEFAULT_ETHYLENE_PENALTY = 0.70


def temp_factor(q10: float, ref_temp_c: float, actual_temp_c: float) -> float:
    """How many times faster this product decays at ``actual_temp_c`` than at reference.

    Greater than one means faster. A freezer returns a value well under one, which is the
    whole reason frozen peas are not on the ledger.
    """
    return float(q10 ** ((actual_temp_c - ref_temp_c) / 10.0))


def shelf_life_days(
    profile: Profile,
    actual_temp_c: float,
    *,
    is_cut: bool = False,
    ethylene_exposed: bool = False,
    ethylene_penalty: float = DEFAULT_ETHYLENE_PENALTY,
) -> float:
    """Total life this batch has from the moment it was received, at this temperature."""
    factor = temp_factor(profile.q10, profile.ref_temp_c, actual_temp_c)
    life = profile.base_shelf_life_days / factor
    if is_cut:
        life *= profile.cut_life_factor
    if ethylene_exposed and profile.ethylene_sensitive:
        life *= ethylene_penalty
    return max(0.0, life)


def remaining_shelf_life(
    profile: Profile,
    actual_temp_c: float,
    age_days: float,
    *,
    is_cut: bool = False,
    ethylene_exposed: bool = False,
    ethylene_penalty: float = DEFAULT_ETHYLENE_PENALTY,
) -> float:
    """Days of usable life left. Never negative — a batch past its life is simply at zero."""
    life = shelf_life_days(
        profile,
        actual_temp_c,
        is_cut=is_cut,
        ethylene_exposed=ethylene_exposed,
        ethylene_penalty=ethylene_penalty,
    )
    return max(0.0, life - age_days)


def life_gain_from_rezone(
    profile: Profile,
    from_temp_c: float,
    to_temp_c: float,
    age_days: float,
    **kwargs,
) -> float:
    """Days bought by moving a batch to a colder zone. Costs nothing, which is the point."""
    before = remaining_shelf_life(profile, from_temp_c, age_days, **kwargs)
    after = remaining_shelf_life(profile, to_temp_c, age_days, **kwargs)
    return max(0.0, after - before)


@dataclass(frozen=True)
class RiskAssessment:
    rsl_days: float
    days_to_consume: float
    risk_pct: float
    qty_at_risk_kg: float
    value_at_risk_inr: float
    co2e_at_risk_kg: float


def assess_risk(
    *,
    rsl_days: float,
    qty_kg: float,
    daily_usage_kg: float,
    unit_cost_per_kg: float,
    co2e_per_kg: float,
) -> RiskAssessment:
    """How much of this batch will still be sitting there when its life runs out.

    A batch is not "at risk" because it is old. It is at risk because the kitchen cannot
    get through it in time. Four kilograms of paneer with a day of life is a crisis if the
    kitchen uses two kilograms a day, and a non-event if it uses six.

        days_to_consume = qty / daily_usage
        risk            = (days_to_consume - rsl) / days_to_consume, clamped to [0, 1]

    The risk fraction is literally the share of the batch still on hand at expiry, which
    is why multiplying it by the batch value gives a number an accountant would accept.
    """
    if qty_kg <= 0:
        return RiskAssessment(rsl_days, 0.0, 0.0, 0.0, 0.0, 0.0)

    usage = max(daily_usage_kg, 1e-6)
    days_to_consume = qty_kg / usage

    if days_to_consume <= 0:
        risk = 0.0
    else:
        risk = (days_to_consume - rsl_days) / days_to_consume
    risk = min(1.0, max(0.0, risk))

    qty_at_risk = qty_kg * risk
    return RiskAssessment(
        rsl_days=rsl_days,
        days_to_consume=days_to_consume,
        risk_pct=risk * 100.0,
        qty_at_risk_kg=qty_at_risk,
        value_at_risk_inr=qty_at_risk * unit_cost_per_kg,
        co2e_at_risk_kg=qty_at_risk * co2e_per_kg,
    )


def severity(rsl_days: float, *, critical: float = 1.0, warning: float = 2.5) -> str:
    if rsl_days <= critical:
        return "critical"
    if rsl_days <= warning:
        return "warning"
    return "fine"
