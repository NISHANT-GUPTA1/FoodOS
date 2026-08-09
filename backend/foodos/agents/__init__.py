"""FoodOS agents.

Four agents, one rule: the LLM never computes a number.

    Diagnostician   attribution facts        -> one sentence of root cause
    Planner         low-shelf-life stock     -> a menu special the kitchen can run
    Communicator    a transfer decision      -> the WhatsApp message that gets a yes
    Verifier        everything above         -> pass, or block and log

Numbers reach an operator through exactly one path: the engine computes a
:class:`~foodos.agents.facts.Fact`, an agent writes a ``{{token}}``, and Python substitutes
the value after the model has finished writing. :mod:`foodos.agents.guard` rejects any raw
model output containing a numeral, and :mod:`foodos.agents.verifier` blocks any rendered
output whose numbers do not trace back to a computed fact.

Owner: Person D. Never imports from foodos.engine, foodos.api or foodos.models.
"""

from .base import Agent, AgentOutput, MissingFactsError
from .communicator import Communicator
from .content import ContentPack, load_content
from .diagnostician import Diagnostician
from .facts import Fact, FactSet
from .guard import NumberEmittedError, assert_number_free, find_numbers
from .planner import Planner
from .templates import UnknownTokenError, render
from .verifier import Finding, VerificationResult, Verifier

__all__ = [
    "Agent",
    "AgentOutput",
    "Communicator",
    "ContentPack",
    "Diagnostician",
    "Fact",
    "FactSet",
    "Finding",
    "MissingFactsError",
    "NumberEmittedError",
    "Planner",
    "UnknownTokenError",
    "VerificationResult",
    "Verifier",
    "assert_number_free",
    "find_numbers",
    "load_content",
    "render",
]
