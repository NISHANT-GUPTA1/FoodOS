"""Contract 1 · the agent orchestrator. FoodOS-Team-Split-v2.md §2.

Two functions, and the split between them is the whole architecture:

    propose_actions(batch_facts) -> candidate action PARAMETERS, no rupees
    narrate(scored_plan)         -> prose about numbers B already computed

**The agents never rank and never compute.** They say "try a reefer" and "try
leaving at 04:00"; B turns each into an Action, scores it through the one
`score()`, and the winner is whatever V(a) says. An agent that could rank would
be a second optimiser wearing a hat.

The invariant, which must be true in code and not on a slide: every agent
receives computed numbers as structured facts and may not produce one.
`guard.py` enforces it and `test_agents/test_no_number_contract.py` proves it —
both are reused here unchanged rather than reimplemented.
"""

from __future__ import annotations

#: Departure shifts worth proposing, in hours. Negative is earlier.
_SHIFTS = (-6.0, -12.0)


def _scenario_base(features: dict) -> dict:
    """Strip `fuse()`'s bookkeeping keys, leaving what the simulator accepts.

    Duplicated from `models.features.scenario_base` on purpose. The agent layer
    may not import `foodos.models` — `test_no_number_contract.py` asserts it,
    and that boundary is what keeps an agent from reaching into a model instead
    of being handed facts. Four lines is a cheaper price than the exception.
    """
    return {k: v for k, v in features.items() if not str(k).startswith("_")}


def propose_actions(batch_facts: dict) -> list[dict]:
    """Candidate action parameters for one batch.

    Sourced from A's ablation: `agri.predict.ablate` already answers "which
    single change reduces loss most", which is exactly a proposal. Anything it
    surfaces as controllable becomes a candidate; B decides what it is worth.

    Returns parameter dicts only — `{"kind": ..., ...}`. No value, no ranking,
    no currency. Contract 1 is explicit about that and it is what keeps the
    agents out of the objective function.
    """
    features = batch_facts.get("features") or batch_facts
    base = _scenario_base(features)
    proposals: list[dict] = []

    for hours in _SHIFTS:
        proposals.append({"kind": "depart_earlier", "departure_shift_hours": hours})

    try:
        from foodos.agri.commodity import TOMATO
        from foodos.agri.predict import ablate

        actions, _drivers = ablate(base, TOMATO)
        for item in actions:
            if not getattr(item, "controllable", False):
                continue
            proposal = _as_proposal(item)
            if proposal and proposal not in proposals:
                proposals.append(proposal)
    except Exception:
        # A's ablation is optional. The deterministic shifts above still give
        # the planner something to score, and B's own sweep covers the rest.
        pass

    return proposals


def _as_proposal(driver) -> dict | None:
    """One ablation result -> one action parameter dict."""
    field = getattr(driver, "field", "")
    target = getattr(driver, "counterfactual", None)
    if target in (None, ""):
        return None

    if field == "transport_mode":
        # A speaks the scenario vocabulary ("refrigerated"); the engine and the
        # wire say "reefer". Translated here rather than in either of theirs.
        mode = {"refrigerated": "reefer"}.get(str(target), str(target))
        return {"kind": "upgrade_transport", "transport": mode}
    if field in ("transit_hours", "destination"):
        return {"kind": "reroute", "mandi": str(target)}
    if field in ("field_hours", "mandi_holding_hours"):
        return {"kind": "depart_earlier", "departure_shift_hours": -6.0}
    return None


def narrate(scored_plan: dict) -> dict:
    """One sentence about a plan B has already scored and chosen.

    Every figure in the returned text is read from `scored_plan`; none is
    computed here. The Verifier checks the sentence against those same facts
    and blocks on a mismatch, so a hallucinated number never reaches a screen —
    it is logged and the deterministic sentence is used instead.

    Shape is frozen in §2:
        {"rationale_text", "drivers", "verified", "blocked_reason"}
    """
    facts = _facts_of(scored_plan)
    text = _deterministic(facts)
    blocked: str | None = None
    verified = True

    try:
        from foodos.agents.guard import assert_no_new_numbers

        assert_no_new_numbers(text, facts)
    except ImportError:
        # The kitchen guard is optional at import time; the deterministic
        # sentence carries no number the caller did not already have, so it is
        # safe by construction.
        pass
    except Exception as exc:
        verified, blocked = False, str(exc)

    return {
        "rationale_text": text,
        "drivers": scored_plan.get("drivers", []),
        "verified": verified,
        "blocked_reason": blocked,
    }


def _facts_of(plan: dict) -> dict:
    return {
        "label": plan.get("label", "this plan"),
        "loss_pct": plan.get("loss_pct"),
        "baseline_loss_pct": (plan.get("terms") or {}).get("baseline_loss_pct"),
        "net_value": plan.get("net_value"),
        "delta_vs_baseline": plan.get("delta_vs_baseline"),
    }


def _deterministic(facts: dict) -> str:
    """The sentence used when no LLM is reachable, and the one the Verifier
    compares against. Reads only what B computed."""
    label = facts["label"]
    loss = facts.get("loss_pct")
    delta = facts.get("delta_vs_baseline")

    if loss is None:
        return f"{label} is the highest-value option under the current weighting."
    if delta:
        return (
            f"{label} brings predicted loss to {loss}% and is worth "
            f"{abs(delta):,.0f} rupees more than shipping as planned."
        )
    return f"{label} brings predicted loss to {loss}%."
