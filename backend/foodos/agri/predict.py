"""Inference — one shipment in, a Batch Intelligence profile out.

This is the entry point the API and the agents call. It assembles Screen 3
(Batch Intelligence) and Screen 4 (What-If) from four things:

  point estimate   the simulator, which is authoritative. Not the surrogate.
  interval         Monte Carlo over input uncertainty (see `uncertainty`)
  drivers          per-shipment ablation, not global feature importance
  actions          the same ablation, restricted to what the user can change

**Why ablation rather than the model's feature importance.** Gain importance is
a global statement — "maturity matters across the dataset" — and a manager
holding one consignment cannot act on it. Ablation asks the question they
actually have: *hold this shipment fixed, change one thing, how much loss goes
away?* The answer is in percentage points and kilograms for this lot, it is
exact rather than attributed, and it doubles as the candidate action set the
optimiser scores. One mechanism, three uses.

It is also cheap. Each ablation is one simulator call at roughly 50
microseconds, so a full driver panel costs less than a millisecond.

**Controllable and uncontrollable are kept apart.** Ambient temperature is a
driver of loss but not an action — telling an FPO manager to make August cooler
is not a recommendation. Only the controllable set becomes actions; the rest is
explanation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

import numpy as np

from foodos.agri.commodity import TOMATO, Commodity
from foodos.agri.scenario import (
    FieldHolding,
    HarvestMethod,
    HarvestWindow,
    Packaging,
    ScenarioBatch,
    TransportMode,
)
from foodos.agri.simulate import FARM_STAGES, MARKET_STAGES, STAGES, simulate
from foodos.agri.uncertainty import Interval, intervals, sensitivity

#: Categorical choices an FPO can actually make. The ablation **searches these**
#: rather than assuming a single best option, and that is not fussiness — the
#: assumption is provably false.
#:
#: An earlier version hardcoded "pre-dawn is the best harvest window". On a
#: thirty-six hour haul it is not: harvesting at 05:00 puts dispatch at 09:30
#: and drags the whole run through the afternoon peak, so it comes out slightly
#: *worse* than a morning pick. A test caught it. The same trap is waiting in
#: every other field, so no field gets a presumed answer.
#:
#: Cost of searching instead of assuming: about twenty extra simulator calls,
#: which is a millisecond.
CONTROLLABLE_CHOICES: dict[str, list] = {
    "harvest_window": list(HarvestWindow),
    "harvest_method": list(HarvestMethod),
    "field_holding": list(FieldHolding),
    "packaging": list(Packaging),
    "transport_mode": list(TransportMode),
}

#: Continuous controls where less is monotonically better — asserted by
#: `test_loss_is_monotonic_in_every_driver`, so a target value is safe here in a
#: way it is not for the categoricals above. These are floors an FPO can
#: realistically hit, not zero.
CONTROLLABLE_TARGETS: dict[str, float] = {
    "field_hours": 1.0,
    "mandi_holding_hours": 2.0,
}

#: Drivers the manager cannot change for this consignment. Explanation only.
UNCONTROLLABLE: dict[str, object] = {
    "ambient_mean_c": 22.0,      # what a cool day would have done
    "maturity_factor": 1.30,     # what picking at breaker stage would have done
    "visual_damage_fraction": 0.0,
    "road_roughness": 1.0,       # a national highway rather than a link road
    "transit_hours": None,       # filled per shipment: halve it
}

_LABELS = {
    "harvest_window": "harvest window",
    "harvest_method": "harvest method",
    "field_holding": "field holding",
    "field_hours": "hours held in the field",
    "packaging": "packaging",
    "transport_mode": "transport mode",
    "mandi_holding_hours": "hours held at the mandi",
    "ambient_mean_c": "ambient temperature",
    "maturity_factor": "harvest maturity",
    "visual_damage_fraction": "damage at intake",
    "road_roughness": "road quality",
    "transit_hours": "transit duration",
}


@dataclass
class Driver:
    field: str
    label: str
    current: object
    counterfactual: object
    loss_reduction_pp: float
    mass_saved_kg: float
    controllable: bool


@dataclass
class BatchIntelligence:
    """Everything Screen 3 renders, computed and traceable."""

    commodity: str
    quantity_kg: float
    loss_pct: float
    loss_low_pct: float
    loss_high_pct: float
    mass_at_risk_kg: float
    rul_hours: float
    rul_low_hours: float
    rul_high_hours: float
    quality_score: float
    risk_level: str
    stage_losses_pp: dict[str, float]
    farm_operations_pp: float
    market_level_pp: float
    drivers: list[Driver] = field(default_factory=list)
    actions: list[Driver] = field(default_factory=list)
    biggest_unknown: str | None = None

    def as_dict(self) -> dict:
        out = asdict(self)
        out["drivers"] = [asdict(d) for d in self.drivers]
        out["actions"] = [asdict(d) for d in self.actions]
        return out


def _one(base: dict, commodity: Commodity = TOMATO) -> ScenarioBatch:
    """A single-row scenario batch from a plain dict."""
    string_fields = {
        "harvest_method",
        "harvest_window",
        "field_holding",
        "packaging",
        "transport_mode",
    }
    columns = {
        key: (np.array([str(value)]) if key in string_fields else np.array([float(value)]))
        for key, value in base.items()
    }
    return ScenarioBatch(n=1, commodity=commodity, meta={"sampler": "single"}, **columns)


def run(base: dict, commodity: Commodity = TOMATO) -> dict:
    """Simulate one shipment and return its row as a plain dict."""
    return simulate(_one(base, commodity)).iloc[0].to_dict()


def risk_level(loss_fraction: float) -> str:
    """Screen 1's traffic light. Thresholds are the ones the Command Center
    groups on, so they live here rather than being re-invented in the UI."""
    if loss_fraction >= 0.12:
        return "high"
    if loss_fraction >= 0.06:
        return "medium"
    return "low"


def ablate(
    base: dict,
    commodity: Commodity = TOMATO,
    include_uncontrollable: bool = True,
) -> tuple[list[Driver], list[Driver]]:
    """Change one input at a time; measure what the change is worth.

    Returns (actions, drivers) — the controllable set and the explanatory set,
    each ranked by loss removed.
    """
    row = run(base, commodity)
    current_loss = float(row["total_loss"])
    quantity = float(base["quantity_kg"])

    def measure(field_name: str, value: object, controllable: bool) -> Driver | None:
        if value is None or str(base[field_name]) == str(value):
            return None
        trial = {**base, field_name: value}
        reduction = current_loss - float(run(trial, commodity)["total_loss"])
        return Driver(
            field=field_name,
            label=_LABELS.get(field_name, field_name),
            current=base[field_name],
            counterfactual=value,
            loss_reduction_pp=round(reduction * 100.0, 3),
            mass_saved_kg=round(reduction * quantity, 1),
            controllable=controllable,
        )

    actions: list[Driver] = []

    # Categoricals: try every option, keep the best. Never presume one wins.
    for field_name, options in CONTROLLABLE_CHOICES.items():
        candidates = [
            d
            for option in options
            if (d := measure(field_name, option, True)) is not None
        ]
        if candidates:
            best = max(candidates, key=lambda d: d.loss_reduction_pp)
            if best.loss_reduction_pp > 0.0:
                actions.append(best)

    # Continuous: monotone, so the floor is the best attainable value.
    for field_name, target in CONTROLLABLE_TARGETS.items():
        if float(base[field_name]) <= target:
            continue
        if (d := measure(field_name, target, True)) is not None and d.loss_reduction_pp > 0.0:
            actions.append(d)

    drivers: list[Driver] = []
    if include_uncontrollable:
        for field_name, value in UNCONTROLLABLE.items():
            target = (
                float(base[field_name]) * 0.5 if field_name == "transit_hours" else value
            )
            if (d := measure(field_name, target, False)) is not None:
                drivers.append(d)

    actions.sort(key=lambda d: d.loss_reduction_pp, reverse=True)
    drivers.sort(key=lambda d: d.loss_reduction_pp, reverse=True)
    return actions, drivers


def predict(
    base: dict,
    commodity: Commodity = TOMATO,
    mc_draws: int = 2_000,
    with_sensitivity: bool = True,
) -> BatchIntelligence:
    """The full Batch Intelligence profile for one shipment."""
    row = run(base, commodity)
    band = intervals(base, n=mc_draws, commodity=commodity)
    actions, drivers = ablate(base, commodity)

    biggest_unknown = None
    if with_sensitivity:
        ranked = sensitivity(base, n=max(mc_draws // 2, 400), commodity=commodity)
        if ranked and ranked[0]["share_of_width"] > 0.15:
            biggest_unknown = ranked[0]["field"]

    loss = float(row["total_loss"])
    return BatchIntelligence(
        commodity=commodity.name,
        quantity_kg=float(base["quantity_kg"]),
        loss_pct=round(loss * 100.0, 2),
        loss_low_pct=round(band["loss"].low, 2),
        loss_high_pct=round(band["loss"].high, 2),
        mass_at_risk_kg=round(loss * float(base["quantity_kg"]), 1),
        rul_hours=round(float(row["rul_hours_at_dispatch"]), 1),
        rul_low_hours=round(band["rul"].low, 1),
        rul_high_hours=round(band["rul"].high, 1),
        quality_score=round(float(row["quality_score"]), 1),
        risk_level=risk_level(loss),
        stage_losses_pp={s: round(float(row[f"loss_{s}"]) * 100.0, 3) for s in STAGES},
        farm_operations_pp=round(float(row["farm_operations_loss"]) * 100.0, 2),
        market_level_pp=round(float(row["market_level_loss"]) * 100.0, 2),
        actions=actions,
        drivers=drivers,
        biggest_unknown=biggest_unknown,
    )


def what_if(base: dict, commodity: Commodity = TOMATO, **changes) -> dict:
    """Screen 4. Apply slider changes and report the delta against the plan.

    Fast enough to call on every drag: one simulator run each side.
    """
    before = run(base, commodity)
    after = run({**base, **changes}, commodity)
    delta = float(before["total_loss"]) - float(after["total_loss"])
    quantity = float(base["quantity_kg"])

    return {
        "changes": {k: str(v) for k, v in changes.items()},
        "loss_before_pct": round(float(before["total_loss"]) * 100.0, 2),
        "loss_after_pct": round(float(after["total_loss"]) * 100.0, 2),
        "loss_reduction_pp": round(delta * 100.0, 2),
        "mass_saved_kg": round(delta * quantity, 1),
        "rul_before_hours": round(float(before["rul_hours_at_dispatch"]), 1),
        "rul_after_hours": round(float(after["rul_hours_at_dispatch"]), 1),
    }
