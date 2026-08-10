"""Demand forecasting — LightGBM quantile regression.

One model per quantile, all dishes together with dish as a categorical feature. Fourteen
dishes and half a year of history is not enough data to fit fourteen separate models well;
pooling lets a quiet dish borrow the weekday and weather shape from a busy one, which is
the difference between a usable forecast and an expensive random number generator.

The engine needs a *distribution*, not a point estimate — the newsvendor is a statement
about quantiles. That is why this is quantile regression and not a regressor with an error
bar bolted on afterwards.

Known limitation, stated rather than hidden: the target is units SOLD, which is censored
by what was produced. On a day the kitchen sold out, true demand was higher than the
number we train on. In this dataset the kitchen over-produces far more often than it runs
out, so the bias is small — but it is real, it biases the forecast down, and a production
system would model it explicitly.

Owner: Person A.
"""

from __future__ import annotations

import datetime as dt
import warnings
from dataclasses import dataclass, field

import lightgbm as lgb
import numpy as np
import pandas as pd

from ..config import get_config

MODEL_VERSION = "lgbm-quantile-1"

FEATURES = [
    "dow", "is_weekend", "is_holiday", "rain_mm", "temp_c", "promo", "local_event",
    "dish_code", "lag_1", "lag_7", "lag_14", "roll_7", "roll_28", "dow_mean",
]
CATEGORICAL = ["dish_code", "dow"]

LGB_PARAMS = {
    "objective": "quantile",
    "learning_rate": 0.06,
    "num_leaves": 15,
    "min_data_in_leaf": 20,
    "feature_fraction": 0.85,
    "bagging_fraction": 0.85,
    "bagging_freq": 1,
    "verbosity": -1,
    "num_threads": 2,
}
NUM_ROUNDS = 220


def build_features(sales: pd.DataFrame, context: pd.DataFrame) -> pd.DataFrame:
    """Join demand context onto sales and add the lag and rolling features.

    Every lag is shifted by at least one day. A feature that peeks at the same day's sales
    would make the backtest look wonderful and the demo look like a fraud.
    """
    frame = sales.merge(context, on="date", how="left").sort_values(["dish_id", "date"])
    grouped = frame.groupby("dish_id", observed=True)["qty_portions"]

    frame["lag_1"] = grouped.shift(1)
    frame["lag_7"] = grouped.shift(7)
    frame["lag_14"] = grouped.shift(14)
    frame["roll_7"] = grouped.shift(1).rolling(7, min_periods=3).mean()
    frame["roll_28"] = grouped.shift(1).rolling(28, min_periods=7).mean()

    # Mean for this dish on this weekday, computed from the past only.
    frame["dow_mean"] = (
        frame.groupby(["dish_id", "dow"], observed=True)["qty_portions"]
        .transform(lambda s: s.shift(1).expanding(min_periods=2).mean())
    )

    frame["dish_code"] = frame["dish_id"].astype("category").cat.codes
    return frame


