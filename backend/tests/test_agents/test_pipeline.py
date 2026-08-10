"""The agent pipeline: retries, blocking, fallbacks, and the audit trail.

Owner: Person D.
"""

from __future__ import annotations

import json

import pytest

from foodos.agents import audit, demo_facts
from foodos.agents.base import MissingFactsError
from foodos.agents.communicator import BANNED_FRAMING, Communicator
from foodos.agents.diagnostician import Diagnostician
from foodos.agents.llm import LLMError, OfflineClient, ScriptedClient
from foodos.agents.planner import Planner
from foodos.agents.settings import get_settings


class ExplodingClient:
    name = "exploding"

    def complete(self, *, system, user, agent):
        raise LLMError("connection refused")


# --- offline behaviour -------------------------------------------------------

def test_offline_is_selected_when_there_is_no_api_key():
    assert get_settings().is_offline


@pytest.mark.parametrize(
    "agent_cls,facts_fn",
    [
        (Diagnostician, demo_facts.diagnostician_facts),
        (Planner, demo_facts.planner_facts),
        (Communicator, demo_facts.communicator_facts),
    ],
    ids=["diagnostician", "planner", "communicator"],
)
def test_every_agent_runs_end_to_end_with_the_network_off(agent_cls, facts_fn):
    """The H33-36 wifi-off rehearsal, as a test."""
    output = agent_cls().run(facts_fn())
    assert not output.blocked, output.verification.explain()
    assert output.text
    assert "{{" not in output.text


def test_offline_templates_only_reference_facts_the_agent_requires():
    """An offline template referencing a fact the engine will not supply would blow up on
    stage rather than in this file, which is the wrong order."""
    from foodos.agents.templates import tokens_in

    for agent_cls in (Diagnostician, Planner, Communicator):
        template = OfflineClient.TEMPLATES[agent_cls.name]
        for token in tokens_in(template):
            assert token in agent_cls.required_facts, (
                f"offline {agent_cls.name} template uses {{{{{token}}}}}, which is not in "
                f"{agent_cls.__name__}.required_facts"
            )


# --- guarding and retries ----------------------------------------------------

def test_a_clean_first_answer_is_not_retried():
    client = ScriptedClient(["{{top_contributor_name}} carries {{top_contributor_share}}."])
    output = Diagnostician(client=client).run(demo_facts.diagnostician_facts())
    assert output.attempts == 1
    assert len(client.calls) == 1


def test_retries_stop_at_the_configured_limit(monkeypatch):
    monkeypatch.setenv("FOODOS_AGENT_RETRIES", "1")
    client = ScriptedClient(["63 portions."] * 5)
    output = Diagnostician(client=client).run(demo_facts.diagnostician_facts())
    assert output.attempts == 2  # first try plus one retry
    assert output.blocked


# --- failure modes -----------------------------------------------------------

def test_a_model_outage_blocks_rather_than_invents():
    output = Planner(client=ExplodingClient()).run(demo_facts.planner_facts())
    assert output.blocked
    assert "model_unavailable" in output.verification.blocking_codes
    assert output.display_text == Planner.fallback_text


def test_a_token_for_a_fact_that_does_not_exist_blocks():
    client = ScriptedClient(["Recover {{profit_next_quarter}} on {{special_dish_name}}."])
    output = Planner(client=client).run(demo_facts.planner_facts())
    assert output.blocked
    assert "unknown_fact" in output.verification.blocking_codes


def test_missing_required_facts_refuses_to_call_the_model():
    client = ScriptedClient(["should never be reached"])
    facts = demo_facts.planner_facts()
    trimmed = type(facts)([f for f in facts if f.key != "special_dish_name"])

    with pytest.raises(MissingFactsError):
        Planner(client=client).run(trimmed)
    assert client.calls == []


def test_fallback_text_is_shown_and_contains_no_numbers():
    from foodos.agents.guard import find_numbers

    for agent_cls in (Diagnostician, Planner, Communicator):
        assert find_numbers(agent_cls.fallback_text) == []


