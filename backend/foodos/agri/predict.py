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

from foodos.agri import i18n
from foodos.agri.commodity import TOMATO, Commodity
from foodos.agri.i18n import Locale
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

#: Fields whose values are questionnaire answers rather than numbers, so their
#: values localise through `i18n.option()` rather than being formatted.
_CATEGORICAL_FIELDS = frozenset(CONTROLLABLE_CHOICES)


def _value_label(field_name: str, value: object, locale: Locale) -> str:
    """A field value as a user would read it, in their language."""
    if field_name in _CATEGORICAL_FIELDS:
        return i18n.option(str(value), locale)
    return i18n.format_indian(float(value), decimals=1)


@dataclass
class Driver:
    field: str
    label: str
    current: object
    counterfactual: object
    loss_reduction_pp: float
    mass_saved_kg: float
    controllable: bool
    #: Localised, ready to render. Kept alongside the raw values rather than
    #: replacing them so the optimiser still sees machine-readable answers.
    current_label: str = ""
    counterfactual_label: str = ""


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

    #: Everything below is display-ready in the requested language. The numeric
    #: fields above stay machine-readable — the optimiser and the API must never
    #: have to parse a localised string back into a number.
    locale: str = str(i18n.DEFAULT_LOCALE)
    commodity_label: str = ""
    risk_label: str = ""
    biggest_unknown_label: str | None = None
    #: Set when the requested language was too sparsely translated to render
    #: readably, so this profile is in `locale` instead. The UI should say so.
    requested_locale_unavailable: str | None = None

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
    locale: Locale = i18n.DEFAULT_LOCALE,
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
            label=i18n.field_label(field_name, locale),
            current=base[field_name],
            counterfactual=value,
            loss_reduction_pp=round(reduction * 100.0, 3),
            mass_saved_kg=round(reduction * quantity, 1),
            controllable=controllable,
            current_label=_value_label(field_name, base[field_name], locale),
            counterfactual_label=_value_label(field_name, value, locale),
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
    locale: Locale = i18n.DEFAULT_LOCALE,
) -> BatchIntelligence:
    """The full Batch Intelligence profile for one shipment.

    `locale` defaults to Hindi, because the primary user reads Hindi and a
    default of English would make the shipped behaviour the wrong one.
    """
    # Resolve before rendering anything: a locale too sparsely translated to be
    # readable substitutes wholesale rather than mixing scripts mid-sentence.
    locale, unavailable = i18n.resolve_locale(locale)

    row = run(base, commodity)
    band = intervals(base, n=mc_draws, commodity=commodity)
    actions, drivers = ablate(base, commodity, locale=locale)

    biggest_unknown = None
    if with_sensitivity:
        ranked = sensitivity(base, n=max(mc_draws // 2, 400), commodity=commodity)
        if ranked and ranked[0]["share_of_width"] > 0.15:
            biggest_unknown = ranked[0]["field"]

    loss = float(row["total_loss"])
    return BatchIntelligence(
        locale=str(locale),
        requested_locale_unavailable=str(unavailable) if unavailable else None,
        commodity_label=i18n.commodity_name(commodity.key, locale),
        risk_label=i18n.t(f"out.risk.{risk_level(loss)}", locale),
        biggest_unknown_label=(
            i18n.field_label(biggest_unknown, locale) if biggest_unknown else None
        ),
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


def render_advisory(
    profile: BatchIntelligence, locale: Locale | None = None
) -> str:
    """The one message an FPO manager receives, in their language.

    This is the actual deliverable of the whole engine. Everything upstream —
    Arrhenius, the lognormal, the Monte Carlo, the ablation — exists so that
    these four lines are true. The product's own design rule is one number per
    person, so this is deliberately short and leads with the decision rather
    than with the diagnosis.

    Reads only fields already computed on the profile. It formats; it never
    calculates, so no figure here can disagree with the API response.
    """
    loc = Locale(locale or profile.locale)

    headline = i18n.t("msg.headline", loc).format(
        qty=i18n.format_kg(profile.quantity_kg, loc),
        commodity=profile.commodity_label or profile.commodity,
        loss=i18n.format_pct(profile.loss_pct, loc),
        mass=i18n.format_kg(profile.mass_at_risk_kg, loc),
    )
    lines = [
        headline,
        i18n.t("msg.rul", loc).format(hours=i18n.format_hours(profile.rul_hours, loc)),
        f"{i18n.t('out.risk.' + profile.risk_level, loc)}",
    ]

    if profile.actions:
        best = profile.actions[0]
        lines.append(
            i18n.t("msg.action", loc).format(
                label=best.label,
                change=f"{best.current_label} → {best.counterfactual_label}",
                mass=i18n.format_kg(best.mass_saved_kg, loc),
            )
        )

    if profile.biggest_unknown_label:
        lines.append(
            f"{i18n.t('out.biggest_unknown', loc)}: {profile.biggest_unknown_label}"
        )

    return "\n".join(lines)


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
