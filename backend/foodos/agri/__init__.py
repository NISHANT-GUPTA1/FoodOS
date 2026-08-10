"""Person A — the calibrated synthetic simulation engine.

Everything downstream is blocked until this emits a dataset, so it is the first
thing built and the first thing shipped.

    python -m foodos.agri.calibrate                 # fit to NABCONS, print the report
    python -m foodos.agri.simulate --n 100000       # write the training set

Why a new package rather than the layout in the Master Execution Blueprint: that
layout puts `engine/rul_engine.py` and `engine/optimiser.py` beside B's existing
`engine/optimiser.py`, which collides on both filename and meaning. `agri/` keeps
A's rewrite and B's shipped kitchen engine in the same repo without either team
editing the other's modules.
"""

from foodos.agri.commodity import TOMATO, Commodity, MaturityStage
from foodos.agri.kinetics import (
    arrhenius_rate_multiplier,
    q10_at,
    remaining_useful_life_hours,
    spoilage_fraction,
)

__all__ = [
    "Commodity",
    "MaturityStage",
    "TOMATO",
    "arrhenius_rate_multiplier",
    "q10_at",
    "spoilage_fraction",
    "remaining_useful_life_hours",
]
