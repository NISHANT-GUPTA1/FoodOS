# The agents, and how the no-number rule is enforced

**Owner:** Person D. **Audience:** the team, and any judge who asks the follow-up question.

---

## The claim

> The LLM never computes a number.

This is not a prompt instruction we hope holds. It is a property of the pipeline. This
document explains the mechanism, then shows where each part of it lives in code and which
test would go red if someone broke it.

---

## The mechanism

A number reaches an operator through exactly one path:

```
engine computes a Fact ──► agent writes {{token}} ──► Python substitutes ──► Verifier checks
```

The model participates only in the second step, and at that point **no number exists in the
string it is writing**. It is shown fact *keys* and *labels* — `{{special_value_inr}}`,
"contribution recovered by running the special" — and never a value. It cannot copy a figure
it has not seen, and it cannot do arithmetic on one either.

Substitution happens in `templates.render()`, after the model has finished. The first moment
a digit exists in the output is a moment the model has no further influence over.

### The three legs

**Leg 1 — the model is never shown a value.**
`FactSet.catalogue()` renders keys, labels and units. It never renders `Fact.display` or
`Fact.value`.
→ `test_the_prompt_contains_no_fact_values`

**Leg 2 — a number the model wrote is rejected, not repaired.**
`guard.find_numbers()` scans raw output for digits (ASCII, Devanagari, Arabic-Indic),
superscripts, vulgar fractions, Roman numerals and spelled-out cardinals — after stripping
`{{tokens}}`, so the model's legitimate references are invisible to it. A violation earns one
retry with a correction; a second violation blocks the output entirely and the operator sees
a fallback.
→ `test_an_agent_that_writes_a_number_is_blocked`, `test_run_always_guards_before_it_renders`

**Leg 3 — every delivered number traces to a computed fact.**
`Verifier._c3_untraceable_number` extracts every numeric literal from the rendered text and
requires each to match a form of a computed fact. Rounded and re-scaled variants do not
match: 0.7 days does not make "1" traceable, and 4.4 kg does not make "4400 g" traceable.
→ `test_a_plausible_rounding_is_still_blocked`, `test_a_unit_conversion_the_agent_did_itself_is_blocked`

### What the guard deliberately does not block

`CO₂e` survives, because the subscript in a chemical formula is not a quantity. Ordinals
("first contributor", "second") survive, because they are ranking words. Words that merely
contain a number word — "none", "someone", "atonement" — survive, because `\b` boundaries are
used. Each of these has a test, because each was a bug waiting to be introduced by a
well-meaning tightening.

---

## The four agents

| Agent | Input | Output | Blocks on |
|---|---|---|---|
| **Diagnostician** | attribution shares | one sentence of root cause | any number of its own |
| **Planner** | at-risk batch + the dish the optimiser chose | 2–3 sentence special brief | naming a dish not in the facts |
| **Communicator** | winning transfer channel | 3–4 line WhatsApp message | banned framing, untraceable figures |
| **Verifier** | everything above, plus the facts | pass, or block and log | see below |

Every agent declares `required_facts`. If the engine does not supply them, the model is
**not called at all** — `MissingFactsError` is raised instead. An agent that improvises
because a field was missing is worse than an agent that fails loudly.

### The Verifier's six checks

| Code | Catches |
|---|---|
| `malformed_output` | a brace survived rendering |
| `unknown_fact` | a token for a fact the engine never computed |
| `untraceable_number` | **a number that matches no computed fact** |
| `hallucinated_entity` | a dish, ingredient or channel not in the facts |
| `direction_mismatch` | a fall described as a rise |
| `ungrounded_output` | prose citing no computed fact at all |

All six are deterministic and run with the network off. A seventh, optional check asks
`claude-sonnet-5` whether the sentence is a fair reading of the facts — it is **off by
default** (`FOODOS_VERIFIER_LLM=1` to enable) and can only ever add a block, never remove
one. The guarantee must not depend on a model being reachable.

Every run, passed or blocked, appends a line to `backend/data/agent_audit.jsonl` with the
template, the rendered text, the facts, and every finding. That log is the evidence behind
the claim, and the deck screenshot is a tail of it.

---

## Running it

```bash
# no backend, no API key, no network — the planted pathologies
python -m foodos.agents.runner all --demo

# against the contract fixtures Person C is building on
python -m foodos.agents.runner diagnose --fixture contracts/mock

# against Person B's live API
python -m foodos.agents.runner plan --api http://localhost:8000

# the Verifier blocking, formatted for a screenshot
python -m foodos.agents.demo

# audit summary
python -m foodos.agents.runner log
```

### Environment

| Variable | Default | What it does |
|---|---|---|
| `ANTHROPIC_API_KEY` | unset | absent means offline, automatically |
| `FOODOS_MODEL` | `claude-sonnet-5` | the only model this project uses |
| `FOODOS_LLM_OFFLINE` | `0` | force deterministic templates — **set this for the wifi-off rehearsal** |
| `FOODOS_VERIFIER_LLM` | `0` | enable the Verifier's semantic check |
| `FOODOS_AGENT_RETRIES` | `2` | corrections allowed before blocking |
| `FOODOS_API_URL` | `http://localhost:8000` | Person B's API |
| `FOODOS_AGENT_LOG` | `backend/data/agent_audit.jsonl` | audit trail |

### Offline mode is not a degraded mode

`OfflineClient` returns hand-written templates that go through the *same* guard, the *same*
renderer and the *same* Verifier, and produce the *same* numbers — because the numbers were
never the model's contribution in the first place. The sentences are less fluent. Nothing
else changes. This is why the wifi-off rehearsal at H33–36 is expected to pass rather than
hoped to.

---

## For Person B — what the agents need from the API

The agent layer calls your endpoints over HTTP and imports nothing from `engine/`, `api/`,
`schema/` or `models/`. `test_the_agent_layer_never_imports_the_engine` parses the AST and
fails if that ever stops being true.

The mapping from your payloads to facts lives in **one place**:
`backend/foodos/agents/runner.py`, functions `facts_from_why`, `facts_from_rescue_special`
and `facts_from_transfer`. They accept several candidate field names each, so a rename at
freeze time costs one line.

Fields the agents read:

| Endpoint | Fields needed |
|---|---|
| `/api/why` | `contributors[]` with `name` and `share`; optionally `value_at_risk`, `worst_dish` |
| `/api/rescue` | `batch{id, ingredient_name, zone_name, qty_kg, rsl_days}`, `special{dish_name, portions, value_inr, station}`, `channels[]` with `excluded`, `value_inr`, `pickup_by` |

If a field is missing, the runner raises with the list of keys your payload actually had.
That is intentional — it makes wiring at H16 a two-minute job instead of a hunt.

---

## What would falsify the claim

Honest list, so nobody has to find these in the Q&A:

1. **A fact whose value is wrong.** The pipeline guarantees the number came from the engine,
   not that the engine is right. The content tests defend the constants; Person A's backtest
   defends the forecast.
2. **A true number in a misleading sentence.** This is what the Verifier's `direction_mismatch`
   and the optional semantic check are for, and neither is airtight. A model can cite the
   right share and imply the wrong cause.
3. **A number the operator infers.** If a card shows 80 → 63, the reader computes 17. That is
   fine, and it is also not the model doing arithmetic.

The claim is precise, and it is worth stating precisely: *no number in a FoodOS output was
produced by a language model.* It is not a claim that the system cannot be wrong.
