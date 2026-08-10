"""The agent pipeline.

Every agent in FoodOS runs the same five steps, in the same order, with no way around them:

    1. REQUIRE   the facts the agent declares are present, or refuse to call the model
    2. ASK       the model, showing it fact KEYS and never fact VALUES
    3. GUARD     reject raw output containing any number the model wrote itself
    4. RENDER    substitute computed values into the model's tokens, in Python
    5. VERIFY    check the rendered text against the facts; block on mismatch
    6. AUDIT     append the whole exchange to the log, passed or blocked

Steps 3 and 4 are why the no-number claim holds. The model finishes writing before any
number exists in the string. There is no branch that skips the guard, and a blocked output
returns a fallback rather than the model's text.

Owner: Person D.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from . import audit, guard
from .content import ContentPack, load_content
from .facts import FactSet
from .llm import LLMClient, LLMError, get_client
from .prompts import load_prompt
from .settings import Settings, get_settings
from .templates import MalformedTemplateError, UnknownTokenError, render, tokens_in
from .verifier import Finding, VerificationResult, Verifier


class MissingFactsError(Exception):
    """The engine did not supply everything this agent needs. Never call the model blind."""


@dataclass
class AgentOutput:
    """What an agent returns. ``text`` is safe to show only when ``blocked`` is False."""

    agent: str
    text: str
    template: str
    blocked: bool
    verification: VerificationResult
    facts_used: list[str] = field(default_factory=list)
    attempts: int = 1
    number_violations: list[str] = field(default_factory=list)
    model: str = ""
    fallback: str | None = None

    @property
    def display_text(self) -> str:
        """Always safe to render in a UI. Falls back when the output was blocked."""
        if self.blocked:
            return self.fallback or "This explanation could not be verified and was withheld."
        return self.text

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent": self.agent,
            "text": self.text,
            "template": self.template,
            "blocked": self.blocked,
            "attempts": self.attempts,
            "facts_used": self.facts_used,
            "number_violations": self.number_violations,
            "model": self.model,
            "verification": self.verification.to_dict(),
        }


class Agent(ABC):
    """Base class. Subclasses supply a name, the facts they need, and a user message."""

    #: Matches the prompt filename in ``prompts/``.
    name: str = "agent"

    #: Facts this agent cannot work without. Absence is a bug in the caller, not a
    #: reason to let the model improvise.
    required_facts: tuple[str, ...] = ()

    #: Shown to the operator when the Verifier blocks. Must contain no numbers itself.
    fallback_text: str = "This explanation could not be verified and was withheld."

    def __init__(
        self,
        *,
        client: LLMClient | None = None,
        content: ContentPack | None = None,
        verifier: Verifier | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.client = client or get_client(self.settings)
        self.content = content if content is not None else load_content()
        self.verifier = verifier or Verifier(
            self.content,
            llm=self.client,
            use_llm=self.settings.verifier_llm,
        )

    # -- subclass hooks -----------------------------------------------------

    @abstractmethod
    def user_message(self, facts: FactSet) -> str:
        """The task half of the prompt. The fact CATALOGUE, never the fact values."""

    def system_prompt(self) -> str:
        return load_prompt(self.name)

    # -- the pipeline -------------------------------------------------------

    def run(self, facts: FactSet, *, verify: bool = True) -> AgentOutput:
        missing = facts.missing(self.required_facts)
        if missing:
            raise MissingFactsError(
                f"{self.name}: engine did not supply required fact(s): {', '.join(missing)}"
            )

        system = self.system_prompt()
        user = self.user_message(facts)
        violations: list[str] = []
        template = ""
        attempts = 0

        # 2 + 3: ask, then guard. A number in the raw reply earns one correction.
        for attempt in range(1, self.settings.max_retries + 2):
            attempts = attempt
            try:
                template = self.client.complete(system=system, user=user, agent=self.name).strip()
            except LLMError as exc:
                return self._blocked(
                    facts, template="", rendered="", attempts=attempt,
                    findings=[Finding("model_unavailable", str(exc))], violations=violations,
                )

            report = guard.inspect(template, block_number_words=self.settings.block_number_words)
            if report.clean:
                break

            violations.extend(report.offenders)
            user = f"{self.user_message(facts)}\n\n{guard.correction_for(list(report.offenders))}"
        else:
            # Exhausted retries and the model kept writing numbers. Nothing gets through.
            return self._blocked(
                facts, template=template, rendered="", attempts=attempts,
                findings=[
                    Finding(
                        "number_emitted",
                        f"model wrote its own number(s) on every attempt: {', '.join(violations[:6])}",
                    )
                ],
                violations=violations,
            )

        # 4: render — the first moment a number exists in this string.
        try:
            rendered = render(template, facts)
        except UnknownTokenError as exc:
            return self._blocked(
                facts, template=template, rendered="", attempts=attempts,
                findings=[Finding("unknown_fact", str(exc))], violations=violations,
            )
        except MalformedTemplateError as exc:
            return self._blocked(
                facts, template=template, rendered="", attempts=attempts,
                findings=[Finding("malformed_output", str(exc))], violations=violations,
            )

        # 5: verify.
        if verify:
            result = self.verifier.check(
                agent=self.name, template=template, rendered=rendered, facts=facts
            )
        else:
            result = VerificationResult(agent=self.name, checks_run=["(skipped)"])

        output = AgentOutput(
            agent=self.name,
            text=rendered,
            template=template,
            blocked=result.blocked,
            verification=result,
            facts_used=tokens_in(template),
            attempts=attempts,
            number_violations=violations,
            model=self.settings.model if self.client.name == "anthropic" else self.client.name,
            fallback=self.fallback_text,
        )
        self._audit(output, facts)
        return output

    # -- helpers ------------------------------------------------------------

    def _blocked(
        self,
        facts: FactSet,
        *,
        template: str,
        rendered: str,
        attempts: int,
        findings: list[Finding],
        violations: list[str],
    ) -> AgentOutput:
        result = VerificationResult(agent=self.name, findings=findings, checks_run=["pre-render"])
        output = AgentOutput(
            agent=self.name,
            text=rendered,
            template=template,
            blocked=True,
            verification=result,
            facts_used=tokens_in(template),
            attempts=attempts,
            number_violations=violations,
            model=self.settings.model if self.client.name == "anthropic" else self.client.name,
            fallback=self.fallback_text,
        )
        self._audit(output, facts)
        return output

    def _audit(self, output: AgentOutput, facts: FactSet) -> None:
        audit.append(
            self.settings.audit_log_path,
            {
                **output.to_dict(),
                "facts": facts.snapshot(),
                "offline": self.settings.is_offline,
            },
        )
