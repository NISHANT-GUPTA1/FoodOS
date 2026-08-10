"""The agri transit action space — builders only, no ranking, no objective.

FoodOS-Team-Split-v2.md §4, H8-13. This module answers one question: *what could
we do with this consignment?* It answers it as `Action` objects with the terms
`score()` consumes already populated. It does not decide which is best — that is
`optimiser.rank()`, and there is exactly one of those.

B's hard rule, and the reason this file is short: **`score()` is not edited.**
Every action here is a different shape of the same V(a). If this file grows past
300 lines it has stopped being an action space and become a second optimiser.

Loss under each action comes from A's model (`agri.predict.what_if`), never from
arithmetic invented here — a second decay model is the first thing Ruling 1
forbids. When A is unreachable the builder falls back to the baseline loss and
stamps `degraded` into `facts`: an A outage costs accuracy, never a screen.

Horizons follow §4 — PREVENT changes the journey (depart_earlier,
upgrade_transport), PRESERVE changes the destination (reroute, split_batch),
RECOVER accepts it will not arrive saleable (divert_to_channel).
"""

from __future__ import annotations

from dataclasses import dataclass

from foodos import content
from foodos.engine.actions import Action
from foodos.schema.enums import ActionType, Horizon

#: Fallback mandi price when D's content has none for a destination.
DEFAULT_PRICE_PER_KG = 22.0

#: Loading, paperwork and driver cost of leaving outside the planned slot.
DEPARTURE_SHIFT_COST = 900.0

#: A split pays a second drop fee and a second unload.
SPLIT_FIXED_COST = 2400.0


@dataclass(frozen=True)
class TransitSubject:
    """Everything a builder needs about the consignment under consideration.

    A plain value object rather than the ORM row on purpose: the simulator
    (§4 H17-21) builds one straight from Screen 4's sliders with no database
    write and gets plans through the identical code path.
    """

    consignment_id: int
    code: str
    commodity: str
    qty_kg: float
    origin: str
    destination: str
    transport: str
    packaging: str
    transit_hours: float
    price_per_kg: float = DEFAULT_PRICE_PER_KG
    #: Route length, for the per-km cost of a transport upgrade. Kept here and
    #: NOT in `base`: `base` is A's ScenarioBatch input and rejects stray keys.
    distance_km: float = 0.0
    #: A's `base` dict — the input to `agri.predict.what_if`.
    base: dict | None = None
    baseline_loss_pct: float = 0.0


def _loss_under(subject: TransitSubject, **changes) -> tuple[float, bool]:
    """Ask A's model what the loss becomes under `changes`.

    Returns (loss_pct, degraded). `degraded` is True when A could not be reached
    and the baseline was substituted, so the UI can say the figure is a fallback
    rather than a prediction.
    """
    if not subject.base:
        return subject.baseline_loss_pct, True
    try:
        from foodos.agri.predict import what_if  # noqa: PLC0415 — optional at import

        return float(what_if(dict(subject.base), **changes)["loss_after_pct"]), False
    except Exception:
        return subject.baseline_loss_pct, True


def _build(
    subject: TransitSubject,
    action_type: ActionType,
    horizon: Horizon,
    label: str,
    params: dict,
    loss_pct: float,
    cost: float,
    *,
    degraded: bool = False,
    revenue: float | None = None,
    price_per_kg: float | None = None,
    social_value: float = 0.0,
    kg_food_saved: float | None = None,
    channel_id: int | None = None,
    blocked_reason: str | None = None,
) -> Action:
    """Construct one Action with the five terms `score()` reads.

    `Action` is frozen, so everything is computed before construction. The
    arithmetic is identical for every builder — only the loss A predicts and
    the cost vary. That is what keeps this an action space, not an optimiser.
    """
    price = price_per_kg if price_per_kg is not None else subject.price_per_kg
    arriving_kg = subject.qty_kg * (1.0 - loss_pct / 100.0)
    saved_kg = max(subject.baseline_loss_pct - loss_pct, 0.0) / 100.0 * subject.qty_kg

    return Action(
        action_type=action_type,
        horizon=horizon,
        label=label,
        subject_type="consignment",
        subject_id=subject.consignment_id,
        subject_label=f"{subject.code} · {subject.commodity}",
        qty=subject.qty_kg,
        qty_kg=subject.qty_kg,
        baseline_qty=subject.qty_kg,
        recovered_value=revenue if revenue is not None else arriving_kg * price,
        cost=cost,
        loss_probability=loss_pct / 100.0,
        value_at_risk=subject.qty_kg * subject.price_per_kg,
        kg_food_saved=saved_kg if kg_food_saved is None else kg_food_saved,
        social_value=social_value,
        lead_time_hours=subject.transit_hours,
        blocked_reason=blocked_reason,
        channel_id=channel_id,
        params=params,
        facts={
            "loss_pct": round(loss_pct, 2),
            "baseline_loss_pct": round(subject.baseline_loss_pct, 2),
            "arriving_kg": round(arriving_kg, 1),
            "price_per_kg": price,
            "degraded": degraded,
        },
    )


def do_nothing(subject: TransitSubject) -> Action:
    """Ship it exactly as planned. Always present, always scored.

    Contract 2b guarantees exactly one row with `is_baseline: true`, and every
    other plan's `delta_vs_baseline` is measured against it. A matrix without it
    has nothing to compare against.
    """
    return _build(
        subject,
        ActionType.DO_NOTHING,
        Horizon.PREVENT,
        f"Ship as planned — {subject.transport.replace('_', ' ')} to {subject.destination}",
        {"kind": "do_nothing"},
        subject.baseline_loss_pct,
        0.0,
    )


