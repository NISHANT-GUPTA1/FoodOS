"""Arrhenius deterioration kinetics and the batch loss model.

Two ideas carry this module.

**One.** Deterioration rate follows Arrhenius, expressed relative to a reference
temperature rather than as `A·exp(-Ea/RT)`:

    k_rel(T) = exp( (Ea/R) · (1/T_ref - 1/T) )

Mathematically identical, numerically far better behaved — the pre-exponential
factor `A` for produce respiration is around 1e12, and carrying it around gains
nothing but floating-point noise. `k_rel` is dimensionless and equals 1.0 at the
reference temperature, so "this hour cost 3.7 reference-hours of life" is a
sentence anyone can check.

**Two, and this is the one that makes a loss *percentage* meaningful.** A crate
is not one fruit. It is a population, and the fruit in it do not all fail at the
same moment — a hand-harvested lot spreads roughly three to one between the
first and the last to go. So each fruit carries its own life budget drawn from a
lognormal, and the batch loss fraction is simply the share of that population
whose budget the accumulated thermal stress has already exhausted:

    loss = P(L < S) = Phi( (ln S - ln L_median) / sigma )

A single-value model cannot produce a partial loss at all — it is either fine or
entirely gone — which is why it cannot answer "what does leaving six hours
earlier save?". The distribution is what makes the marginal question answerable,
and the marginal question is the entire product.

No SciPy: the normal CDF is Zelen & Severo, and the inverse comes from stdlib
`statistics`. `pyproject.toml` pins the dependency set deliberately, and this
module does not need to widen it.
"""

from __future__ import annotations

from statistics import NormalDist

import numpy as np

from foodos.agri.commodity import (
    CELSIUS_TO_KELVIN,
    MATURITY_LIFE_FACTOR,
    R_GAS,
    Commodity,
    MaturityStage,
)

# --------------------------------------------------------------------------
# Normal distribution, vectorised, no SciPy
# --------------------------------------------------------------------------

# Abramowitz & Stegun 26.2.17 (Zelen & Severo). |error| < 7.5e-8, which is six
# orders of magnitude tighter than anything the parameters justify.
_AS_P = 0.2316419
_AS_B = (0.319381530, -0.356563782, 1.781477937, -1.821255978, 1.330274429)
_INV_SQRT_2PI = 0.3989422804014327


def norm_cdf(x):
    """Standard normal CDF. Accepts a scalar or an ndarray."""
    x = np.asarray(x, dtype=float)
    ax = np.abs(x)
    t = 1.0 / (1.0 + _AS_P * ax)
    poly = t * (
        _AS_B[0] + t * (_AS_B[1] + t * (_AS_B[2] + t * (_AS_B[3] + t * _AS_B[4])))
    )
    upper_tail = _INV_SQRT_2PI * np.exp(-0.5 * ax * ax) * poly
    return np.where(x >= 0.0, 1.0 - upper_tail, upper_tail)


def norm_ppf(q: float) -> float:
    """Inverse standard normal. Scalar only — it is called on constants."""
    return NormalDist().inv_cdf(q)


# --------------------------------------------------------------------------
# Arrhenius
# --------------------------------------------------------------------------


def arrhenius_rate_multiplier(temp_c, commodity: Commodity):
    """Deterioration rate at `temp_c` as a multiple of the rate at T_ref.

    Returns 1.0 at the reference temperature, above 1 when warmer, below 1 when
    cooler — plus a chilling penalty that turns the curve back upward below the
    commodity's chilling threshold, so nothing in the system can conclude that
    colder is unconditionally better.
    """
    temp_c = np.asarray(temp_c, dtype=float)
    kelvin = temp_c + CELSIUS_TO_KELVIN

    exponent = (commodity.ea_j_per_mol / R_GAS) * (
        1.0 / commodity.kelvin_ref() - 1.0 / kelvin
    )
    rate = np.exp(exponent)

    degrees_below = np.maximum(commodity.chilling_threshold_c - temp_c, 0.0)
    return rate + commodity.chilling_penalty_per_deg * degrees_below


