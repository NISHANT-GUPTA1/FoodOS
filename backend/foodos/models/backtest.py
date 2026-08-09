"""Backtest — accuracy measured on days the model never saw.

The rule this file exists to enforce: the model is fitted on data strictly before the
held-out window, and evaluated only on days inside it. No refitting, no peeking, no
"we retrained nightly so every day is out-of-sample really".

The baseline is same-day-last-week. It is the honest comparator because it is what a
competent kitchen manager already does in their head. Beating a random-number generator
would prove nothing.

Owner: Person A.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .forecaster import Forecaster, build_features


@dataclass
class BacktestResult:
    days: list[dict] = field(default_factory=list)
    mae: float = 0.0
    baseline_mae: float = 0.0
    improvement_pct: float = 0.0
    held_out_from: dt.date | None = None
    held_out_to: dt.date | None = None

    @property
    def beats_baseline(self) -> bool:
        return self.mae < self.baseline_mae


def naive_baseline(sales: pd.DataFrame) -> pd.DataFrame:
    """Same day last week. What the manager already does, and a genuinely hard target."""
    frame = sales.sort_values(["dish_id", "date"]).copy()
    frame["baseline"] = frame.groupby("dish_id", observed=True)["qty_portions"].shift(7)
    return frame[["date", "dish_id", "baseline"]]


def run_backtest(
    sales: pd.DataFrame,
    context: pd.DataFrame,
    *,
    held_out_days: int = 28,
    quantiles: tuple[float, ...] | None = None,
) -> tuple[BacktestResult, pd.DataFrame]:
    """Fit before the cutoff, predict after it, score only the held-out days.

    Returns the result and the long-form median forecast for the held-out window, which
    the attribution model needs in order to split over-production into plan drift and
    forecast error.
    """
    frame = build_features(sales, context)
    last_date = frame["date"].max()
    cutoff = (last_date - pd.Timedelta(days=held_out_days - 1)).date()

    forecaster = Forecaster(quantiles=quantiles or ())
    forecaster.fit(frame, up_to=cutoff)

    held_out = frame[frame["date"] >= pd.Timestamp(cutoff)].dropna(subset=["lag_14", "roll_28"])
    if held_out.empty:
        return BacktestResult(), pd.DataFrame(columns=["date", "dish_id", "forecast_median"])

    grid = forecaster.predict_grid(held_out)
    median = (
        grid[np.isclose(grid["quantile"], 0.5)]
        .rename(columns={"value": "forecast_median"})[["date", "dish_id", "forecast_median"]]
    )

    scored = (
        held_out[["date", "dish_id", "qty_portions"]]
        .merge(median, on=["date", "dish_id"], how="left")
        .merge(naive_baseline(sales), on=["date", "dish_id"], how="left")
    )
    scored = scored.dropna(subset=["forecast_median", "baseline"])

    mae = float(np.mean(np.abs(scored["qty_portions"] - scored["forecast_median"])))
    baseline_mae = float(np.mean(np.abs(scored["qty_portions"] - scored["baseline"])))

    daily = (
        scored.groupby("date", observed=True)
        .agg(
            actual=("qty_portions", "sum"),
            forecast=("forecast_median", "sum"),
            baseline=("baseline", "sum"),
        )
        .reset_index()
    )

    result = BacktestResult(
        days=[
            {
                "date": row.date.date(),
                "actual": round(float(row.actual), 1),
                "forecast": round(float(row.forecast), 1),
                "baseline": round(float(row.baseline), 1),
                "held_out": True,
            }
            for row in daily.itertuples()
        ],
        mae=round(mae, 2),
        baseline_mae=round(baseline_mae, 2),
        improvement_pct=round(100.0 * (baseline_mae - mae) / baseline_mae, 1) if baseline_mae else 0.0,
        held_out_from=cutoff,
        held_out_to=last_date.date(),
    )
    return result, median
