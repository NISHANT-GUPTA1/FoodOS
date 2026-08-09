"""Model layer — Person A.

The four functions frozen in the H3 contract. Person B's engine imports only
these; everything else in this package is internal.
"""

from .attribution import attribute
from .backtest import run_backtest
from .forecast import predict_quantiles, train
from .rsl import compute_rsl, ledger

__all__ = ["attribute", "train", "predict_quantiles", "compute_rsl", "ledger",
           "run_backtest"]
