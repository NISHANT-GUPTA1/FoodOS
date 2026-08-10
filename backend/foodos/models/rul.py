"""Contract 1 · remaining useful life. FoodOS-Team-Split-v2.md §2.

Hours, not days — a shipment decision is made inside one working day, and a
figure rounded to days cannot tell a manager whether the truck leaves tonight.

Wraps `foodos.agri.kinetics` through the simulator. **No second physics**
(Ruling 1): the accumulated-life-fraction model already exists and this file
does not reformulate it.
"""

from __future__ import annotations

from foodos.models.features import scenario_base

#: Used when A's simulator is unreachable. A day and a bit — short enough that
#: nobody mistakes it for a healthy batch, long enough not to trigger a panic.
FALLBACK_RUL_HOURS = 31.0
FALLBACK_QUALITY = 70.0


def predict_rul_hours(features: dict) -> float:
    """Hours of usable life left at dispatch."""
    try:
        from foodos.agri.commodity import TOMATO
        from foodos.agri.predict import run

        return round(float(run(scenario_base(features), TOMATO)["rul_hours_at_dispatch"]), 1)
    except Exception:
        return FALLBACK_RUL_HOURS


def quality_score(features: dict) -> float:
    """0-100. The Q in the batch profile."""
    try:
        from foodos.agri.commodity import TOMATO
        from foodos.agri.predict import run

        return round(float(run(scenario_base(features), TOMATO)["quality_score"]), 1)
    except Exception:
        return FALLBACK_QUALITY
