"""The Verifier.

Fourth agent, and the only one with authority. It reads every other agent's output next to
the facts the engine computed and decides whether an operator is allowed to see it. On a
mismatch it blocks and logs. It does not repair, soften, or annotate — a corrected number
still means the pipeline produced a wrong one, and we want that in the log.

Six deterministic checks, all of which run with the network off:

    C1 malformed_output      a brace survived rendering
    C2 unknown_fact          the model referenced a fact the engine never computed
    C3 untraceable_number    a number in the output does not trace to a computed fact
    C4 hallucinated_entity   the output names a dish, ingredient or channel not in the facts
    C5 direction_mismatch    the output describes a fall as a rise, or the reverse
    C6 ungrounded_output     the output cites no computed fact at all

C3 is the one that matters. Everything else is hygiene; C3 is the check that makes
"the LLM never computes a number" verifiable rather than aspirational.

An optional seventh check asks claude-sonnet-5 whether the sentence is a fair reading of
the facts. It is OFF by default and can only ever add a block, never remove one.

Owner: Person D.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .facts import DIRECTION_WORDS, FactSet
from .templates import tokens_in

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .content import ContentPack
    from .llm import LLMClient

#: Any number as it could appear on screen: 63, 1,84,000, 12.4, 38%, all optionally
#: prefixed with a rupee sign.
_NUMBER_IN_TEXT = re.compile(r"₹?\s?\d[\d,]*(?:\.\d+)?\s?%?")

_LEADING_BRACE = re.compile(r"\{\{|\}\}")


def _normalise_number(text: str) -> str:
    """'₹1,84,000' -> '184000';  '12.40 kg' -> '12.4';  '38 %' -> '38'."""
    cleaned = text.replace("₹", "").replace(",", "").replace("%", "").strip()
    try:
        value = float(cleaned)
    except ValueError:
        return cleaned
    if value == int(value):
        return str(int(value))
    return f"{value:g}"


@dataclass(frozen=True)
class Finding:
    code: str
    detail: str
    severity: str = "block"  # "block" | "warn"

    @property
    def blocking(self) -> bool:
        return self.severity == "block"


@dataclass
class VerificationResult:
    agent: str
    findings: list[Finding] = field(default_factory=list)
    checks_run: list[str] = field(default_factory=list)

    @property
    def blocked(self) -> bool:
        return any(f.blocking for f in self.findings)

    @property
    def passed(self) -> bool:
        return not self.blocked

    @property
    def blocking_codes(self) -> list[str]:
        return [f.code for f in self.findings if f.blocking]

    def explain(self) -> str:
        if not self.findings:
            return f"{self.agent}: PASS — every number traced to a computed fact."
        lines = [f"{self.agent}: {'BLOCKED' if self.blocked else 'PASS with warnings'}"]
        for f in self.findings:
            marker = "BLOCK" if f.blocking else " warn"
            lines.append(f"  [{marker}] {f.code}: {f.detail}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "agent": self.agent,
            "blocked": self.blocked,
            "checks_run": self.checks_run,
            "findings": [{"code": f.code, "detail": f.detail, "severity": f.severity} for f in self.findings],
        }


class Verifier:
    """Checks an agent's output against the computed facts. Blocks on mismatch."""

    name = "verifier"

    def __init__(
        self,
        content: "ContentPack | None" = None,
        *,
        llm: "LLMClient | None" = None,
        use_llm: bool = False,
    ) -> None:
        self.content = content
        self.llm = llm
        self.use_llm = use_llm and llm is not None

    # -- individual checks --------------------------------------------------

    def _c1_malformed(self, rendered: str) -> list[Finding]:
        match = _LEADING_BRACE.search(rendered)
        if match:
            return [Finding("malformed_output", f"unresolved brace near {rendered[max(0, match.start()-20):match.start()+20]!r}")]
        return []

    def _c2_unknown_fact(self, template: str, facts: FactSet) -> list[Finding]:
        unknown = [t for t in tokens_in(template) if t not in facts]
        if unknown:
            return [
                Finding(
                    "unknown_fact",
                    f"referenced fact(s) the engine never computed: {', '.join(unknown)}",
                )
            ]
        return []

    def _c3_untraceable_number(self, rendered: str, facts: FactSet) -> list[Finding]:
        allowed = {_normalise_number(f) for f in facts.numeric_forms()}
        # Text facts legitimately carry digits — batch ids, pickup times, dates. They came
        # from the engine too, so numbers inside them are traceable by definition.
        for value in facts.text_values():
            for match in _NUMBER_IN_TEXT.finditer(value):
                allowed.add(_normalise_number(match.group(0).strip()))
        computed = ", ".join(
            f"{f.key}={f.display}" for f in facts if f.is_numeric
        ) or "(no numeric facts)"

        findings = []
        seen: set[str] = set()
        for match in _NUMBER_IN_TEXT.finditer(rendered):
            literal = match.group(0).strip()
            key = _normalise_number(literal)
            if key in allowed or key in seen:
                continue
            seen.add(key)
            findings.append(
                Finding(
                    "untraceable_number",
                    f"{literal!r} appears in the output but matches no computed fact. "
                    f"Computed: {computed}",
                )
            )
        return findings

    def _c4_hallucinated_entity(self, rendered: str, facts: FactSet) -> list[Finding]:
        if self.content is None:
            return []
        haystack = rendered.lower()
        grounded = " | ".join(facts.text_values()).lower()

        hits = [
            name
            for name in self.content.known_names()
            if name.lower() in haystack and name.lower() not in grounded
        ]
        # "Mutton Rogan Josh" already implies "Mutton". Report the longest match only,
        # so one hallucinated dish produces one finding rather than a pile of fragments.
        longest = [
            name
            for name in hits
            if not any(other != name and name.lower() in other.lower() for other in hits)
        ]
        return [
            Finding(
                "hallucinated_entity",
                f"output names {name!r}, which is not in any computed fact",
            )
            for name in sorted(longest)
        ]

    def _c5_direction_mismatch(self, rendered: str, facts: FactSet) -> list[Finding]:
        haystack = rendered.lower()
        findings = []
        for fact in facts:
            if not fact.direction:
                continue
            opposite = "up" if fact.direction == "down" else "down"
            for word in DIRECTION_WORDS[opposite]:
                if re.search(rf"\b{re.escape(word)}\b", haystack):
                    findings.append(
                        Finding(
                            "direction_mismatch",
                            f"{fact.key!r} moved {fact.direction}, but the output says {word!r}",
                        )
                    )
                    break
        return findings

    def _c6_ungrounded(self, template: str) -> list[Finding]:
        if not tokens_in(template):
            return [
                Finding(
                    "ungrounded_output",
                    "output cites no computed fact at all — it is prose with nothing behind it",
                )
            ]
        return []

    def _c7_llm_reading(self, rendered: str, facts: FactSet) -> list[Finding]:
        if not self.use_llm or self.llm is None:
            return []
        from .prompts import load_prompt

        listing = "\n".join(f"  {f.key} = {f.display}  ({f.label or f.key})" for f in facts)
        user = (
            f"COMPUTED FACTS\n{listing}\n\n"
            f"OUTPUT UNDER REVIEW\n{rendered}\n\n"
            "Reply with exactly PASS, or BLOCK followed by a colon and a short reason."
        )
        try:
            verdict = self.llm.complete(
                system=load_prompt("verifier"), user=user, agent="verifier"
            ).strip()
        except Exception as exc:  # a verifier that crashes must not silently approve
            return [Finding("verifier_unavailable", f"semantic check could not run: {exc}", "warn")]

        if verdict.upper().startswith("BLOCK"):
            _, _, reason = verdict.partition(":")
            return [Finding("semantic_mismatch", reason.strip() or "model judged the reading unfair")]
        return []

    # -- entry point --------------------------------------------------------

    def check(
        self,
        *,
        agent: str,
        template: str,
        rendered: str,
        facts: FactSet,
    ) -> VerificationResult:
        result = VerificationResult(agent=agent)
        result.checks_run = [
            "malformed_output",
            "unknown_fact",
            "untraceable_number",
            "hallucinated_entity",
            "direction_mismatch",
            "ungrounded_output",
        ]
        result.findings += self._c1_malformed(rendered)
        result.findings += self._c2_unknown_fact(template, facts)
        result.findings += self._c3_untraceable_number(rendered, facts)
        result.findings += self._c4_hallucinated_entity(rendered, facts)
        result.findings += self._c5_direction_mismatch(rendered, facts)
        result.findings += self._c6_ungrounded(template)

        if self.use_llm:
            result.checks_run.append("semantic_mismatch")
            result.findings += self._c7_llm_reading(rendered, facts)

        return result