# --- the communicator's framing rule ----------------------------------------

def test_the_communicator_prompt_bans_the_dumping_vocabulary():
    facts = demo_facts.communicator_facts()
    message = Communicator().user_message(facts)
    for word in ("surplus", "leftover", "waste"):
        assert word in message, "the ban list must be stated in the prompt"


def test_framing_violations_are_detectable_without_a_model_call():
    agent = Communicator()
    assert agent.framing_violations("We have surplus paneer to get rid of") == [
        "surplus",
        "get rid of",
    ]
    assert agent.framing_violations("We have paneer in good condition") == []


def test_the_offline_transfer_message_uses_none_of_the_banned_words():
    output = Communicator().run(demo_facts.communicator_facts())
    assert Communicator().framing_violations(output.text) == []
    assert not output.blocked


# --- audit trail -------------------------------------------------------------

def test_every_run_is_logged(tmp_path, monkeypatch):
    log = tmp_path / "audit.jsonl"
    monkeypatch.setenv("FOODOS_AGENT_LOG", str(log))

    Diagnostician().run(demo_facts.diagnostician_facts())
    Planner(client=ScriptedClient(["63 portions"] * 5)).run(demo_facts.planner_facts())

    records = audit.read_all(log)
    assert len(records) == 2
    assert {r["agent"] for r in records} == {"diagnostician", "planner"}


def test_a_block_is_logged_with_its_reason(tmp_path, monkeypatch):
    log = tmp_path / "audit.jsonl"
    monkeypatch.setenv("FOODOS_AGENT_LOG", str(log))

    Planner(client=ScriptedClient(["63 portions"] * 5)).run(demo_facts.planner_facts())

    blocked = audit.blocked_only(log)
    assert len(blocked) == 1
    assert blocked[0]["verification"]["findings"][0]["code"] == "number_emitted"
    assert "63" in blocked[0]["number_violations"]


def test_the_log_records_the_facts_the_output_was_built_from(tmp_path, monkeypatch):
    """Reproducibility: a logged line has everything needed to re-derive the output."""
    log = tmp_path / "audit.jsonl"
    monkeypatch.setenv("FOODOS_AGENT_LOG", str(log))

    Diagnostician().run(demo_facts.diagnostician_facts())

    record = audit.read_all(log)[0]
    assert record["facts"]["top_contributor_share"]["display"] == "38%"
    assert record["facts"]["top_contributor_share"]["source"] == "engine:/api/why"
    assert record["template"]
    assert record["text"]


def test_the_log_is_valid_jsonl(tmp_path, monkeypatch):
    log = tmp_path / "audit.jsonl"
    monkeypatch.setenv("FOODOS_AGENT_LOG", str(log))
    Diagnostician().run(demo_facts.diagnostician_facts())

    for line in log.read_text(encoding="utf-8").splitlines():
        json.loads(line)


def test_summary_counts_passes_and_blocks(tmp_path, monkeypatch):
    log = tmp_path / "audit.jsonl"
    monkeypatch.setenv("FOODOS_AGENT_LOG", str(log))

    Diagnostician().run(demo_facts.diagnostician_facts())
    Planner(client=ScriptedClient(["63"] * 5)).run(demo_facts.planner_facts())

    stats = audit.summary(log)
    assert stats == {"total": 2, "passed": 1, "blocked": 1, "number_violations": 1}


def test_a_broken_log_path_does_not_kill_the_run(monkeypatch, tmp_path):
    """A demo must not die because a log file could not be written."""
    blocker = tmp_path / "not_a_dir"
    blocker.write_text("i am a file", encoding="utf-8")
    monkeypatch.setenv("FOODOS_AGENT_LOG", str(blocker / "audit.jsonl"))

    output = Diagnostician().run(demo_facts.diagnostician_facts())
    assert not output.blocked
