# FoodOS — deck outline

**Owner: D.** Eleven slides. The deck is scaffolding for the demo, not a parallel
presentation — if a slide competes with the product for attention it comes out.

> The kitchen node's deck is kept at
> [`deck-outline-kitchen-node.md`](deck-outline-kitchen-node.md). Its design rules still
> apply here and are not restated: 16:9, dark, C's exact colour tokens so the deck and
> the app do not look like two products, no stock photography of vegetables in a wooden
> crate, no logo wall, no team photo.

Build rules:

- **One idea per slide.** If it needs a second sentence to be understood, it is two slides.
- **No slide is read aloud.** The script in `demo-script.md` is what is said; the slide is
  what is looked at while it is said.
- **Every number on a slide has its source on the same slide**, in small type. A judge who
  photographs a slide should be able to check it later.
- Slides 3 through 8 are **the live product**, not slides. The deck is a wrapper.

---

| # | When | Title | The one thing on it |
| --- | --- | --- | --- |
| 1 | 0:00 | **8.37%** | The NABCONS figure, huge. Source line underneath. |
| 2 | 0:20 | The gap | 31 hours of life. 36.5 hours of road. Two bars. |
| 3–8 | 0:35 | *(live product)* | Screens 2, 3, 4 |
| 9 | 3:50 | The agent that was blocked | A's Verifier screenshot |
| 10 | 4:10 | One engine, many nodes | Four node icons around one `V(a)` |
| 11 | 4:35 | FoodOS | Name, one line, contact |

Backup slides sit after 11 and are never shown unless asked for.

---

## Slide 1 — 8.37%

**Visual:** the number at 200pt. Below it, in 14pt: *NABCONS 2022 for MoFPI — tomato,
farm operations. Market stage is a further 3.25%. Separate stages, not additive.*

That last clause is on the slide deliberately. It pre-empts the sector-literate judge who
is about to point out that everyone inflates this figure by adding the stages together,
and it is worth more than the bigger number would be.

---

## Slide 2 — The gap

**Visual:** two horizontal bars.

```
remaining life   ███████████████████████████████            31 h
road to Delhi    ████████████████████████████████████████   36.5 h
```

No other content. Do not label it "the problem". The bars are the problem.

---

## Slides 3–8 — the product

Live. See `demo-script.md`. The deck holds a **static screenshot of each of the three
screens** in the same positions, so that if the app dies the deck advances through the
same beats and the story still lands. Those screenshots are captured at H33, after the
calibration is locked, and re-captured if any figure changes.

---

## Slide 9 — The agent that was blocked

**Visual:** A's screenshot of the Verifier refusing an agent output, with the offending
number circled and the blocked reason legible.

Caption, 14pt: *`tests/test_agents/test_no_number_contract.py` — the guarantee is a test,
not a policy.*

This is the credibility slide. It is the one thing in the deck that a technical judge
cannot get from any other team's presentation, and it takes twenty seconds.

---

## Slide 10 — One engine, many nodes

**Visual:** one box in the centre reading `V(a)` — the objective function, written out.
Four boxes around it: **Farm gate · Kitchen · Cold store · Retail back room**. Farm gate
and Kitchen are solid; the other two are outlined.

Solid means built and demonstrated. Outlined means the same shape of problem, not yet
built. **Do not fill in the outlines.** A judge who discovers that two of four claimed
nodes are aspirational has stopped listening to the two that are real.

Caption: *Different inputs. Different action space. One objective function.*

---

## Slide 11 — FoodOS

Name. One line: *The decision layer for perishable supply chains.* Contact.

Leave it up during questions.

---

## Backup slides — shown only if asked

| # | Trigger | Content |
| --- | --- | --- |
| B1 | "How does the model work?" | The Q10 equation, the three multipliers, one worked line for T1024 |
| B2 | "How accurate is it?" | A's MAE, interval coverage, and the naive-constant baseline beside it |
| B3 | "What data do you need?" | The four ingestion layers, and which are optional |
| B4 | "What about cold chain / IoT?" | The out-of-scope list and why each item is out |
| B5 | "Business model?" | Per-consignment fee to the FPO aggregator; open API for buyers |
| B6 | "Why only tomato?" | Adding a commodity is one YAML file plus a calibration pass — show `commodities.yaml` |
| B7 | "Who else is doing this?" | Cold-chain hardware and mandi price apps. Neither makes a decision. |

B6 is worth building well. "Show me the code that adds a second commodity" is the
question that separates a demo from a product, and the answer is a content file with a
citation beside every constant.

---

## What is deliberately not in this deck

- **A market-size slide.** A TAM number invented in an afternoon is the least defensible
  thing anyone puts on a screen, and it invites the one question with no good answer.
- **A team slide.** Nobody scores it and it costs fifteen seconds of a 4:40 budget.
- **An architecture diagram.** The product demonstrates the architecture. A boxes-and-
  arrows slide about a system that is running on the same screen is a step backwards.
- **The word "AI" on any slide.** Slide 9 says something specific about what the language
  models are forbidden from doing. That is worth more than the word.