def depart_earlier(subject: TransitSubject, hours: float) -> Action:
    """Leave `hours` earlier, moving transit into the cool part of the night.

    A's scenario expresses this as `field_hours` — time the load sits at the
    collection point before the truck moves. Six hours earlier is six fewer
    hours in the sun at the origin. Note ScenarioBatch has no
    `departure_shift_hours`; passing one silently returns the baseline.
    """
    field_hours = max(float((subject.base or {}).get("field_hours", 0.0)) + hours, 0.0)
    loss, degraded = _loss_under(subject, field_hours=field_hours)
    return _build(
        subject,
        ActionType.DEPART_EARLIER,
        Horizon.PREVENT,
        f"Depart {abs(hours):.0f}h {'earlier' if hours < 0 else 'later'}",
        {"kind": "depart_earlier", "departure_shift_hours": hours},
        loss,
        DEPARTURE_SHIFT_COST,
        degraded=degraded,
    )


def upgrade_transport(subject: TransitSubject, mode: str) -> Action:
    """Move to a cooler vehicle class.

    Cost is D's `cost_per_km` delta across the real route distance, not a flat
    fee. A reefer over 2,150 km is a different decision from one over 90 km,
    and flattening that is how you end up refrigerating a trip to the next village.
    """
    modes = content.transport_modes()
    here, there = modes.get(subject.transport, {}), modes.get(mode, {})
    delta = float(there.get("cost_per_km", 0.0)) - float(here.get("cost_per_km", 0.0))
    loss, degraded = _loss_under(
        subject, transport_mode=there.get("agri_scenario_key", mode)
    )
    return _build(
        subject,
        ActionType.UPGRADE_TRANSPORT,
        Horizon.PREVENT,
        f"Upgrade to {there.get('display_name', mode)}",
        {"kind": "upgrade_transport", "transport": mode},
        loss,
        max(delta, 0.0) * subject.distance_km,
        degraded=degraded,
    )


def reroute(subject: TransitSubject, mandi_key: str) -> Action:
    """Send the whole load to a nearer mandi.

    Shorter transit means less accumulated thermal stress but usually a lower
    price. Settling that trade is what `score()` is for, so both sides are
    handed over rather than pre-judged here.
    """
    target = content.mandis().get(mandi_key, {})
    hours = float(target.get("typical_transit_hours", subject.transit_hours))
    price = float(target.get("price_per_kg", subject.price_per_kg))
    loss, degraded = _loss_under(subject, transit_hours=hours)

    absorption = float(target.get("daily_absorption_kg", 0.0))
    blocked = None
    if absorption and subject.qty_kg > absorption:
        blocked = (
            f"{target.get('display_name', mandi_key)} absorbs about "
            f"{absorption:,.0f} kg a day; this load is {subject.qty_kg:,.0f} kg"
        )

    return _build(
        subject,
        ActionType.REROUTE,
        Horizon.PRESERVE,
        f"Reroute to {target.get('display_name', mandi_key)}",
        {"kind": "reroute", "mandi": mandi_key},
        loss,
        0.0,
        degraded=degraded,
        price_per_kg=price,
        blocked_reason=blocked,
    )


def split_batch(subject: TransitSubject, allocations: list[dict]) -> Action:
    """Two destinations, one drop each.

    Sized to what each mandi can actually absorb, so the second drop earns its
    price instead of flooding a market and taking the whole load down with it.
    """
    mandis = content.mandis()
    labels, revenue, weighted = [], 0.0, 0.0

    for leg in allocations:
        target = mandis.get(leg["mandi"], {})
        qty = float(leg["qty_kg"])
        hours = float(target.get("typical_transit_hours", subject.transit_hours))
        price = float(target.get("price_per_kg", subject.price_per_kg))
        loss, _ = _loss_under(subject, transit_hours=hours)
        revenue += qty * (1.0 - loss / 100.0) * price
        weighted += loss * qty
        labels.append(f"{qty / 1000:.0f}T {target.get('display_name', leg['mandi'])}")

    total = sum(float(a["qty_kg"]) for a in allocations) or subject.qty_kg
    blocked = None
    if abs(total - subject.qty_kg) > 1.0:
        blocked = f"allocations total {total:,.0f} kg against a {subject.qty_kg:,.0f} kg load"

    return _build(
        subject,
        ActionType.SPLIT_BATCH,
        Horizon.PRESERVE,
        "Split " + " / ".join(labels),
        {"kind": "split_batch", "destinations": allocations},
        weighted / total,
        SPLIT_FIXED_COST,
        revenue=revenue,
        blocked_reason=blocked,
    )


def divert_to_channel(subject: TransitSubject, channel: dict) -> Action:
    """Send it somewhere other than a mandi — processing, donation, feed.

    Reuses the channel vocabulary the kitchen rescue waterfall already ranks
    against, so this is the existing RECOVER horizon reaching a new subject
    type rather than a parallel one.
    """
    recovery = float(channel.get("recovery_factor", 0.0))
    arriving_kg = subject.qty_kg * (1.0 - subject.baseline_loss_pct / 100.0)
    feeds_humans = bool(channel.get("feeds_a_human", True))

    return _build(
        subject,
        ActionType.DIVERT_TO_CHANNEL,
        Horizon.RECOVER,
        f"Divert to {channel.get('name', channel.get('id', 'channel'))}",
        {"kind": "divert_to_channel", "channel": channel.get("id")},
        subject.baseline_loss_pct,
        float(channel.get("fixed_cost", 0.0)),
        revenue=arriving_kg * subject.price_per_kg * recovery,
        social_value=arriving_kg * float(channel.get("social_value_per_kg", 0.0)),
        kg_food_saved=arriving_kg if feeds_humans else 0.0,
        channel_id=channel.get("db_id"),
    )
