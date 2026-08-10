"""Paths, prices, lambda, and every other constant the engine reads.

One place. If a number is hard-coded anywhere in engine/, api/ or ingest/, it is a bug —
it belongs here or in backend/foodos/content/.

Owner: Person B.
"""

from __future__ import annotations

import datetime as dt
import os
from dataclasses import dataclass, field
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - optional at runtime
    pass

# backend/foodos/config.py -> backend/
BACKEND_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_ROOT.parent

DATA_DIR = BACKEND_ROOT / "data"
SAMPLE_DIR = DATA_DIR / "sample"
CONTENT_DIR = BACKEND_ROOT / "foodos" / "content"
CONTRACTS_DIR = REPO_ROOT / "contracts"
MOCK_DIR = CONTRACTS_DIR / "mock"

DB_PATH = DATA_DIR / "foodos.db"
DB_URL = f"sqlite:///{DB_PATH}"

#: CSV files the generator writes and the loader reads. Order matters — it is the
#: dependency order the seed applies them in.
CSV_FILES = (
    "demand_context.csv",
    "sales.csv",
    "production.csv",
    "batches.csv",
    "inventory_events.csv",
    "waste_events.csv",
    "zone_temperatures.csv",
)


def _date(name: str, default: str) -> dt.date:
    return dt.date.fromisoformat(os.getenv(name, default))


@dataclass(frozen=True)
class Config:
    """Every field is a default_factory so environment changes are picked up per call."""

    # --- paths -------------------------------------------------------------
    db_url: str = field(default_factory=lambda: os.getenv("FOODOS_DB_URL", DB_URL))
    data_dir: Path = field(default_factory=lambda: DATA_DIR)
    content_dir: Path = field(default_factory=lambda: CONTENT_DIR)

    # --- the objective -----------------------------------------------------
    #: Default sustainability weight. Every endpoint that depends on it takes ?lambda=
    #: and echoes the value it actually used back in the response.
    default_lambda: float = field(default_factory=lambda: float(os.getenv("FOODOS_LAMBDA", "0.5")))
    lambda_min: float = 0.0
    lambda_max: float = 1.0

    # --- demo dataset ------------------------------------------------------
    #: Must be a Tuesday. The NGO channel runs Mon/Wed/Fri, and pathology three depends
    #: on that exclusion firing. tests/test_engine/test_rescue.py asserts it.
    demo_date: dt.date = field(default_factory=lambda: _date("FOODOS_DEMO_DATE", "2026-08-11"))
    history_days: int = field(default_factory=lambda: int(os.getenv("FOODOS_HISTORY_DAYS", "180")))
    seed: int = field(default_factory=lambda: int(os.getenv("FOODOS_SEED", "20260811")))

    # --- forecasting -------------------------------------------------------
    #: Quantiles LightGBM is trained on. q* lands between 0.53 and 0.81 across the menu,
    #: so the grid brackets it comfortably and the engine interpolates between levels.
    forecast_quantiles: tuple[float, ...] = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)
    backtest_days: int = 28

    # --- risk thresholds ---------------------------------------------------
    critical_rsl_days: float = 1.0
    warning_rsl_days: float = 2.5

    # --- recommendations ---------------------------------------------------
    #: Recommendations worth less than this are noise and are not shown. A manager who
    #: is handed twenty cards acts on none of them.
    min_saving_inr: float = 75.0
    max_recommendations: int = 12
    recommendation_ttl_hours: int = 14

    @property
    def demo_datetime(self) -> dt.datetime:
        """Service-time on the demo date. Cutoff checks are made against this."""
        return dt.datetime.combine(self.demo_date, dt.time(11, 30))

    def clamp_lambda(self, value: float | None) -> float:
        if value is None:
            return self.default_lambda
        return max(self.lambda_min, min(self.lambda_max, float(value)))


def get_config() -> Config:
    return Config()


#: Convenience singleton for modules that do not need a fresh read.
config = get_config()
