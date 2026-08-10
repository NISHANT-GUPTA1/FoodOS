"""The learned layer — a LightGBM surrogate for the simulator.

    python -m foodos.agri.risk_model --n 100000

**Be precise about what this model is, because it is easy to oversell.**

The simulator is the model. This is a gradient-boosted approximation *of* the
simulator, trained on its output. It is therefore:

  - not more accurate than the physics. It approximates it, with error.
  - not faster in any way that matters. The simulator runs a shipment in about
    50 microseconds; the What-If sliders do not need a surrogate to feel live.
  - not an independent second opinion. It cannot know anything the Arrhenius
    equation above it does not already contain.

So why build it at all? Three honest reasons, and none of them is accuracy:

1. **Feature attribution.** The Risk Agent has to say *"high maturity plus a
   36-hour open-truck run at 35 C"*, and that needs global importance over the
   whole feature space, not a one-off ablation.
2. **It is the retraining slot.** The day real observed losses exist, the same
   pipeline retrains on `(features -> observed loss)` and the model stops being
   a surrogate and becomes a genuine predictor. The architecture has to exist
   before the data arrives, or it never gets built.
3. **It proves the fusion layer works** — that questionnaire, vision and
   external features actually carry the signal, rather than the physics being
   the only thing doing any work.

The number worth reporting is therefore **fidelity**, not accuracy: how closely
does the surrogate reproduce the simulator? Calling that "prediction accuracy"
would be a category error, so `evaluate()` names it `fidelity_*` throughout.

**On confidence intervals — see `uncertainty.py`.** The label is a deterministic
function of the features: the same shipment always yields the same loss. So any
spread quantile regression finds here is *surrogate approximation error*, not
uncertainty about the outcome.

That prediction was worth checking rather than asserting, and checking it
corrected it. The band does not collapse to a point, which is what you might
expect from a deterministic label — it comes out around 13 percentage points
wide, because the surrogate's own error is substantial. It is also
mis-calibrated: 73% of held-out values fall inside a nominally 80% band.

Both facts point the same way. Shown to a user, that band would report how
imprecise our approximation is while appearing to report how uncertain their
shipment is. Those are different quantities, only one of them is actionable,
and the band is not even a well-calibrated estimate of the wrong one.
`quantile_band_diagnostic()` measures it so the argument stays evidence.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from foodos.agri.commodity import TOMATO
from foodos.agri.features import (
    FEATURE_NAMES,
    TARGETS,
    assert_no_leakage,
    build_features,
    categorical_feature_names,
)
from foodos.agri.scenario import sample_diverse
from foodos.agri.simulate import simulate

MODEL_DIR = Path("data/agri/models")

#: Deliberately modest. The surrogate should reproduce a smooth physical
#: function, not memorise 100k rows, and an over-fitted surrogate would hide
#: exactly the regions where the fusion layer is weak.
LGBM_PARAMS = dict(
    objective="regression",
    n_estimators=800,
    learning_rate=0.06,
    num_leaves=96,
    min_child_samples=40,
    subsample=0.85,
    subsample_freq=1,
    colsample_bytree=0.85,
    reg_lambda=1.0,
    verbose=-1,
)


@dataclass
class Fidelity:
    """How closely the surrogate reproduces the simulator, on held-out rows."""

    target: str
    unit: str
    rows: int
    mae: float
    rmse: float
    r2: float
    p95_abs_error: float
    max_abs_error: float
    #: Predicting the training mean. A surrogate that cannot beat this has
    #: learned nothing from the fusion layer at all.
    baseline_mae: float
    improvement_vs_baseline: float


def _metrics(target: str, unit: str, actual, predicted, baseline_value: float) -> Fidelity:
    actual = np.asarray(actual, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    err = np.abs(actual - predicted)
    variance = float(np.var(actual))
    baseline_mae = float(np.mean(np.abs(actual - baseline_value)))

    return Fidelity(
        target=target,
        unit=unit,
        rows=int(len(actual)),
        mae=float(err.mean()),
        rmse=float(np.sqrt(np.mean((actual - predicted) ** 2))),
        r2=float(1.0 - np.mean((actual - predicted) ** 2) / variance) if variance else 0.0,
        p95_abs_error=float(np.percentile(err, 95)),
        max_abs_error=float(err.max()),
        baseline_mae=baseline_mae,
        improvement_vs_baseline=(
            float(1.0 - err.mean() / baseline_mae) if baseline_mae else 0.0
        ),
    )


def build_dataset(n: int = 100_000, seed: int = 11) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Simulate `n` shipments and split into features and targets."""
    frame = simulate(sample_diverse(TOMATO, n, seed=seed))
    features = build_features(frame)
    assert_no_leakage(features)
    targets = frame[[TARGETS["loss"], TARGETS["rul"]]].copy()
    return features, targets


