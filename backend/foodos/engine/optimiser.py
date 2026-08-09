"""THE OBJECTIVE FUNCTION.

There is exactly one V(a) in FoodOS and it is `score()` below. PREVENT,
PRESERVE and RECOVER are three action spaces scored by this one function.

    V(a) =  E[ value recovered | a ]
          - cost(a)
          - P(loss | a) * value_at_risk
          + lambda * waste_aversion_per_kg * kg_food_saved
          + mu     * social_value

`kg_food_saved` is signed: an action that puts *more* food at risk than the
baseline carries a negative term, which is what makes the lambda slider push
prepared quantities down rather than merely re-rank them. CO2e is reported
alongside every decision but is not an input to the objective — pricing the
same externality twice would double-count it.

    subject to:  rsl >= lead_time + handling_margin
                 qty >= channel minimum
                 domain eligibility (set by the builder)

If you are about to write a second objective function anywhere in this
codebase: stop, and add an action type here instead. One V(a), three action
spaces, or the platform claim is fiction.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from foodos.engine.actions import Action
from foodos.engine.context import DecisionContext


@dataclass(frozen=True)
class Gate:
    ok: bool
    reason: str | None = None


def feasibility(action: Action, ctx: DecisionContext) -> Gate:
    """Universal feasibility gate.

    Applied before ranking, and its verdict is *returned*, never hidden — an
    excluded option always travels with the reason it was excluded.
    """
    if action.blocked_reason:
        return Gate(False, action.blocked_reason)

    if action.min_qty_required > 0 and action.qty + 1e-9 < action.min_qty_required:
        return Gate(
            False,
            f"below the {action.min_qty_required:g} minimum for this channel "
            f"({action.qty:g} available)",
        )

    if action.rsl_days is not None and action.lead_time_hours > 0:
        required_hours = action.lead_time_hours + ctx.handling_margin_hours
        available_hours = action.rsl_days * 24.0
        if available_hours + 1e-9 < required_hours:
            return Gate(
                False,
                f"needs {required_hours:.0f} h of remaining life "
                f"(lead time {action.lead_time_hours:.0f} h + "
                f"{ctx.handling_margin_hours:.0f} h handling); "
                f"only {available_hours:.0f} h left",
            )

    return Gate(True)


@dataclass(frozen=True)
class ScoredAction:
    action: Action
    value: float
    feasible: bool
    exclusion_reason: str | None
    terms: dict[str, float] = field(default_factory=dict)

    @property
    def net_recovery(self) -> float:
        """What a human would call 'money recovered' — before the weights."""
        return self.terms.get("recovered_value", 0.0) - self.terms.get("cost", 0.0)


def score(action: Action, ctx: DecisionContext) -> ScoredAction:
    """V(a). The only objective function in FoodOS.

    Every term is returned alongside the total so the UI can show *why* an
    action won, and so no number in the interface is unattributable.
    """
    gate = feasibility(action, ctx)

    recovered_value = action.recovered_value
    cost = action.cost
    expected_loss = action.loss_probability * action.value_at_risk
    sustainability = ctx.lam * ctx.waste_aversion_per_kg * action.kg_food_saved
    social = ctx.mu * action.social_value

    value = recovered_value - cost - expected_loss + sustainability + social

    terms = {
        "recovered_value": recovered_value,
        "cost": cost,
        "expected_loss": expected_loss,
        "sustainability": sustainability,
        "social": social,
        "total": value,
    }

    return ScoredAction(
        action=action,
        value=value if gate.ok else float("-inf"),
        feasible=gate.ok,
        exclusion_reason=gate.reason,
        terms=terms,
    )


@dataclass(frozen=True)
class RankedActions:
    ranked: list[ScoredAction]  # feasible, best first
    excluded: list[ScoredAction]  # infeasible, each with its reason

    @property
    def best(self) -> ScoredAction | None:
        return self.ranked[0] if self.ranked else None

    @property
    def baseline(self) -> ScoredAction | None:
        for s in self.ranked + self.excluded:
            if s.action.is_baseline:
                return s
        return None

    def uplift(self) -> float:
        """Value of acting versus the do-nothing baseline."""
        best, base = self.best, self.baseline
        if best is None:
            return 0.0
        if base is None:
            return best.value
        return best.value - base.value

    @property
    def all_scored(self) -> list[ScoredAction]:
        return self.ranked + self.excluded


def rank(actions: list[Action], ctx: DecisionContext) -> RankedActions:
    """Score every candidate, split feasible from excluded, order by value."""
    scored = [score(a, ctx) for a in actions]
    feasible = sorted(
        (s for s in scored if s.feasible), key=lambda s: s.value, reverse=True
    )
    excluded = [s for s in scored if not s.feasible]
    return RankedActions(ranked=feasible, excluded=excluded)


def argmax(actions: list[Action], ctx: DecisionContext) -> ScoredAction | None:
    return rank(actions, ctx).best
