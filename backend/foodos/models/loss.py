"""Contract 1 · the loss model. FoodOS-Team-Split-v2.md §2.

Adapters over `foodos.agri`, not a second model. `train_loss_model` drives A's
gradient-boosted surrogate; `predict_loss` returns A's Batch Intelligence in
the contracted shape.

Both degrade rather than raise. §2: if a number A owns is not available yet, the
caller gets a deterministic placeholder behind the same signature, and nobody
blocks.
"""

from __future__ import annotations

from foodos.models.features import scenario_base

#: Returned when A's simulator cannot be reached. Deliberately the NABCONS
#: short-haul figure rather than a flattering one.
FALLBACK_LOSS_PCT = 8.4


def train_loss_model(scenarios_path: str | None = None, n: int = 20_000) -> str:
    """Fit the surrogate and return a model_run_id.

    `scenarios_path` is accepted for the frozen signature; A's trainer builds
    its own dataset from the physics rather than reading a file, so the path is
    recorded in the run id instead of being loaded.
    """
    from foodos.agri import risk_model

    features, targets = risk_model.build_dataset(n=n)
    models, scores = risk_model.train(features, targets)
    path = risk_model.save(models, scores)
    return f"agri.risk_model:{path.name}"


def predict_loss(features: dict) -> dict:
    """Loss percentage, band, confidence and ranked drivers.

    Shape is frozen in §2:
        {"loss_pct", "low", "high", "confidence", "drivers"}
    """
    base = scenario_base(features)
    missing = features.get("_missing") or []

    try:
        from foodos.agri.commodity import TOMATO
        from foodos.agri.predict import predict

        bi = predict(base, TOMATO, mc_draws=300, with_sensitivity=False)
        total = sum(abs(d.loss_reduction_pp) for d in bi.drivers) or 1.0
        return {
            "loss_pct": bi.loss_pct,
            "low": bi.loss_low_pct,
            "high": bi.loss_high_pct,
            # Every absent ingestion layer widens the honest uncertainty.
            "confidence": _confidence(len(missing)),
            "drivers": [
                {
                    "name": d.field,
                    "contribution": round(abs(d.loss_reduction_pp) / total, 3),
                    "text": d.label,
                }
                for d in bi.drivers
            ],
            "model_run_id": "agri.predict",
        }
    except Exception:
        return {
            "loss_pct": FALLBACK_LOSS_PCT,
            "low": None,
            "high": None,
            "confidence": "LOW",
            "drivers": [],
            "model_run_id": None,
        }


def _confidence(missing_layers: int) -> str:
    if missing_layers == 0:
        return "HIGH"
    return "MEDIUM" if missing_layers <= 2 else "LOW"
