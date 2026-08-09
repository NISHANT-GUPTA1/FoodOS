"""Remaining Shelf Life — Q10 spoilage kinetics.

OWNER: Person A (Data & Models).
CONTRACT (frozen at H3):
    compute_rsl(batch: dict, zone_temp_c: float, profile: dict) -> float

This is NOT "AI freshness detection" and must never be described as such. It is
a hundred-year-old rate law with four stated assumptions a chef can argue with:

    k(T)   = k_ref * Q10 ^ ((T - T_ref) / 10)

    dLife  = (dt / base_shelf_life) * Q10 ^ ((T - T_ref) / 10) / g_intake

    RSL    = base_shelf_life * (1 - sum(dLife)) * g_handling * g_cut

Note where g_intake sits: a poor crate at goods-receipt does not shorten the
clock at the end, it makes the clock run faster from the start. That is the
physically honest place for it, and it is why two crates with the same printed
date can differ by three days of usable life.

No sensor is required anywhere. Storage temperature is a declared zone value,
an uploaded log, or a simulated profile — all three are digital inputs.
"""

from __future__ import annotations

from datetime import date, datetime

import pandas as pd

from ..data import catalog as C
from . import loader

# g_handling penalties, in fractions of remaining life
ETHYLENE_PENALTY_DAYS = 0.8


def _as_date(value) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "")[:19]).date()


def life_burn_per_day(profile: dict, temp_c: float, intake_grade: float) -> float:
    """Fraction of total shelf life consumed per day held at `temp_c`."""
    accel = profile["q10"] ** ((temp_c - profile["ref_temp_c"]) / 10.0)
    return (1.0 / profile["base_shelf_life_days"]) * accel / max(intake_grade, 0.35)


def dock_life_burn(profile: dict, dwell_hours: float, intake_grade: float,
                   dock_temp_c: float = 31.0) -> float:
    """Life lost while the crate stood on the receiving dock."""
    return life_burn_per_day(profile, dock_temp_c, intake_grade) * (dwell_hours / 24.0)


def compute_rsl(batch: dict, zone_temp_c: float, profile: dict,
                as_of: str | date | None = None) -> float:
    """Remaining shelf life in days.

    batch needs: received_at, intake_grade, and optionally dock_dwell_hours,
    state ('whole' | 'cut' | 'prepared'), ethylene_neighbour (bool).
    profile needs: base_shelf_life_days, ref_temp_c, q10, cut_life_factor.
    """
    grade = float(batch.get("intake_grade", 1.0) or 1.0)
    received = _as_date(batch["received_at"])
    as_of_date = _as_date(as_of) if as_of is not None else date.fromisoformat(C.DEMO_TODAY)
    days_held = max(0, (as_of_date - received).days)

    life_used = dock_life_burn(profile, float(batch.get("dock_dwell_hours", 0.0)), grade)
    life_used += days_held * life_burn_per_day(profile, zone_temp_c, grade)

    rsl = profile["base_shelf_life_days"] * (1.0 - life_used)

    if str(batch.get("state", "whole")) in ("cut", "prepared"):
        rsl *= profile.get("cut_life_factor", 1.0)
    if batch.get("ethylene_neighbour"):
        rsl -= ETHYLENE_PENALTY_DAYS

    return round(max(0.0, rsl), 2)


def profile_for_category(category: str) -> dict:
    base, ref, q10, cut, sensitive, emitter = C.SHELF_LIFE_PROFILES[category]
    return {
        "category": category, "base_shelf_life_days": base, "ref_temp_c": ref,
        "q10": q10, "cut_life_factor": cut,
        "ethylene_sensitive": sensitive, "ethylene_emitter": emitter,
    }


