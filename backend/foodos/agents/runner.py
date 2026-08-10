"""CLI entry point and the API-to-facts mapping.

    python -m foodos.agents.runner diagnose --demo
    python -m foodos.agents.runner plan --api http://localhost:8000
    python -m foodos.agents.runner communicate --fixture contracts/mock
    python -m foodos.agents.runner all --demo
    python -m foodos.agents.runner log

The builders below are the seam against Person B's contract. They are deliberately tolerant
about field names and brutally specific when a field is missing, so wiring against the real
API at H16 is a matter of editing one dictionary rather than hunting through agent code.

Owner: Person D.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any, Iterable, Mapping, Sequence

from . import audit, demo_facts
from .api_client import ApiError, FixtureClient, FoodosApiClient
from .base import AgentOutput
from .communicator import Communicator
from .diagnostician import Diagnostician
from .facts import (
    UNIT_DAYS,
    UNIT_INR,
    UNIT_KG,
    UNIT_PCT,
    UNIT_PORTIONS,
    UNIT_TEXT,
    Fact,
    FactSet,
)
from .planner import Planner
from .settings import get_settings

_MISSING = object()


def pick(payload: Mapping[str, Any], candidates: Sequence[str], *, default: Any = _MISSING) -> Any:
    """First present key from ``candidates``, supporting dotted paths.

    The contract freezes at H3 and this is where a late rename gets absorbed.
    """
    for path in candidates:
        node: Any = payload
        ok = True
        for part in path.split("."):
            if isinstance(node, Mapping) and part in node:
                node = node[part]
            else:
                ok = False
                break
        if ok and node is not None:
            return node
    if default is not _MISSING:
        return default
    raise KeyError(
        f"none of {list(candidates)} found in payload with keys {sorted(payload)}. "
        "Update the field map in foodos/agents/runner.py to match the frozen contract."
    )


# --- API payload -> FactSet --------------------------------------------------

def facts_from_why(payload: Mapping[str, Any]) -> FactSet:
    contributors: Iterable[Mapping[str, Any]] = pick(payload, ["contributors", "attribution", "items"])
    ranked = sorted(contributors, key=lambda c: float(pick(c, ["share", "share_pct", "pct"])), reverse=True)
    if not ranked:
        raise ValueError("/api/why returned no contributors — nothing to diagnose")

    top = ranked[0]
    out = FactSet(
        [
            Fact("top_contributor_name", str(pick(top, ["name", "label", "contributor"])), UNIT_TEXT,
                 "largest contributor", source="engine:/api/why"),
            Fact("top_contributor_share", float(pick(top, ["share", "share_pct", "pct"])), UNIT_PCT,
                 "its share of value at risk", source="engine:/api/why"),
        ]
    )
    if len(ranked) > 1:
        second = ranked[1]
        out.add(Fact("second_contributor_name", str(pick(second, ["name", "label", "contributor"])),
                     UNIT_TEXT, "second contributor", source="engine:/api/why"))
        out.add(Fact("second_contributor_share", float(pick(second, ["share", "share_pct", "pct"])),
                     UNIT_PCT, "its share of value at risk", source="engine:/api/why"))

    value = pick(payload, ["value_at_risk", "inr_at_risk", "kpis.value_at_risk"], default=None)
    if value is not None:
        out.add(Fact("value_at_risk", float(value), UNIT_INR, "value at risk today", source="engine:/api/why"))
    dish = pick(payload, ["worst_dish", "top_dish", "worst_dish_name"], default=None)
    if dish is not None:
        out.add(Fact("worst_dish_name", str(dish), UNIT_TEXT, "dish carrying the most risk", source="engine:/api/why"))
    return out


def facts_from_rescue_special(payload: Mapping[str, Any]) -> FactSet:
    """Planner facts: the at-risk batch plus the special the optimiser chose for it."""
    batch = pick(payload, ["batch", "item", "at_risk"])
    special = pick(payload, ["special", "recommended_special", "recommendation"])
    return FactSet(
        [
            Fact("batch_id", str(pick(batch, ["id", "batch_id"])), UNIT_TEXT, "batch identifier", source="engine:/api/rescue"),
            Fact("batch_ingredient_name", str(pick(batch, ["ingredient_name", "name", "product"])), UNIT_TEXT,
                 "ingredient at risk", source="engine:/api/rescue"),
            Fact("batch_zone_name", str(pick(batch, ["zone_name", "zone", "storage_zone"])), UNIT_TEXT,
                 "where it is stored", source="engine:/api/rescue"),
            Fact("batch_qty_kg", float(pick(batch, ["qty_kg", "quantity_kg", "qty"])), UNIT_KG,
                 "quantity on hand", precision=1, source="engine:/api/rescue"),
            Fact("batch_rsl_days", float(pick(batch, ["rsl_days", "remaining_shelf_life_days", "rsl"])), UNIT_DAYS,
                 "remaining shelf life", precision=1, source="model:rsl"),
            Fact("special_dish_name", str(pick(special, ["dish_name", "name", "dish"])), UNIT_TEXT,
                 "dish the optimiser selected", source="engine:/api/rescue"),
            Fact("special_portions", float(pick(special, ["portions", "qty_portions"])), UNIT_PORTIONS,
                 "portions the batch covers", source="engine:/api/rescue"),
            Fact("special_value_inr", float(pick(special, ["value_inr", "recovered_value", "saving_inr"])), UNIT_INR,
                 "contribution recovered by running the special", source="engine:/api/rescue"),
            Fact("station_name", str(pick(special, ["station", "station_name"], default="Gravy")), UNIT_TEXT,
                 "prep station that owns the work", source="content:recipes"),
        ]
    )


def facts_from_transfer(payload: Mapping[str, Any]) -> FactSet:
    """Communicator facts: the batch and the winning transfer channel."""
    batch = pick(payload, ["batch", "item", "at_risk"])
    channels = pick(payload, ["channels", "options", "ranked_channels"])
    eligible = [c for c in channels if not pick(c, ["excluded", "is_excluded"], default=False)]
    if not eligible:
        raise ValueError("/api/rescue returned no eligible channel — nothing to communicate")
    winner = eligible[0]

    return FactSet(
        [
            Fact("batch_id", str(pick(batch, ["id", "batch_id"])), UNIT_TEXT, "batch identifier", source="engine:/api/rescue"),
            Fact("outlet_name", str(pick(winner, ["counterparty", "outlet_name", "destination"], default="the other outlet")),
                 UNIT_TEXT, "receiving outlet", source="engine:/api/rescue"),
            Fact("batch_ingredient_name", str(pick(batch, ["ingredient_name", "name", "product"])), UNIT_TEXT,
                 "ingredient being transferred", source="engine:/api/rescue"),
            Fact("batch_qty_kg", float(pick(batch, ["qty_kg", "quantity_kg", "qty"])), UNIT_KG,
                 "quantity to transfer", precision=1, source="engine:/api/rescue"),
            Fact("batch_rsl_days", float(pick(batch, ["rsl_days", "remaining_shelf_life_days", "rsl"])), UNIT_DAYS,
                 "remaining shelf life", precision=1, source="model:rsl"),
            Fact("transfer_value_inr", float(pick(winner, ["value_inr", "recovered_value", "recovery_inr"])), UNIT_INR,
                 "value recovered by the transfer", source="engine:/api/rescue"),
            Fact("pickup_by", str(pick(winner, ["pickup_by", "cutoff", "deadline"], default="the cut-off")), UNIT_TEXT,
                 "collection deadline", source="engine:/api/rescue"),
            Fact("channel_name", str(pick(winner, ["name", "channel_name"], default="Transfer to sister outlet")),
                 UNIT_TEXT, "channel the optimiser ranked first", source="engine:/api/rescue"),
        ]
    )


# --- presentation ------------------------------------------------------------

_RULE = "─" * 78


def show(output: AgentOutput) -> None:
    status = "BLOCKED" if output.blocked else "PASSED"
    print(_RULE)
    print(f"  {output.agent.upper():<16} verifier: {status}   attempts: {output.attempts}   "
          f"model: {output.model}")
    print(_RULE)
    print()
    print(f"  what the model wrote (no numbers — check for yourself):")
    print(f"    {output.template or '(nothing)'}")
    print()
    print(f"  what the operator sees (numbers substituted by Python):")
    print(f"    {output.display_text}")
    print()
    if output.number_violations:
        print(f"  guard caught: {', '.join(output.number_violations[:6])}")
    if output.verification.findings:
        print("  " + output.verification.explain().replace("\n", "\n  "))
    print()


def _source(args: argparse.Namespace):
    if args.demo:
        return None
    if args.fixture:
        return FixtureClient(args.fixture)
    return FoodosApiClient(args.api)


def _facts_for(command: str, args: argparse.Namespace) -> FactSet:
    source = _source(args)
    if source is None:
        return {
            "diagnose": demo_facts.diagnostician_facts,
            "plan": demo_facts.planner_facts,
            "communicate": demo_facts.communicator_facts,
        }[command]()

    if command == "diagnose":
        return facts_from_why(source.why())
    if command == "plan":
        return facts_from_rescue_special(source.rescue(args.batch))
    return facts_from_transfer(source.rescue(args.batch))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="foodos.agents.runner", description="Run a FoodOS agent.")
    parser.add_argument("command", choices=["diagnose", "plan", "communicate", "all", "log"])
    parser.add_argument("--demo", action="store_true", help="use the planted pathology facts, no backend needed")
    parser.add_argument("--api", default=None, help="base URL of Person B's API")
    parser.add_argument("--fixture", default=None, help="directory of contract mock JSON")
    parser.add_argument("--batch", default=None, help="batch id for plan / communicate")
    parser.add_argument("--no-verify", action="store_true", help="skip the Verifier (never do this on stage)")
    args = parser.parse_args(argv)

    settings = get_settings()

    if args.command == "log":
        stats = audit.summary(settings.audit_log_path)
        print(f"audit log: {settings.audit_log_path}")
        for key, value in stats.items():
            print(f"  {key:20} {value}")
        return 0

    if not (args.demo or args.api or args.fixture):
        args.demo = True

    if settings.is_offline:
        reason = "FOODOS_LLM_OFFLINE is set" if settings.offline else "no ANTHROPIC_API_KEY"
        print(f"[llm] offline client ({reason}) — deterministic templates, no network\n")

    agents = {"diagnose": Diagnostician, "plan": Planner, "communicate": Communicator}
    commands = ["diagnose", "plan", "communicate"] if args.command == "all" else [args.command]

    blocked_any = False
    for command in commands:
        try:
            facts = _facts_for(command, args)
        except (ApiError, KeyError, ValueError) as exc:
            print(f"[{command}] could not build facts: {exc}\n", file=sys.stderr)
            blocked_any = True
            continue
        output = agents[command]().run(facts, verify=not args.no_verify)
        show(output)
        blocked_any = blocked_any or output.blocked

    return 1 if blocked_any else 0


if __name__ == "__main__":
    raise SystemExit(main())
