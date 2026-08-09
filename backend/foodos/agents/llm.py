"""Model client.

Two implementations behind one interface:

* :class:`AnthropicClient` — the real thing, ``claude-sonnet-5`` via the Anthropic SDK.
* :class:`OfflineClient`  — deterministic, no network, returns hand-written templates.

The offline client is not a toy. H33-36 includes a full rehearsal with the wifi off, and
a demo that dies without internet is a demo that dies on stage. Because agent output is
templates rather than prose-with-numbers, an offline template is genuinely the same shape
of artifact as a model one: it goes through the same guard, the same renderer and the same
Verifier, and produces the same numbers, because the numbers were never the model's.

Owner: Person D.
"""

from __future__ import annotations

from typing import Protocol

from .settings import Settings, get_settings


class LLMError(Exception):
    """The model could not be reached or refused to answer."""


class LLMClient(Protocol):
    name: str

    def complete(self, *, system: str, user: str, agent: str) -> str: ...


class AnthropicClient:
    """claude-sonnet-5. The only model this project uses."""

    name = "anthropic"

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise LLMError(
                "the anthropic SDK is not installed; run `pip install anthropic` "
                "or set FOODOS_LLM_OFFLINE=1"
            ) from exc
        if not self.settings.api_key:
            raise LLMError("ANTHROPIC_API_KEY is not set")
        self._client = anthropic.Anthropic(
            api_key=self.settings.api_key, timeout=self.settings.request_timeout_s
        )

    def complete(self, *, system: str, user: str, agent: str) -> str:
        try:
            message = self._client.messages.create(
                model=self.settings.model,
                max_tokens=self.settings.max_tokens,
                temperature=self.settings.temperature,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
        except Exception as exc:  # pragma: no cover - network dependent
            raise LLMError(f"{agent}: model call failed: {exc}") from exc

        parts = [block.text for block in message.content if getattr(block, "type", "") == "text"]
        text = "".join(parts).strip()
        if not text:
            raise LLMError(f"{agent}: model returned an empty response")
        return text


class OfflineClient:
    """Deterministic stand-in. Same contract, no network, no API key."""

    name = "offline"

    #: One template per agent. Every token here must be in that agent's ``required_facts``,
    #: which ``tests/test_agents/test_offline_templates.py`` verifies, so the offline path
    #: can never render a token the engine did not compute.
    TEMPLATES: dict[str, str] = {
        "diagnostician": (
            "{{top_contributor_name}} is the largest single driver of today's risk, "
            "carrying {{top_contributor_share}} of the value at risk — demand softened "
            "but the production plan was not moved with it."
        ),
        "planner": (
            "Run {{special_dish_name}} as tonight's special. It uses the "
            "{{batch_ingredient_name}} sitting in {{batch_zone_name}} with "
            "{{batch_rsl_days}} of life left, and {{batch_qty_kg}} on hand covers "
            "{{special_portions}} at a recovered value of {{special_value_inr}}. "
            "The {{station_name}} station can prep it without pulling anyone off the main line."
        ),
        "communicator": (
            "Hi {{outlet_name}} team — we are holding {{batch_qty_kg}} of "
            "{{batch_ingredient_name}} with {{batch_rsl_days}} of shelf life left. "
            "Transferring it to you at our cost works out to {{transfer_value_inr}}. "
            "If you can collect by {{pickup_by}} it stays inside the cold chain the whole way. "
            "Say the word and we will pack it now."
        ),
        "verifier": "PASS",
    }

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def complete(self, *, system: str, user: str, agent: str) -> str:
        try:
            return self.TEMPLATES[agent]
        except KeyError:
            raise LLMError(
                f"offline client has no canned template for agent {agent!r}; "
                "add one to OfflineClient.TEMPLATES"
            ) from None


class ScriptedClient:
    """Returns whatever it is told to, in order. Test double for guard and retry paths."""

    name = "scripted"

    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, str]] = []

    def complete(self, *, system: str, user: str, agent: str) -> str:
        self.calls.append({"system": system, "user": user, "agent": agent})
        if not self._responses:
            raise LLMError("ScriptedClient ran out of responses")
        return self._responses.pop(0)


def get_client(settings: Settings | None = None) -> LLMClient:
    settings = settings or get_settings()
    if settings.is_offline:
        return OfflineClient(settings)
    return AnthropicClient(settings)
