"""Confidence intervals, from the uncertainty that actually exists.

The blueprint asks for *"Expected Loss: 8.4%, Likely Range: 6.7%-10.9%"*. The
tempting way to produce that is quantile regression on the training data. It
would be wrong, and quietly so.

The label is a deterministic function of the features: give the simulator the
same shipment twice and it returns the same loss. The conditional distribution
of loss given features is a point mass, so whatever spread a quantile model
finds is its own approximation error wearing a confidence interval's clothes.

Measured rather than assumed — `risk_model.quantile_band_diagnostic()` runs it —
that band comes out about 13 percentage points wide and captures only 73% of
held-out values against a nominal 80%. So it is both the wrong quantity and a
poorly calibrated estimate of it. Dressing that up as a likely range is the same
failure as an LLM inventing a number, arrived at more respectably.

The uncertainty that *is* real lives in the inputs. The FPO manager estimating
"about ten hours" does not know the traffic. The forecast for tomorrow's high
carries a couple of degrees of error. The vision model's damage fraction is an
estimate from five photographs. Propagate those and you get a band that means
something: **given what you do not know about this shipment, here is the range
the loss could land in.**

Which is also more useful than a statistical band, because it decomposes.
`sensitivity()` reports which unknown is doing the widening, so the answer to a
wide interval is an action — *"pin down your departure slot and this tightens by
two thirds"* — rather than a shrug.

Cost: the simulator runs a shipment in about 50 microseconds, so two thousand
Monte Carlo draws cost a few milliseconds. The What-If sliders stay live.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from foodos.agri.commodity import TOMATO, Commodity
from foodos.agri.scenario import ScenarioBatch
from foodos.agri.simulate import simulate

#: How well an FPO manager, a weather service and a vision model actually know
#: each input. Every entry is a claim about the world and is commented as one.
#:
#:   ("lognormal", s)  multiplicative, exp(N(0, s)) — for durations, which are
#:                     positive and whose errors are proportional and
#:                     right-skewed (traffic delays you, it rarely speeds you up)
#:   ("normal", s)     additive, N(0, s) — for temperatures and indices
#:   ("relative", f)   additive, N(0, f * value) — for estimates whose error
#:                     scales with the reading, like a vision damage fraction
DEFAULT_UNCERTAINTY: dict[str, tuple[str, float]] = {
    # The single largest unknown. A stated departure and a stated arrival are
    # both aspirations; breakdowns, checkposts and traffic are not modelled
    # anywhere else, so they live here.
    "transit_hours": ("lognormal", 0.22),
    # Worse than transit. Whether a lot clears the mandi in two hours or sits
    # until the next session depends on buyers who have not arrived yet.
    "mandi_holding_hours": ("lognormal", 0.45),
    # The grower knows roughly how long the crop sat, but not to the half hour.
    "field_hours": ("lognormal", 0.18),
    # Public forecast error for a next-day maximum, in degrees.
    "ambient_mean_c": ("normal", 1.6),
    "diurnal_amplitude_c": ("normal", 1.2),
    # Vision estimates from three to five representative photographs. The
    # blueprint is explicit that these are probabilistic features, not truth,
    # and this is where that admission is cashed in.
    "visual_damage_fraction": ("relative", 0.30),
    "maturity_factor": ("normal", 0.09),
    # Road quality along a known route is roughly known.
    "road_roughness": ("normal", 0.12),
}

#: Answered by choosing, not by estimating. The manager knows which truck.
CERTAIN_FIELDS = frozenset(
    {
        "harvest_method",
        "harvest_window",
        "field_holding",
        "packaging",
        "transport_mode",
        "quantity_kg",
    }
)

_FLOOR = {
    "transit_hours": 0.5,
    "mandi_holding_hours": 0.25,
    "field_hours": 0.05,
    "visual_damage_fraction": 0.0,
    "maturity_factor": 0.42,
    "road_roughness": 0.85,
    "ambient_mean_c": -5.0,
    "diurnal_amplitude_c": 0.5,
}
_CEILING = {"maturity_factor": 1.75, "visual_damage_fraction": 0.9}


@dataclass(frozen=True)
class Interval:
    """A predicted quantity with the range its unknown inputs imply."""

    median: float
    low: float
    high: float
    unit: str

    @property
    def width(self) -> float:
        return self.high - self.low


def perturb(
    base: dict,
    n: int,
    commodity: Commodity = TOMATO,
    uncertainty: dict[str, tuple[str, float]] | None = None,
    rng: np.random.Generator | None = None,
    freeze: str | None = None,
) -> ScenarioBatch:
    """`n` copies of one shipment, with the uncertain inputs jittered.

    `freeze` holds one field at its stated value while everything else varies —
    which is how `sensitivity()` attributes the width of the band.
    """
    uncertainty = DEFAULT_UNCERTAINTY if uncertainty is None else uncertainty
    rng = rng or np.random.default_rng(0)

    columns: dict[str, np.ndarray] = {}
    for field in CERTAIN_FIELDS:
        value = base[field]
        columns[field] = (
            np.full(n, float(value))
            if field == "quantity_kg"
            else np.array([str(value)] * n)
        )

    for field, (kind, scale) in uncertainty.items():
        value = float(base[field])
        if field == freeze or scale == 0.0:
            drawn = np.full(n, value)
        elif kind == "lognormal":
            drawn = value * np.exp(rng.normal(0.0, scale, n))
        elif kind == "relative":
            drawn = value + rng.normal(0.0, scale * max(value, 1e-6), n)
        else:
            drawn = value + rng.normal(0.0, scale, n)

        drawn = np.clip(drawn, _FLOOR.get(field, 0.0), _CEILING.get(field, np.inf))
        columns[field] = drawn

    return ScenarioBatch(
        n=n, commodity=commodity, meta={"sampler": "uncertainty"}, **columns
    )


def intervals(
    base: dict,
    n: int = 2_000,
    commodity: Commodity = TOMATO,
    low_q: float = 0.10,
    high_q: float = 0.90,
    seed: int = 0,
) -> dict[str, Interval]:
    """Monte Carlo the unknowns through the simulator. Milliseconds."""
    frame = simulate(
        perturb(base, n, commodity, rng=np.random.default_rng(seed))
    )
    out = {}
    for key, column, unit, scale in (
        ("loss", "total_loss", "percent", 100.0),
        ("rul", "rul_hours_at_dispatch", "hours", 1.0),
    ):
        values = frame[column].to_numpy() * scale
        out[key] = Interval(
            median=float(np.median(values)),
            low=float(np.quantile(values, low_q)),
            high=float(np.quantile(values, high_q)),
            unit=unit,
        )
    return out


def sensitivity(
    base: dict,
    n: int = 2_000,
    commodity: Commodity = TOMATO,
    seed: int = 0,
) -> list[dict]:
    """Which unknown is widening the band, and by how much.

    Freezes one field at its stated value, re-runs, and reports how much of the
    interval width disappears. That converts a wide range into an instruction:
    the field at the top of this list is the one worth pinning down.

    Contributions do not sum to one — the inputs interact through a nonlinear
    model — so they are reported as shares of the unfrozen width and labelled
    as such rather than normalised into a tidy pie chart that would imply an
    additivity the physics does not have.
    """
    full = intervals(base, n, commodity, seed=seed)["loss"]
    if full.width <= 0:
        return []

    rows = []
    for field in DEFAULT_UNCERTAINTY:
        frame = simulate(
            perturb(base, n, commodity, rng=np.random.default_rng(seed), freeze=field)
        )
        values = frame["total_loss"].to_numpy() * 100.0
        narrowed = float(np.quantile(values, 0.9) - np.quantile(values, 0.1))
        rows.append(
            {
                "field": field,
                "width_removed_pp": round(full.width - narrowed, 4),
                "share_of_width": round(
                    max(full.width - narrowed, 0.0) / full.width, 4
                ),
            }
        )

    rows.sort(key=lambda row: row["width_removed_pp"], reverse=True)
    return rows