def _split(n: int, holdout: float, seed: int) -> tuple[np.ndarray, np.ndarray]:
    """A held-out block, drawn by a fixed permutation so it is reproducible."""
    order = np.random.default_rng(seed).permutation(n)
    cut = int(n * (1.0 - holdout))
    return order[:cut], order[cut:]


def train(
    features: pd.DataFrame,
    targets: pd.DataFrame,
    holdout: float = 0.2,
    seed: int = 42,
) -> tuple[dict, dict[str, Fidelity]]:
    """Fit one surrogate per target. Returns the boosters and their fidelity."""
    from lightgbm import LGBMRegressor

    train_idx, test_idx = _split(len(features), holdout, seed)
    x_train = features.iloc[train_idx]
    x_test = features.iloc[test_idx]

    models: dict = {}
    scores: dict[str, Fidelity] = {}

    for name, column in TARGETS.items():
        y_train = targets[column].to_numpy()[train_idx]
        y_test = targets[column].to_numpy()[test_idx]

        model = LGBMRegressor(**LGBM_PARAMS, random_state=seed)
        model.fit(
            x_train,
            y_train,
            categorical_feature=categorical_feature_names(),
        )
        models[name] = model
        scores[name] = _metrics(
            target=column,
            unit="loss fraction" if name == "loss" else "hours",
            actual=y_test,
            predicted=model.predict(x_test),
            baseline_value=float(y_train.mean()),
        )

    return models, scores


def quantile_band_diagnostic(
    features: pd.DataFrame,
    targets: pd.DataFrame,
    holdout: float = 0.2,
    seed: int = 42,
) -> dict:
    """Evidence for why the intervals do not come from quantile regression.

    Trains q10 and q90 models on the loss target and measures the resulting
    band. The label is a deterministic function of the features, so whatever
    spread these models find is surrogate approximation error rather than
    uncertainty about the shipment.

    Measuring rather than assuming corrected the expectation here: the band does
    not collapse to a point, it comes out wide, because the surrogate's error is
    large. It is also mis-calibrated — empirical coverage lands well under the
    nominal 80%. Either finding alone disqualifies it as a user-facing interval;
    together they make the case unarguable. Use `uncertainty.py` instead.
    """
    from lightgbm import LGBMRegressor

    train_idx, test_idx = _split(len(features), holdout, seed)
    x_train, x_test = features.iloc[train_idx], features.iloc[test_idx]
    y_train = targets[TARGETS["loss"]].to_numpy()[train_idx]
    y_test = targets[TARGETS["loss"]].to_numpy()[test_idx]

    bounds = {}
    for alpha, key in ((0.1, "q10"), (0.9, "q90")):
        model = LGBMRegressor(
            **{**LGBM_PARAMS, "objective": "quantile", "alpha": alpha},
            random_state=seed,
        )
        model.fit(x_train, y_train, categorical_feature=categorical_feature_names())
        bounds[key] = model.predict(x_test)

    width = bounds["q90"] - bounds["q10"]
    inside = float(np.mean((y_test >= bounds["q10"]) & (y_test <= bounds["q90"])))
    spread = float(np.std(y_test))

    return {
        "median_band_width": float(np.median(width)),
        "band_width_as_share_of_label_spread": float(np.median(width) / spread),
        "empirical_coverage": inside,
        "nominal_coverage": 0.8,
        "interpretation": (
            "The features determine the label exactly, so this band measures "
            "surrogate approximation error, not uncertainty about the shipment. "
            "It is wide because the surrogate is imprecise, and its empirical "
            "coverage misses the nominal 80%. Not a user-facing confidence "
            "range. See uncertainty.py."
        ),
    }