def q10_at(temp_c: float, commodity: Commodity) -> float:
    """The Q10 implied by this commodity's activation energy, at `temp_c`.

    Reported rather than used. Q10 is the number a food technologist will
    challenge you on, and being able to state it — 2.6 for tomato at 20 C,
    against a published range of 2.0-3.0 — is what makes the choice of Ea
    defensible instead of arbitrary.
    """
    kelvin = temp_c + CELSIUS_TO_KELVIN
    return float(
        np.exp((commodity.ea_j_per_mol / R_GAS) * 10.0 / (kelvin * (kelvin + 10.0)))
    )


def thermal_stress_days(hours, temp_c, commodity: Commodity):
    """Life consumed by an exposure, in reference-days.

    One day at the reference temperature costs exactly 1.0. Four hours on a
    32 C dock costs about 0.5 — which is the whole "your spinach lost two days
    on the receiving dock" argument, in one line of arithmetic.
    """
    hours = np.asarray(hours, dtype=float)
    return (hours / 24.0) * arrhenius_rate_multiplier(temp_c, commodity)


# --------------------------------------------------------------------------
# Batch life budget and loss
# --------------------------------------------------------------------------


def life_budget_median(
    commodity: Commodity,
    maturity: MaturityStage | str,
    damage_fraction=0.0,
):
    """Median per-fruit life budget for a batch, in reference-days.

    Three multiplicands, each independently arguable by a grower: the crop's
    reference life, how ripe it was picked, and how roughly it has been handled.
    Damage does not only destroy fruit outright — bruised tissue respires faster
    and admits pathogens, so what survives has less life left.
    """
    if isinstance(maturity, str):
        maturity = MaturityStage(maturity)
    damage_fraction = np.asarray(damage_fraction, dtype=float)

    handling = np.clip(1.0 - commodity.damage_life_penalty * damage_fraction, 0.05, 1.0)
    return commodity.ref_life_days * MATURITY_LIFE_FACTOR[maturity] * handling


def life_budget_median_by_factor(commodity: Commodity, maturity_factor, damage_fraction):
    """Vectorised twin of `life_budget_median`, for whole scenario arrays.

    The sampler works in maturity *factors* rather than enum members so a batch
    can sit between two USDA colour stages, which real fruit does.
    """
    maturity_factor = np.asarray(maturity_factor, dtype=float)
    damage_fraction = np.asarray(damage_fraction, dtype=float)
    handling = np.clip(1.0 - commodity.damage_life_penalty * damage_fraction, 0.05, 1.0)
    return commodity.ref_life_days * maturity_factor * handling


def spoilage_fraction(stress_days, life_median_days, sigma: float):
    """Share of the batch whose life budget the accumulated stress has used up.

    `Phi((ln S - ln L_median) / sigma)`, with S = 0 mapped to zero loss rather
    than to `log(0)`.
    """
    stress_days = np.asarray(stress_days, dtype=float)
    life_median_days = np.asarray(life_median_days, dtype=float)

    safe_stress = np.where(stress_days > 0.0, stress_days, 1.0)
    z = (np.log(safe_stress) - np.log(life_median_days)) / sigma
    return np.where(stress_days > 0.0, norm_cdf(z), 0.0)


def critical_life_budget(commodity: Commodity, life_median_days):
    """The life budget of the fruit at the critical-spoilage quantile.

    When accumulated stress reaches this, the batch has lost
    `critical_spoilage_fraction` of its mass and no longer meets fresh-retail
    standards. This is Q_crit, expressed in the same reference-days as stress so
    the two can simply be subtracted.
    """
    z = norm_ppf(commodity.critical_spoilage_fraction)
    return np.asarray(life_median_days, dtype=float) * np.exp(
        commodity.life_spread_sigma * z
    )


def remaining_useful_life_hours(
    stress_days_so_far,
    life_median_days,
    forward_temp_c,
    commodity: Commodity,
):
    """Hours until the batch stops meeting fresh-retail standards.

    Forward-looking: it asks how long the *remaining* stress capacity lasts at
    the temperature the batch is about to see, so re-answering it with a cooler
    truck or an earlier departure changes the number. A RUL that does not move
    when the plan moves is a label, not a decision input.
    """
    capacity = np.maximum(
        critical_life_budget(commodity, life_median_days)
        - np.asarray(stress_days_so_far, dtype=float),
        0.0,
    )
    rate = arrhenius_rate_multiplier(forward_temp_c, commodity)
    return 24.0 * capacity / rate
