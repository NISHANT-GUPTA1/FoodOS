"""THE HARD RULE.

    "the LLM never computes a number" must be true in the code, not just on a slide.

This file is that sentence, written as executable assertions. If anything here goes red,
the claim comes off the deck until it is green again.

The guarantee has three legs, and each is tested separately below:

    1. The model is never shown a value it could copy or do arithmetic on.
    2. Raw model output containing a number of its own is rejected, not repaired.
    3. Every number in a delivered output traces back to a fact the engine computed.

Owner: Person D.
"""

from __future__ import annotations

import inspect as py_inspect

import pytest

from foodos.agents import demo_facts
from foodos.agents.base import Agent
from foodos.agents.communicator import Communicator
from foodos.agents.diagnostician import Diagnostician
from foodos.agents.facts import FactSet
from foodos.agents.guard import find_numbers
from foodos.agents.llm import OfflineClient, ScriptedClient
from foodos.agents.planner import Planner
from foodos.agents.prompts import HOUSE_RULES, load_prompt
from foodos.agents.templates import tokens_in

AGENTS = [
    (Diagnostician, demo_facts.diagnostician_facts),
    (Planner, demo_facts.planner_facts),
    (Communicator, demo_facts.communicator_facts),
]
AGENT_IDS = ["diagnostician", "planner", "communicator"]


# --- leg 1: the model is never shown a number --------------------------------

@pytest.mark.parametrize("agent_cls,facts_fn", AGENTS, ids=AGENT_IDS)
def test_the_prompt_contains_no_fact_values(agent_cls, facts_fn):
    """Whatever we send the model, none of the computed values are in it."""
    facts = facts_fn()
    agent = agent_cls()
    message = agent.user_message(facts)

    for fact in facts:
        if not fact.is_numeric:
            continue
        for form in fact.numeric_forms():
            assert form not in message, (
                f"{agent_cls.__name__} leaked the value of {fact.key} ({form!r}) into the prompt"
            )


@pytest.mark.parametrize("agent_cls,facts_fn", AGENTS, ids=AGENT_IDS)
def test_the_prompt_does_contain_every_fact_key(agent_cls, facts_fn):
    """It has to know what it may cite, or it will invent something instead."""
    facts = facts_fn()
    message = agent_cls().user_message(facts)
    for fact in facts:
        assert f"{{{{{fact.key}}}}}" in message, f"{fact.key} was not offered to {agent_cls.__name__}"


@pytest.mark.parametrize("name", ["diagnostician", "planner", "communicator", "verifier"])
def test_every_system_prompt_carries_the_house_rule(name):
    prompt = load_prompt(name)
    assert HOUSE_RULES.strip()[:60] in prompt
    assert "You may not write a number" in prompt


# --- leg 2: a number the model wrote is rejected ------------------------------

@pytest.mark.parametrize("agent_cls,facts_fn", AGENTS, ids=AGENT_IDS)
def test_an_agent_that_writes_a_number_is_blocked(agent_cls, facts_fn):
    """Not corrected, not stripped, not rounded — blocked, with a fallback in its place."""
    numeric = "The batch is 4.4 kg and covers 36 portions, worth about 6,700 rupees."
    agent = agent_cls(client=ScriptedClient([numeric] * 5))

    output = agent.run(facts_fn())

    assert output.blocked
    assert output.verification.blocking_codes == ["number_emitted"]
    assert output.text == ""
    assert output.display_text == agent.fallback_text
    assert find_numbers(output.display_text) == []


@pytest.mark.parametrize("agent_cls,facts_fn", AGENTS, ids=AGENT_IDS)
def test_a_number_earns_a_correction_before_a_block(agent_cls, facts_fn):
    """One slip is retried with feedback. Persistence is what gets blocked."""
    good = "{{" + facts_fn().keys()[0] + "}} is the only thing this says."
    client = ScriptedClient(["The answer is 63 portions.", good])
    agent = agent_cls(client=client)

    output = agent.run(facts_fn(), verify=False)

    assert output.attempts == 2
    assert not output.blocked
    assert "63" in output.number_violations
    assert "You are not permitted to state" in client.calls[1]["user"]


@pytest.mark.parametrize("agent_cls,facts_fn", AGENTS, ids=AGENT_IDS)
def test_the_offline_template_itself_contains_no_number(agent_cls, facts_fn):
    """The fallback path is held to the same rule as the model."""
    template = OfflineClient.TEMPLATES[agent_cls.name]
    assert find_numbers(template) == []


# --- leg 3: delivered numbers trace to computed facts -------------------------

@pytest.mark.parametrize("agent_cls,facts_fn", AGENTS, ids=AGENT_IDS)
def test_every_number_delivered_traces_to_a_computed_fact(agent_cls, facts_fn):
    facts = facts_fn()
    output = agent_cls().run(facts)

    assert not output.blocked, output.verification.explain()

    allowed: set[str] = set()
    for fact in facts:
        allowed |= fact.numeric_forms()
        if not fact.is_numeric:
            allowed.add(str(fact.value))

    import re

    for literal in re.findall(r"₹?\d[\d,]*(?:\.\d+)?%?", output.text):
        assert any(literal in form or literal.strip("₹%") in form for form in allowed), (
            f"{literal!r} was delivered by {agent_cls.__name__} but is not a computed fact"
        )


@pytest.mark.parametrize("agent_cls,facts_fn", AGENTS, ids=AGENT_IDS)
def test_the_delivered_text_is_the_template_with_facts_substituted(agent_cls, facts_fn):
    """There is no third source of text. What ships is the model's words plus our numbers."""
    from foodos.agents.templates import render

    facts = facts_fn()
    output = agent_cls().run(facts)
    assert output.text == render(output.template, facts)


@pytest.mark.parametrize("agent_cls,facts_fn", AGENTS, ids=AGENT_IDS)
def test_every_token_used_was_a_fact_the_engine_supplied(agent_cls, facts_fn):
    facts = facts_fn()
    output = agent_cls().run(facts)
    for token in tokens_in(output.template):
        assert token in facts


# --- structural: there is no way around the pipeline --------------------------

def test_the_agent_layer_never_imports_the_engine():
    """Person D calls Person B's API over HTTP and does not reach into their modules.

    Parsed properly rather than grepped, so prose about the seam does not fail the test
    and ``import foodos.engine as _`` does not sneak past it.
    """
    import ast
    import pathlib

    forbidden = ("foodos.engine", "foodos.api", "foodos.models", "foodos.schema")
    agents_dir = pathlib.Path(py_inspect.getfile(Agent)).parent

    for path in agents_dir.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            for name in names:
                assert not any(
                    name == bad or name.startswith(bad + ".") for bad in forbidden
                ), f"{path.name} imports {name}"


def test_run_always_guards_before_it_renders():
    """A structural check: the guard call precedes the render call in Agent.run."""
    source = py_inspect.getsource(Agent.run)
    guard_at = source.index("guard.inspect")
    render_at = source.index("render(template, facts)")
    assert guard_at < render_at, "Agent.run renders before it guards — the rule is broken"


def test_blocked_output_never_exposes_the_model_text():
    facts = demo_facts.planner_facts()
    agent = Planner(client=ScriptedClient(["It is 63 portions."] * 5))
    output = agent.run(facts)

    assert output.blocked
    assert "63" not in output.display_text
    assert output.template not in output.display_text


def test_no_agent_can_run_without_the_facts_it_needs():
    from foodos.agents.base import MissingFactsError

    with pytest.raises(MissingFactsError) as excinfo:
        Planner().run(FactSet([]))
    assert "special_dish_name" in str(excinfo.value)
