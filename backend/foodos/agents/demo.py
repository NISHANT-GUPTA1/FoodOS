"""The Verifier, blocking. Run this, screenshot it, put it in the deck.

    python -m foodos.agents.demo

Four scenarios against the same computed facts:

    1. A well-behaved agent            -> passes, numbers substituted by Python
    2. An agent that writes a number   -> the guard catches it before rendering
    3. Output with a tampered figure   -> C3 untraceable_number blocks it
    4. Output naming a dish nobody has -> C4 hallucinated_entity blocks it

Scenarios 3 and 4 simulate the failure we cannot otherwise stage on demand: a model that
gets past the guard and still says something false. The point of the screenshot is that
the system refuses it rather than printing it in a nice card.

Owner: Person D.
"""

from __future__ import annotations

from .content import load_content
from .demo_facts import planner_facts
from .llm import ScriptedClient
from .planner import Planner
from .settings import get_settings
from .templates import render
from .verifier import Verifier

WIDTH = 78
RULE = "═" * WIDTH


def _box(title: str) -> None:
    print()
    print(RULE)
    print(f"  {title}")
    print(RULE)


def _verdict(passed: bool) -> str:
    return "PASS  — shown to the operator" if passed else "BLOCK — withheld from the operator"


GOOD = (
    "Run {{special_dish_name}} as tonight's special — it clears the "
    "{{batch_ingredient_name}} in {{batch_zone_name}} with {{batch_rsl_days}} of life left. "
    "{{batch_qty_kg}} on hand covers {{special_portions}} and brings back "
    "{{special_value_inr}}. {{station_name}} can prep it before service."
)

WITH_A_NUMBER = (
    "Run {{special_dish_name}} tonight — about 4.4 kg of paneer left, roughly 36 portions, "
    "worth around 6,700 rupees."
)

TAMPERED = (
    "Run Paneer Butter Masala as tonight's special — 4.4 kg on hand covers 36 portions "
    "and brings back ₹31,900."
)

HALLUCINATED = (
    "Run Mutton Rogan Josh as tonight's special — {{batch_qty_kg}} on hand covers "
    "{{special_portions}} and brings back {{special_value_inr}}."
)


def main() -> int:
    settings = get_settings()
    content = load_content()
    facts = planner_facts()
    verifier = Verifier(content)

    print()
    print("FoodOS — the LLM never computes a number")
    print(f"audit log: {settings.audit_log_path}")
    print()
    print("Computed facts available to the agent (it sees these KEYS, never these VALUES):")
    for fact in facts:
        print(f"    {fact.key:24} = {fact.display}")

    # --- 1 ------------------------------------------------------------------
    _box("1. A well-behaved agent")
    agent = Planner(client=ScriptedClient([GOOD]), content=content, verifier=verifier)
    out = agent.run(facts)
    print("\n  model wrote:")
    print(f"    {out.template}")
    print("\n  Python rendered:")
    print(f"    {out.text}")
    print(f"\n  verifier: {_verdict(not out.blocked)}")

    # --- 2 ------------------------------------------------------------------
    _box("2. The agent writes its own numbers")
    agent = Planner(
        client=ScriptedClient([WITH_A_NUMBER, WITH_A_NUMBER, WITH_A_NUMBER]),
        content=content,
        verifier=verifier,
    )
    out = agent.run(facts)
    print("\n  model wrote:")
    print(f"    {out.template}")
    unique = list(dict.fromkeys(out.number_violations))
    print(f"\n  guard caught, on every attempt: {', '.join(unique)}")
    print(f"  attempts before giving up: {out.attempts}")
    print(f"\n  verifier: {_verdict(not out.blocked)}")
    print(f"  operator sees instead: {out.display_text}")

    # --- 3 ------------------------------------------------------------------
    _box("3. A figure is tampered with after rendering")
    print("\n  text under review:")
    print(f"    {TAMPERED}")
    result = verifier.check(agent="planner", template=GOOD, rendered=TAMPERED, facts=facts)
    print(f"\n  verifier: {_verdict(result.passed)}")
    print("  " + result.explain().replace("\n", "\n  "))

    # --- 4 ------------------------------------------------------------------
    _box("4. The output names a dish that is not in the facts")
    rendered = render(HALLUCINATED, facts)
    print("\n  text under review:")
    print(f"    {rendered}")
    result = verifier.check(agent="planner", template=HALLUCINATED, rendered=rendered, facts=facts)
    print(f"\n  verifier: {_verdict(result.passed)}")
    print("  " + result.explain().replace("\n", "\n  "))

    print()
    print(RULE)
    print("  Every number above was placed by Python from a computed fact.")
    print("  The model's job ended at the token.")
    print(RULE)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