def importance(model, features: pd.DataFrame, top: int = 12) -> list[dict]:
    """Gain importance — what the Risk Agent turns into a loss-driver sentence."""
    gains = np.asarray(model.booster_.feature_importance(importance_type="gain"), float)
    total = gains.sum() or 1.0
    ranked = sorted(
        ({"feature": f, "gain_share": float(g / total)} for f, g in zip(FEATURE_NAMES, gains)),
        key=lambda row: row["gain_share"],
        reverse=True,
    )
    return ranked[:top]


def save(models: dict, scores: dict[str, Fidelity], directory: Path = MODEL_DIR) -> Path:
    """Persist boosters as LightGBM text, never pickle.

    Pickle would tie the artifact to this exact interpreter and library build,
    and would execute arbitrary code on load. The native text format survives
    both, which matters for something a teammate reloads on another machine.
    """
    directory.mkdir(parents=True, exist_ok=True)
    for name, model in models.items():
        model.booster_.save_model(str(directory / f"{name}.txt"))
    (directory / "metadata.json").write_text(
        json.dumps(
            {
                "features": FEATURE_NAMES,
                "targets": TARGETS,
                "fidelity": {k: asdict(v) for k, v in scores.items()},
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return directory


def load(directory: Path = MODEL_DIR) -> tuple[dict, dict]:
    """Reload saved boosters. Raises if training has not been run."""
    import lightgbm as lgb

    metadata_path = directory / "metadata.json"
    if not metadata_path.exists():
        raise FileNotFoundError(
            f"no trained surrogate at {directory}. Run: python -m foodos.agri.risk_model"
        )
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    boosters = {
        name: lgb.Booster(model_file=str(directory / f"{name}.txt")) for name in TARGETS
    }
    return boosters, metadata


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the LightGBM surrogate.")
    parser.add_argument("--n", type=int, default=100_000)
    parser.add_argument("--seed", type=int, default=11)
    parser.add_argument("--holdout", type=float, default=0.2)
    parser.add_argument("--out", type=Path, default=MODEL_DIR)
    parser.add_argument("--skip-degeneracy-check", action="store_true")
    args = parser.parse_args()

    print(f"simulating {args.n:,} shipments ...")
    features, targets = build_dataset(args.n, seed=args.seed)
    print(f"  {len(features):,} rows x {len(FEATURE_NAMES)} features, no leakage")

    models, scores = train(features, targets, holdout=args.holdout, seed=args.seed)

    print(f"\nSURROGATE FIDELITY (held out {args.holdout:.0%}, never trained on)")
    for name, score in scores.items():
        unit = "pp" if name == "loss" else "h"
        scale = 100.0 if name == "loss" else 1.0
        print(f"\n  {name}  ({score.target}, {score.unit})")
        print(f"    MAE                 {score.mae * scale:8.3f} {unit}")
        print(f"    RMSE                {score.rmse * scale:8.3f} {unit}")
        print(f"    P95 abs error       {score.p95_abs_error * scale:8.3f} {unit}")
        print(f"    max abs error       {score.max_abs_error * scale:8.3f} {unit}")
        print(f"    R2                  {score.r2:8.4f}")
        print(f"    vs mean baseline    {score.improvement_vs_baseline:8.1%} better")

    print("\nTOP LOSS DRIVERS (gain share, loss model)")
    for row in importance(models["loss"], features, top=8):
        bar = "#" * max(int(row["gain_share"] * 60), 1)
        print(f"    {row['feature']:34} {row['gain_share']:6.1%}  {bar}")

    if not args.skip_degeneracy_check:
        print("\nWHY INTERVALS DO NOT COME FROM THIS MODEL")
        report = quantile_band_diagnostic(features, targets, args.holdout, args.seed)
        print(f"    median q10-q90 width      {report['median_band_width'] * 100:.3f} pp")
        print(
            f"    as share of label spread  "
            f"{report['band_width_as_share_of_label_spread']:.3f}"
        )
        print(f"    empirical coverage        {report['empirical_coverage']:.3f}")
        print("    -> measures surrogate error, not uncertainty. Use uncertainty.py.")

    path = save(models, scores, args.out)
    print(f"\nsaved to {path}/")
    print(
        "\nThis is a SURROGATE for the simulator, not an independent predictor.\n"
        "It exists for feature attribution, and as the slot that retrains on real\n"
        "observed losses the day they exist. See this module's docstring."
    )


if __name__ == "__main__":
    main()
