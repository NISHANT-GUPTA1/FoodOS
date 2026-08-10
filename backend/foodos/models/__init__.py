"""Model layer — Person A.

The four functions frozen in the H3 contract, re-exported here.

Post-merge note: the engine also imports the injected-data layer directly from the
submodules (`attribution.attribute_window`, `backtest.run_backtest_holdout`, and
`rsl.assess_risk` / `remaining_shelf_life` / `life_gain_from_rezone` / `severity`).
Those are deliberately NOT re-exported — the H3 contract names below are the stable
surface, and the injected layer is still being reconciled with it.
"""

from .attribution import attribute
from .backtest import run_backtest
from .forecast import predict_quantiles, train
from .rsl import compute_rsl, ledger

__all__ = ["attribute", "train", "predict_quantiles", "compute_rsl", "ledger",
           "run_backtest"]