def ethylene_conflicts(tables: dict[str, pd.DataFrame]) -> list[dict]:
    """Ethylene emitters sharing a storage zone with sensitive produce.

    Costs nothing to fix, measurably shortens the sensitive item's life, and is
    the cheapest recommendation the product makes.
    """
    open_b = tables["open_batches"]
    products = tables["products"]

    rows = open_b.merge(
        products[["product_id", "category", "name"]].reset_index(drop=True),
        on="product_id", how="left")
    out = []
    for zone_id, zone_rows in rows.groupby("storage_zone_id"):
        cats = {c: profile_for_category(c) for c in zone_rows["category"].unique()
                if c in C.SHELF_LIFE_PROFILES}
        emitters = sorted({r["name"] for _, r in zone_rows.iterrows()
                           if cats.get(r["category"], {}).get("ethylene_emitter")})
        sensitive = [r for _, r in zone_rows.iterrows()
                     if cats.get(r["category"], {}).get("ethylene_sensitive")]
        if not emitters or not sensitive:
            continue
        for r in sensitive:
            out.append({
                "storage_zone_id": zone_id,
                "batch_id": r["batch_id"],
                "product": r["name"],
                "qty_remaining": float(r["qty_remaining"]),
                "rsl_days": float(r["rsl_days"]),
                "life_lost_days": ETHYLENE_PENALTY_DAYS,
                "value_at_risk": round(float(r["value_on_hand"]), 2),
                "emitters_present": emitters,
                "action": f"move away from {', '.join(emitters[:2])}",
            })
    return sorted(out, key=lambda r: r["rsl_days"])[:10]


def ledger(tables: dict[str, pd.DataFrame] | None = None,
           as_of: str | None = None) -> pd.DataFrame:
    """The Food Life Ledger: every open batch with its true remaining life,
    next to the date printed on it."""
    tables = tables or loader.load_all()
    as_of = as_of or C.DEMO_TODAY

    open_b = tables["open_batches"].copy()
    receipts = tables["goods_receipt"][["batch_id", "dock_dwell_hours"]]
    products = tables["products"][["product_id", "name", "category",
                                   "is_produce"]].reset_index(drop=True)
    zones = tables["storage_zones"].set_index("storage_zone_id")["mean_temp_c"]

    df = open_b.merge(receipts, on="batch_id", how="left").merge(
        products, on="product_id", how="left")
    df["dock_dwell_hours"] = df["dock_dwell_hours"].fillna(0.0)

    computed, printed_days = [], []
    for _, r in df.iterrows():
        profile = profile_for_category(r["category"])
        computed.append(compute_rsl(
            {"received_at": r["received_at"], "intake_grade": r["intake_grade"],
             "dock_dwell_hours": r["dock_dwell_hours"], "state": r["state"]},
            float(zones.get(r["storage_zone_id"], 25.0)), profile, as_of=as_of))
        printed_days.append(
            (_as_date(r["printed_expiry"]) - _as_date(as_of)).days)

    df["rsl_days_computed"] = computed
    df["days_to_printed_expiry"] = printed_days
    df["life_overstated_days"] = (df["days_to_printed_expiry"]
                                  - df["rsl_days_computed"]).round(2)
    return df.sort_values("rsl_days_computed")


if __name__ == "__main__":
    t = loader.load_all()
    led = ledger(t)
    cols = ["batch_id", "name", "qty_remaining", "rsl_days_computed",
            "days_to_printed_expiry", "life_overstated_days", "value_on_hand"]
    print(f"\nFood Life Ledger as of {C.DEMO_TODAY} — worst 12 batches\n")
    print(led[cols].head(12).to_string(index=False))
    print(f"\ntotal value on hand   Rs {led['value_on_hand'].sum():,.0f}")
    print(f"batches whose printed date overstates true life by >1 day: "
          f"{int((led['life_overstated_days'] > 1).sum())} of {len(led)}")
    conflicts = ethylene_conflicts(t)
    print(f"\nethylene adjacency conflicts: {len(conflicts)}")
    for c in conflicts[:4]:
        print(f"  {c['product']:<18} {c['qty_remaining']:>6.2f} kg  "
              f"RSL {c['rsl_days']:.2f} d  -{c['life_lost_days']} d  {c['action']}")
