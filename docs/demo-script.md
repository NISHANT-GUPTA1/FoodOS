# Demo script — 4:40

**Owner:** Person D. **Presenter:** Person D.
**Target:** 4 minutes 40 seconds, leaving 20 seconds of slack in a 5-minute slot.

Read this as beats, not as a monologue. The words are a floor, not a ceiling — but the
**timings and the transitions are fixed**, because those are what fall apart under pressure.

Person C drives the laptop. Person D talks. Person B sits with a terminal open and does not
touch anything unless something is on fire.

---

## Setup, before the slot

- [ ] `python -m foodos.ingest.seed` run and finished, database fresh
- [ ] Backend up on `:8000`, frontend on `:5173`
- [ ] Browser on the Today screen, zoomed to 125%, one tab, no bookmarks bar
- [ ] λ slider at 0.5
- [ ] `python -m foodos.agents.demo` output already open in a second terminal, scrolled to
      the block
- [ ] Backup video queued at 0:00 in a third window
- [ ] Phone on silent, in a bag, not in a pocket

---

## 0:00 — 0:35 · The problem, in one number

**Slide 1.**

> A restaurant kitchen throws away between eight and fifteen per cent of everything it buys.
> Every tool in this space tells them that number *after* the week is over. It reports the
> weight of what went into the bin.
>
> Nobody throws away food on purpose. They throw it away because of a decision made three
> days earlier — how much to buy, how much to prep, what to cook this morning. By the time
> waste appears in a report, every decision that caused it is already gone.
>
> FoodOS acts on the decision instead.

**Do not** say "we built a dashboard". Say it acts.

---

## 0:35 — 1:05 · Today

**Switch to the app. Today screen.**

> This is a kitchen manager's morning. Three numbers: kilograms at risk today, what that is
> worth, and — the one that matters — how much of it was preventable.
>
> Not "you wasted this". *This is what is about to happen, and this much of it is still in
> your hands.*

Point at the ranked list.

> Underneath, the actions, ranked by what each one is worth. Every card is the same shape,
> whether it is telling you to cook less, move a tray between fridges, or send stock to
> another outlet.

**Transition:** click the top card's **Why**.

---

## 1:05 — 1:45 · Why

**Why screen.**

> Every recommendation in FoodOS can be opened up. This is the attribution.
>
> Plan drift is carrying the largest share. Not spoilage, not a bad forecast — the forecast
> was right. Weekday demand for this dish fell three weeks ago, and the forecast followed
> it. The prep sheet did not. It is a laminated card on a wall, and nothing in that kitchen's
> day forces anyone to reprint it.

Point at the root-cause sentence.

> That sentence is written by a language model. Every number in it was computed before the
> model was called, and the model is structurally incapable of writing a number — I will
> show you exactly how in a moment.

**Transition:** click through to Plan.

---

## 1:45 — 2:35 · Plan and the λ slider ← **the interaction moment**

**Plan screen.**

> Here is tomorrow's production. Eighty portions planned, sixty-three recommended.
>
> That is a newsvendor calculation: the cost of running out, against the cost of making too
> much. Standard operations research, on the kitchen's real costs and a quantile forecast.

**Now take hold of the slider.** Say this while dragging, slowly, left to right:

> And this is the part I would like you to watch. This slider is the weight on
> sustainability. At the far left, the plan is pure profit — carbon costs nothing, waste
> costs only what it costs to bin it.

Drag to 1.0. Let the table and the totals redraw. **Pause for a full second.**

> At the far right, the full cost of wasted food is priced in — carbon, land, water,
> disposal. The plan changes. Every quantity, every total.
>
> This is one objective function with one parameter, not two products with a toggle. And I
> will be straight with you about the size of it: at any defensible carbon price, carbon
> alone would move a single dish by about one portion. It is the full wastage cost that
> moves the plan, and we priced that at a quarter of the FAO's figure, not at the flattering
> end.

> **If asked "why does the whole plan move?"** — because it is the same calculation on all
> fourteen dishes at once, and the totals are where it shows.

**Transition:** click through to Rescue.

---

## 2:35 — 3:15 · Rescue and the feasibility gate

**Rescue screen, batch B-1057.**

