"""Agent-layer configuration.

Deliberately separate from ``foodos/config.py``, which is Person B's file. Person D does
not edit Person B's files, so the agent layer reads its own environment and nothing else.

Owner: Person D.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

try:  # python-dotenv is on the approved stack; absence must not break a demo run
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - optional at runtime
    pass

#: backend/foodos/agents/settings.py -> backend/
BACKEND_ROOT = Path(__file__).resolve().parents[2]
CONTENT_DIR = BACKEND_ROOT / "foodos" / "content"
REPO_ROOT = BACKEND_ROOT.parent
MOCK_DIR = REPO_ROOT / "contracts" / "mock"


def _flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    """Every field is a ``default_factory``, deliberately.

    A plain default would be evaluated once when this module is imported, which means
    flipping FOODOS_LLM_OFFLINE mid-session would silently do nothing — exactly the kind
    of failure that only shows up during the wifi-off rehearsal.
    """

    model: str = field(default_factory=lambda: os.getenv("FOODOS_MODEL", "claude-sonnet-5"))
    api_key: str | None = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY"))
    api_base_url: str = field(
        default_factory=lambda: os.getenv("FOODOS_API_URL", "http://localhost:8000")
    )
    max_tokens: int = field(default_factory=lambda: int(os.getenv("FOODOS_MAX_TOKENS", "700")))
    temperature: float = field(
        default_factory=lambda: float(os.getenv("FOODOS_TEMPERATURE", "0.2"))
    )
    request_timeout_s: float = field(default_factory=lambda: float(os.getenv("FOODOS_TIMEOUT", "30")))
    max_retries: int = field(default_factory=lambda: int(os.getenv("FOODOS_AGENT_RETRIES", "2")))

    #: Force the deterministic offline client. Set for tests, for the wifi-off rehearsal,
    #: and automatically whenever there is no API key.
    offline: bool = field(default_factory=lambda: _flag("FOODOS_LLM_OFFLINE"))

    #: Optional second opinion from the model inside the Verifier. OFF by default: the
    #: deterministic checks are what block, and they must work with the wifi off.
    verifier_llm: bool = field(default_factory=lambda: _flag("FOODOS_VERIFIER_LLM"))

    #: Block spelled-out cardinals as well as digits.
    block_number_words: bool = field(
        default_factory=lambda: _flag("FOODOS_BLOCK_NUMBER_WORDS", True)
    )

    audit_log_path: Path = field(
        default_factory=lambda: Path(
            os.getenv("FOODOS_AGENT_LOG", str(BACKEND_ROOT / "data" / "agent_audit.jsonl"))
        )
    )
    content_dir: Path = field(default_factory=lambda: CONTENT_DIR)

    @property
    def is_offline(self) -> bool:
        return self.offline or not self.api_key


def get_settings() -> Settings:
    """Read settings fresh. Cheap, and lets a test flip an env var between cases."""
    return Settings()