@dataclass
class Forecaster:
    """Trains one booster per quantile and interpolates between them on demand."""

    quantiles: tuple[float, ...] = ()
    models: dict[float, lgb.Booster] = field(default_factory=dict)
    dish_codes: dict[str, int] = field(default_factory=dict)
    trained_through: dt.date | None = None

    def __post_init__(self) -> None:
        if not self.quantiles:
            self.quantiles = get_config().forecast_quantiles

    # --- training ----------------------------------------------------------

    def fit(self, frame: pd.DataFrame, *, up_to: dt.date | None = None) -> "Forecaster":
        train = frame if up_to is None else frame[frame["date"] < pd.Timestamp(up_to)]
        train = train.dropna(subset=["lag_14", "roll_28"])
        if train.empty:
            raise ValueError("not enough history to fit a forecaster")

        self.dish_codes = (
            train[["dish_id", "dish_code"]].drop_duplicates().set_index("dish_id")["dish_code"].to_dict()
        )
        x = train[FEATURES]
        y = train["qty_portions"]

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            for q in self.quantiles:
                dataset = lgb.Dataset(x, label=y, categorical_feature=CATEGORICAL, free_raw_data=False)
                self.models[q] = lgb.train(
                    {**LGB_PARAMS, "alpha": q}, dataset, num_boost_round=NUM_ROUNDS
                )

        self.trained_through = (
            train["date"].max().date() if hasattr(train["date"].max(), "date") else up_to
        )
        return self

    # --- prediction --------------------------------------------------------

    def predict_grid(self, frame: pd.DataFrame) -> pd.DataFrame:
        """Predict every trained quantile for every row. Returns dish_id, date, q, value."""
        if not self.models:
            raise RuntimeError("forecaster has not been fitted")

        rows = frame.copy()
        out = rows[["date", "dish_id"]].copy()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            for q, model in self.models.items():
                out[q] = np.maximum(0.0, model.predict(rows[FEATURES]))

        melted = out.melt(id_vars=["date", "dish_id"], var_name="quantile", value_name="value")
        melted["quantile"] = melted["quantile"].astype(float)

        # Quantile crossing: independently fitted quantiles can come out of order at the
        # edges. Sorting within each row restores monotonicity, which the newsvendor needs.
        melted = melted.sort_values(["dish_id", "date", "quantile"])
        melted["value"] = (
            melted.groupby(["dish_id", "date"], observed=True)["value"].cummax()
        )
        return melted.reset_index(drop=True)


class QuantileCurve:
    """The forecast for one dish on one day, as a callable distribution.

    ``curve.quantile(0.73)`` interpolates between the trained levels. This is the object
    the optimiser asks for its answer, and the only place a service level becomes portions.
    """

    def __init__(self, quantiles: list[float], values: list[float]) -> None:
        order = np.argsort(quantiles)
        self.q = np.asarray(quantiles, dtype=float)[order]
        self.v = np.maximum.accumulate(np.asarray(values, dtype=float)[order])

    def quantile(self, level: float) -> float:
        level = min(max(float(level), 0.0), 1.0)
        return float(np.interp(level, self.q, self.v))

    @property
    def median(self) -> float:
        return self.quantile(0.5)

    @property
    def spread(self) -> float:
        """A rough standard deviation, from the 10th-to-90th range. Used for confidence."""
        return (self.quantile(0.9) - self.quantile(0.1)) / 2.563

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"QuantileCurve(median={self.median:.1f}, spread={self.spread:.1f})"


def curves_from_frame(frame: pd.DataFrame) -> dict[str, QuantileCurve]:
    """Group a long forecast frame (dish_id, quantile, value) into one curve per dish."""
    curves: dict[str, QuantileCurve] = {}
    for dish_id, group in frame.groupby("dish_id", observed=True):
        curves[str(dish_id)] = QuantileCurve(
            group["quantile"].tolist(), group["value"].tolist()
        )
    return curves


def build_next_day_row(
    dish_id: str,
    dish_code: int,
    target_date: dt.date,
    history: pd.DataFrame,
    context_row: pd.Series,
) -> dict:
    """Assemble the feature row for a day we have no sales for yet."""
    past = history[history["dish_id"] == dish_id].sort_values("date")
    series = past["qty_portions"]

    def lag(n: int) -> float:
        return float(series.iloc[-n]) if len(series) >= n else float(series.mean())

    dow_past = past[past["dow"] == target_date.weekday()]["qty_portions"]

    return {
        "date": pd.Timestamp(target_date),
        "dish_id": dish_id,
        "dish_code": dish_code,
        "dow": target_date.weekday(),
        "is_weekend": int(target_date.weekday() >= 5),
        "is_holiday": int(context_row.get("is_holiday", 0)),
        "rain_mm": float(context_row.get("rain_mm", 0.0)),
        "temp_c": float(context_row.get("temp_c", 28.0)),
        "promo": int(context_row.get("promo", 0)),
        "local_event": int(context_row.get("local_event", 0)),
        "lag_1": lag(1),
        "lag_7": lag(7),
        "lag_14": lag(14),
        "roll_7": float(series.tail(7).mean()),
        "roll_28": float(series.tail(28).mean()),
        "dow_mean": float(dow_past.tail(8).mean()) if len(dow_past) else float(series.mean()),
    }