> Prevention failed here — this was ordered on Sunday for a match that moved. Nine point six
> kilograms of chicken, a day and a half of life, and it is Tuesday.
>
> Ranked channels, by what actually comes back after commission and transport. Transfer to
> our other outlet wins, at two thousand four hundred rupees.

**Point at the greyed-out rows. Slow down here.**

> And these are the ones it *cannot* use. The delivery app, because this stock is raw and
> that channel takes cooked. The food bank, because their collection runs Monday, Wednesday
> and Friday, and today is Tuesday. Animal feed, because poultry cannot enter a
> no-meat-contact stream.
>
> They are greyed out, not hidden. If a system makes an option vanish without telling you
> why, you stop trusting it within a week. That is a product decision, and it is the one I
> would defend hardest.

---

## 3:15 — 4:00 · The agents, and the Verifier blocking

**Second terminal. `python -m foodos.agents.demo` output.**

> Four language-model agents run in this system. One diagnoses, one drafts the special, one
> writes the transfer message, and one checks the other three.
>
> The rule we set ourselves is that the model never computes a number. Not "we told it not
> to" — it cannot.

Point at the model output, still full of `{{tokens}}`.

> This is what the model actually returns. Tokens, no digits. It is never shown a value; it
> is shown the *names* of the facts. Python substitutes the numbers afterwards, from what the
> engine computed. If the model writes so much as a digit, the guard rejects the whole
> response.

Scroll to the block.

> And here is the Verifier doing its job. We tampered with one figure after rendering —
> changed six thousand six hundred and eighty to thirty-one thousand nine hundred. Every
> number in an output has to trace back to a computed fact. This one does not, so it is
> blocked, logged, and the operator sees a fallback instead of a confident lie.
>
> A hundred and fifty-seven tests. One of them is that sentence, written as an assertion.

---

## 4:00 — 4:25 · The platform claim

**Slide: three tracks.**

> Last thing. Everything you have seen runs on one objective function.
>
> A retail shelf and a production line have the same problem — a perishable asset, a
> decision window, a cost of being wrong in either direction. Same optimiser, different
> action set. Markdown timing instead of batch size. About eighty lines each, not three
> products.

Click to the Retail stub, then the Production stub. Two seconds each. Do not linger.

---

## 4:25 — 4:40 · Close

> Kitchens do not need to be told what they wasted. They need to be told what to do this
> morning, what it is worth, and why — in language they will act on, with numbers a machine
> can prove.
>
> That is FoodOS. Thank you.

**Stop talking. Do not add a summary. Do not offer more slides.**

---

## Timing checkpoints

Miss one of these by more than ten seconds and cut, do not speed up.

| Time | You should be |
|---|---|
| 0:35 | Leaving slide 1 |
| 1:05 | On the Why screen |
| 1:45 | Hand on the λ slider |
| 2:35 | Leaving Plan |
| 3:15 | In the terminal |
| 4:00 | On the tracks slide |

## What to cut if you are behind

1. The second track stub click (saves 5s)
2. The FAO honesty aside on the Plan screen (saves 12s)
3. The trim-loss callout on Why, if you added it (saves 10s)

**Never cut:** the λ drag, or the Verifier block. Those two are the demo.

---

## Anticipated questions

**"Is the data real?"**
> Synthetic, generated against real culinary yields, real Indian wholesale prices, and
> published carbon factors. The three failure modes in it are planted deliberately, and they
> are documented — we can show you the file. What is real is every constant: the 0.58 yield
> on cauliflower, the Q10 of 3.0 on fresh dairy, the aggregator commission.

**"What stops the model hallucinating a number?"**
> It never has one to hallucinate with. Show the terminal again.

**"How is this different from an inventory system?"**
> An inventory system tells you what you have. This tells you what to do with it, prices the
> alternatives against each other, and shows its working.

**"Would a kitchen actually use this?"**
> The highest-value recommendation in the whole demo is "move that tray to the other
> fridge". It costs nothing and buys a day. That is the kind of thing that gets a system
> kept.

**"What is the accuracy?"**
> On the Impact screen — measured on held-out days only, against a naive same-day-last-week
> baseline. We will show you the days the model never saw.

**"Why not just use a bigger model / an agent that does the maths?"**
> Because a kitchen manager cannot audit a number a model produced, and neither can you. The
> arithmetic is in code that has tests. The model does the part that is genuinely hard for
> code: saying it in a sentence someone will act on.
