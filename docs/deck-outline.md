# Deck outline

**Owner:** Person D. **Tool:** Google Slides. **Slides:** 9, plus 4 in the appendix.
**Rule:** the deck runs behind a live demo, not instead of it. Slides 1 and 8 are the only
ones on screen for more than five seconds.

---

## Design

- 16:9. Dark background, one accent colour per horizon, matching Person C's tokens exactly —
  the deck and the app must not look like two products.
  - PREVENT `#3B82F6` · PRESERVE `#F59E0B` · RECOVER `#10B981`
- One idea per slide. If a slide needs a second sentence to be understood, it is two slides.
- No stock photography of vegetables in a wooden crate.
- No logo wall, no team photo, no "our journey" slide.
- Every number on a slide is traceable to `backend/foodos/content/` or to a cited source, and
  the citation is on the slide, small, not in a footnote nobody reads.

---

## Slide 1 — The problem
**On screen for 35 seconds. The only slide that gets to be slow.**

> A kitchen throws away 8–15% of what it buys.
> Every tool reports it afterwards.

Sub-line: *The decision that caused it was made three days earlier.*

Source line: FAO food wastage footprint; industry benchmarks for Indian foodservice.

---

## Slide 2 — Three losses, three interventions
**5 seconds. A table, no animation.**

| Loss | Cause | FoodOS |
|---|---|---|
| Over-production | Forecast error, no cost asymmetry | **PREVENT** |
| Spoilage in storage | Shelf life ignored until zero | **PRESERVE** |
| Unsold saleable stock | No route in time | **RECOVER** |

*This is the slide that earns the word "platform" later. Do not skip it.*

---

## Slide 3 — One objective function
**8 seconds. Then go to the app and do not come back to the deck until slide 8.**

```
V(a) = margin(a) − holding(a) − disposal(a) − λ · sustainability(a)

q* = Cu / (Cu + Co + λ · sustainability_per_unit)
```

Sub-line: *One function. Three action spaces. λ is the slider you are about to see.*

---

## Slides 4–7 — Live demo placeholders

Black slides with a single word, so a wrong click never shows the audience the next screen:
`TODAY` · `WHY` · `PLAN` · `RESCUE`

*They exist only so the deck is the same length as the demo and the clicker stays in sync.*

---

## Slide 8 — The LLM never computes a number
**The most important slide in the deck. 25 seconds.**

Left half — **what the model returns**, monospace, verbatim:

```
Run {{special_dish_name}} tonight — {{batch_qty_kg}} on hand
covers {{special_portions}} and brings back {{special_value_inr}}.
```

Right half — **the Verifier blocking**. The screenshot from
`python -m foodos.agents.demo`, scenario 3, cropped to the block:

```
[BLOCK] untraceable_number: '₹31,900' appears in the output
but matches no computed fact.
Computed: special_value_inr=₹6,680 …
```

Bottom line, small: *157 tests. One of them is this sentence.*

> **Screenshot instructions (H16–22):** run `python -m foodos.agents.demo` in a terminal at
> 16pt on a dark theme, capture scenarios 1 and 3, crop tight, no window chrome, no
> timestamp, no username in the prompt.

---

## Slide 9 — Three tracks, one optimiser
**15 seconds.**

Three columns, one per track, same card silhouette:

| Kitchen | Retail | Production |
|---|---|---|
| How much to cook | When to mark down | How big a batch |
| Which special to run | Which store to transfer to | What sequence to run |
| Where surplus goes | Where surplus goes | Where surplus goes |

Bottom line: *Same `V(a)`. Different action set. ~80 lines each.*

---

## Appendix — only if asked

**A1 · The RSL model.** The Q10 equation, the paneer worked example from
`docs/pathologies.md`, and the punchline: *moving a tray between fridges buys a day and costs
nothing.*

**A2 · The feasibility gate.** The three excluded channels for B-1057 and their reasons.
*Excluded options are shown, never hidden.*

**A3 · Where the numbers come from.** Cauliflower 0.58 yield, dairy Q10 3.0, aggregator
commission 22%, carbon at the low end of the CCTS range, wastage externality at a quarter of
the FAO full-cost figure. *We argued from the conservative number.*

**A4 · Backtest.** Held-out days, mean absolute error, comparison to the naive
same-day-last-week baseline, acceptance rate.

---

## Build checklist

- [ ] H0–3 · Skeleton, slides 1–3 and 9 blocked out with placeholder numbers
- [ ] H10 · Real numbers from `content/`, every source line filled in
- [ ] H16–22 · Verifier screenshot captured and placed on slide 8
- [ ] H22–28 · Full pass with the demo, timings marked against `demo-script.md`
- [ ] H28 · Exported to PDF, PDF copied to the presenting laptop, opened once to confirm
- [ ] H33 · Backup video embedded on a hidden slide 10, in case the app will not start
