"""Table loading for the model layer.

OWNER: Person A (Data & Models).

Person B's engine will read the same tables out of SQLite. Everything in
`foodos/models/` takes DataFrames, so swapping the source is a one-line change
here and nothing downstream moves.
"""

from __future__ import annotations

import os
from functools import lru_cache

import pandas as pd

DEFAULT_DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "sample",
)

TABLES = [
    "sites", "storage_zones", "products", "recipes", "demand_context",
    "sales", "production", "goods_receipt", "waste", "open_batches",
    "inventory_events",
]


@lru_cache(maxsize=4)
def load_all(data_dir: str = DEFAULT_DATA_DIR) -> dict[str, pd.DataFrame]:
    """Every table, keyed by name without the .csv."""
    out = {}
    for name in TABLES:
        path = os.path.join(data_dir, f"{name}.csv")
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"{path} is missing. Run:  python -m foodos.data.generate"
            )
        out[name] = pd.read_csv(path)
    out["waste"]["business_date"] = out["waste"]["business_date"].astype(str)
    out["products"] = out["products"].set_index("product_id", drop=False)
    return out


def product_name(tables: dict[str, pd.DataFrame], product_id: str) -> str:
    try:
        return str(tables["products"].loc[product_id, "name"])
    except KeyError:
        return product_id


def dishes(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    p = tables["products"]
    return p[p["is_dish"] == 1]


def ingredients(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    p = tables["products"]
    return p[p["is_dish"] == 0]
