"""Turn a stored quantile grid back into a usable demand distribution.

`Forecast` stores q10..q90 because that is what a quantile regressor emits.
Every downstream decision needs expectations over the distribution, not the
quantiles themselves, so this module is the bridge.

Deterministic by construction: the "samples" are the quantile function
evaluated on a fixed grid, never random draws. Same input, same output, every
run — which is what makes the demo reproducible.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

_KNOT_P = np.array([0.10, 0.25, 0.50, 0.66, 0.75, 0.90])


@dataclass(frozen=True)
class DemandDistribution:
    """A demand distribution reconstructed from its quantiles."""

    knots_p: np.ndarray
    knots_v: np.ndarray
    grid: np.ndarray  # evaluated quantile function, the "sample"

    # ---------------------------------------------------------------- build
    @classmethod
    def from_quantiles(
        cls,
        q10: float,
        q25: float,
        q50: float,
        q66: float,
        q75: float,
        q90: float,
        grid_size: int = 2001,
    ) -> "DemandDistribution":
        vals = np.array([q10, q25, q50, q66, q75, q90], dtype=float)
        # Quantiles must be non-decreasing; a noisy model can emit crossings.
        vals = np.maximum.accumulate(vals)

        # Extend the tails linearly so the 1st and 99th percentiles are not flat.
        lo_slope = (vals[1] - vals[0]) / (_KNOT_P[1] - _KNOT_P[0])
        hi_slope = (vals[5] - vals[4]) / (_KNOT_P[5] - _KNOT_P[4])
        v_min = max(0.0, vals[0] - lo_slope * _KNOT_P[0])
        v_max = vals[5] + hi_slope * (1.0 - _KNOT_P[5])

        knots_p = np.concatenate(([0.0], _KNOT_P, [1.0]))
        knots_v = np.maximum.accumulate(
            np.concatenate(([v_min], vals, [v_max]))
        ).clip(min=0.0)

        # Midpoint rule: p_i = (i + 0.5) / n. Unbiased and free of endpoints.
        ps = (np.arange(grid_size) + 0.5) / grid_size
        grid = np.interp(ps, knots_p, knots_v)
        return cls(knots_p=knots_p, knots_v=knots_v, grid=grid)

    @classmethod
    def from_samples(cls, samples, grid_size: int = 2001) -> "DemandDistribution":
        """Build from raw history — used by the seasonal-naive fallback."""
        arr = np.asarray(list(samples), dtype=float)
        if arr.size == 0:
            arr = np.array([0.0])
        qs = np.quantile(arr, [0.10, 0.25, 0.50, 0.66, 0.75, 0.90])
        return cls.from_quantiles(*qs, grid_size=grid_size)

    # ----------------------------------------------------------- statistics
    def quantile(self, p: float) -> float:
        """Inverse CDF. `p` is clipped into (0, 1)."""
        p = float(np.clip(p, 1e-6, 1 - 1e-6))
        return float(np.interp(p, self.knots_p, self.knots_v))

    @property
    def mean(self) -> float:
        return float(self.grid.mean())

    @property
    def sd(self) -> float:
        return float(self.grid.std())

    def cdf(self, x: float) -> float:
        """P(D <= x)."""
        return float((self.grid <= x).mean())

    def expected_sales(self, qty: float) -> float:
        """E[min(D, Q)] — units that actually move."""
        return float(np.minimum(self.grid, qty).mean())

    def expected_leftover(self, qty: float) -> float:
        """E[(Q - D)+] — units prepared and not sold. This is the waste."""
        return float(np.maximum(qty - self.grid, 0.0).mean())

    def expected_shortfall(self, qty: float) -> float:
        """E[(D - Q)+] — demand you could not serve."""
        return float(np.maximum(self.grid - qty, 0.0).mean())

    def interval(self, lo: float = 0.10, hi: float = 0.90) -> tuple[float, float]:
        return self.quantile(lo), self.quantile(hi)

    @property
    def relative_width(self) -> float:
        """Width of the 10-90 band relative to the median. Drives confidence."""
        lo, hi = self.interval()
        med = self.quantile(0.50)
        return (hi - lo) / med if med > 1e-9 else float("inf")


def scale(dist: DemandDistribution, factor: float) -> DemandDistribution:
    """Scale a distribution — used to convert dish demand into ingredient kg."""
    return DemandDistribution(
        knots_p=dist.knots_p,
        knots_v=dist.knots_v * factor,
        grid=dist.grid * factor,
    )


def convolve_days(dist: DemandDistribution, days: float) -> DemandDistribution:
    """Approximate the distribution of demand accumulated over `days`.

    Mean scales linearly, spread with sqrt(days) — the standard independent-day
    approximation. Adequate over the 1-5 day horizons an RSL window covers.
    """
    days = max(days, 0.0)
    if days <= 0:
        return DemandDistribution.from_quantiles(0, 0, 0, 0, 0, 0, dist.grid.size)
    mu, sigma = dist.mean, dist.sd
    new_mu = mu * days
    new_sigma = sigma * (days**0.5)
    if sigma <= 1e-9:
        return DemandDistribution.from_quantiles(*([new_mu] * 6), grid_size=dist.grid.size)
    centred = (dist.grid - mu) / sigma
    grid = np.sort(np.clip(new_mu + centred * new_sigma, 0.0, None))
    ps = (np.arange(grid.size) + 0.5) / grid.size
    qs = np.interp([0.10, 0.25, 0.50, 0.66, 0.75, 0.90], ps, grid)
    return DemandDistribution.from_quantiles(*qs, grid_size=dist.grid.size)
