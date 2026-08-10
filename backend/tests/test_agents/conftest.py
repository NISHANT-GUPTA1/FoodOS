"""Shared fixtures for the agent tests.

Every test in this package runs offline and writes its audit log to a temp directory.
No test in here may touch the network, an API key, or backend/data/agent_audit.jsonl.

Owner: Person D.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# backend/tests/test_agents/conftest.py -> backend/
BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from foodos.agents.content import load_content  # noqa: E402
from foodos.agents.verifier import Verifier  # noqa: E402


@pytest.fixture(autouse=True)
def offline_and_isolated(monkeypatch, tmp_path):
    """Force the offline client and redirect the audit log. Autouse, no opting out."""
    monkeypatch.setenv("FOODOS_LLM_OFFLINE", "1")
    monkeypatch.setenv("FOODOS_VERIFIER_LLM", "0")
    monkeypatch.setenv("FOODOS_AGENT_LOG", str(tmp_path / "agent_audit.jsonl"))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


@pytest.fixture(scope="session")
def content():
    return load_content()


@pytest.fixture()
def verifier(content):
    return Verifier(content)


@pytest.fixture()
def audit_log(tmp_path):
    return tmp_path / "agent_audit.jsonl"
