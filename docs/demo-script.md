# FoodOS — demo script

**4:40. Owner: D. D presents.**

> **This replaces the kitchen demo as the pitch.** Ruling 2 of `FoodOS-Team-Split-v2.md`
> makes the farm-gate batch story the demo and the seven kitchen screens the platform
> proof, shown for about twenty seconds at 4:10. The kitchen script is kept intact at
> [`demo-script-kitchen-node.md`](demo-script-kitchen-node.md); its Verifier terminal
> walkthrough and its anticipated-questions list are still the best version of those
> beats and are drawn on below.
>
> Rehearsals, the contingency ladder and the freeze rules live in
> [`rehearsal-checklist.md`](rehearsal-checklist.md).

D presents because D did not write the engine. Somebody who built the optimiser explains
it in the vocabulary of the optimiser; somebody who did not has to explain it in the
judge's vocabulary, and that is the only vocabulary that scores.

**One batch, one story, no tour of the software.** Every beat below either sets up the
number or pays it off. Nothing on this page exists to show that a feature exists.

The beats follow §8 of the blueprint: register 10 t Kolar → Delhi → questionnaire →
photos → 8.4% / 31 h / high risk → agents propose → optimiser picks → simulator drops it
to 3.9% → close on the platform.

---

## The timing

| From | To | Len | Beat |
| --- | --- | --- | --- |
| 0:00 | 0:35 | 35 s | The problem, in one number |
| 0:35 | 1:05 | 30 s | Register the batch |
| 1:05 | 1:20 | 15 s | Three photos |
| 1:20 | 2:05 | 45 s | The assessment — 8.4%, 31 hours, high risk |
| 2:05 | 2:35 | 30 s | Every plan we considered, including the ones we ruled out |
| 2:35 | 3:05 | 30 s | The recommended plan |
| 3:05 | 3:50 | 45 s | **What if — hand this to a judge** |
| 3:50 | 4:10 | 20 s | The agent that was not allowed to speak |
| 4:10 | 4:40 | 30 s | One engine, many nodes |

Two spare beats, each ~10 s, are marked **[CUT FIRST]** and **[CUT SECOND]**. If you are
behind at 2:35, drop them without changing anything else.

---

## 0:00 — The problem, in one number · 35 s

**Screen:** slide 1. Nothing running.

> India loses more tomato between the field and the mandi than most countries grow.
> The NABCONS study for the Ministry of Food Processing puts it at eight point three
> seven percent at farm operations alone, before it ever reaches a market.
>
> Here is what that actually looks like. A farmer producer organisation in Kolar packs
> ten tonnes at eleven in the morning and puts it on an open truck to Delhi. Thirty-six
> hours on the road. Nobody in that chain knows, at the moment it matters, whether that
> fruit will survive the journey.
>
> They are not short of a sensor. They are short of a decision.

**[CUT FIRST]** — the sentence about the sensor.

**If the projector fails here:** keep talking. This beat has no screen dependency.

---

## 0:35 — Register the batch · 30 s

**Screen:** Screen 2, step 1. Start on a phone-width window if the projector allows it —
the user is standing next to a truck.

> This is what the FPO operator does. Tomato, ten thousand kilos, Kolar to Delhi APMC.

*Tap through steps 1 and 2. Do not narrate the form fields.*

> Then eight questions. Not a form — a form is what an app asks. These are the eight
> things that actually move the physics, and the tree adapts: I said the lot was picked
> at midday, so it now asks how long it sat in the sun. If I had said reefer, it would
> have stopped asking about covering the load.

*Answer: midday · half the afternoon · partly shaded · red but firm · bruising in most
crates · dry · an hour or two · open truck · ventilated crates · no cover · heaped.*

> Twenty-eight seconds. That is the entire data-entry burden.

**Watch for:** do not read the options aloud. Tap them. The speed is the point.

---

## 1:05 — Three photos · 15 s

**Screen:** Screen 2, step 4. Three pre-loaded photos of open crates.

> Three photos of the open crates. A vision model reads maturity, damage and uniformity
> out of these — as probabilities that go into the same feature vector, never as a
> verdict on screen. And they are optional. A batch with no photos still scores; the
> range just gets wider, and we say so.

**If the photo upload hangs:** tap Skip. It is a supported path and the demo continues
identically. Say "and I will skip them, because it works either way" — the recovery is
the feature.

---

## 1:20 — The assessment · 45 s

**Screen:** Screen 3, hero block.

> **Thirty-one hours of remaining life. The road to Delhi is thirty-six and a half.**
>
> That gap is the whole product. Not an expiry date printed at packing — a remaining
> life computed from the Arrhenius kinetics of this commodity, at the temperatures this
> load will actually meet, on this route, leaving at this hour.
>
> Predicted loss eight point four percent, and note that it is a **band** — six point
> seven to ten point nine. A single number would be a claim we cannot support.
>
> And here is why. These drivers come out of the model, not off a checklist. Picked in
> the afternoon and left in the sun. Fruit already red when packed. Crates heaped above
> the rim, so the stack is resting on the fruit instead of the crate.

*Point at the drivers bars. Do not read all of them — read the top two.*

> Every one of those is a sentence a farmer can act on tomorrow, at no cost.

**[CUT SECOND]** — the "expiry date printed at packing" sentence.

**Watch for:** the numbers on screen are model output. If any of them differs from 8.4 /
31 / HIGH, **read what is on screen** and carry on. Never say a number the screen does not
show.

---

## 2:05 — Every plan we considered · 30 s

**Screen:** Screen 3, plan matrix.

> Four specialist agents look at this batch — risk, logistics, market, rescue. They
> propose actions. **They do not rank them and they are not allowed to produce a
> number.** Every candidate goes through one objective function, and this is the result.
>
> Loss, logistics cost, revenue, net value, for every plan.
>
> And these greyed rows are the ones we ruled out, with the reason still visible. The
> reefer is excluded — not on cost, on availability. Fourteen hours' notice at a district
> hub, and this truck leaves in two.

*Point at one excluded row.*

> A system that shows you only its winning option is a system that is hiding its
> reasoning. Anyone who has run an operation knows the difference.

---

## 2:35 — The recommended plan · 30 s

**Screen:** Screen 3, recommended plan card.

> Split the load — six tonnes to Delhi, four to Jaipur — and leave six hours earlier.
>
> Jaipur is three and a half hours closer at a slightly lower price. That trade, a little
> less per kilogram against materially less decay, is worth more than the price gap. And
> leaving at two in the morning puts the hot part of the corridor in the dark.
>
> **Loss goes from eight point four percent to three point nine.**

*Pause. This is the number the room remembers.*

> Accept, and it goes on the batch. Override, and we record why — which is how the model
> finds out where it is wrong.

**Watch for:** if the engine's recommended plan is not the split, **present the plan the
engine picked** and say what it is. A plan the engine chose beats a plan the deck chose,
and the story survives either way — the claim is the delta, not the split.

---

## 3:05 — What if · 45 s · **the interaction moment**

**Screen:** Screen 4.

> But you should not have to trust my plan. Here — you drive.

*Hand the laptop or the trackpad to a judge. Actually hand it over. If nobody takes it,
drag the departure slider yourself and keep talking.*

> Drag departure. Change the vehicle. Move the split.

*Let them play for a beat before narrating.*

> Every one of those goes through the same scoring function the recommendation came out
> of. Not a lookup, not a second model for the sliders. If the simulator and the
> optimiser disagreed, one of them would be lying, and you would find it in about four
> seconds.
>
> The current plan stays on screen the whole time, so the comparison is never rhetorical.

**If the simulate endpoint is slow or fails:** the previous figure stays on screen by
design. Say "and it holds the last result rather than blanking — a blank number in an
operations tool is how people stop believing the tool." Then move on.

**Hard stop at 3:50** even if the judge is still dragging. "I want to show you one more
thing" is the exit line.

---

## 3:50 — The agent that was not allowed to speak · 20 s

**Screen:** the Verifier screenshot (slide). A's blocked agent output.

> One thing about how this is built, because it is the question I would ask.
>
> There are four language-model agents in here and **not one of them is permitted to
> produce a number.** They receive computed facts and they write sentences. Anything they
> emit that is not traceable to a model run is blocked before it reaches a screen.
>
> This is that happening. Not a policy on a slide — a test in the repository that fails
> the build.

---

## 4:10 — One engine, many nodes · 30 s

**Screen:** Screen 1 briefly, then the Kitchen node group, then the platform slide.

> Last thing. Everything you have seen runs on one objective function.
>
> *(open the Kitchen node group — about eight seconds, do not tour it)*
>
> That is the same engine running a restaurant kitchen. Different inputs, different
> action space, same scoring function, same agents, same guarantee. A cold store, a
> retail back room and a processing plant are the same shape of problem.
>
> Perishability is a decision problem, not a storage problem. We built the decision layer.
>
> Thank you.

**Do not** end on "any questions". End on the sentence. Let the silence sit.

---

## The four questions you will be asked, and the answers

**"Where does 8.37% come from?"**
> NABCONS 2022, commissioned by the Ministry of Food Processing Industries. It is in the
> repository with the citation next to the constant. Farm operations and market stages
> are separate numbers — 8.37 and 3.25 — and we deliberately do not add them, which is
> where the "thirty to forty percent" figure you have heard comes from.

**"Is the loss model better than a rule of thumb?"**
> We test it against a naive constant-rate baseline and report both. A model that cannot
> beat a constant should not be allowed to reroute a truck. *(Quote the actual MAE and
> coverage from A's H13 report. Do not improvise a figure.)*

**"What happens when the internet is down?"**
> This is running with the wifi off right now. Weather, route and price data are captured
> snapshots committed to the repository, and the screen tells you which. There is no live
> call anywhere in the demo path.

**"Do farmers actually have smartphones and will they fill this in?"**
> The operator at the collection hub does, and it is one form per consignment, not per
> farmer. Twenty-eight seconds against a ten-tonne decision. And the honest answer is
> that we do not know yet — that is what a pilot with one FPO in Kolar is for.

## The one question to refuse to bluff

**"What's your accuracy?"**
> Give the number A measured on the held-out slice, with the interval coverage, and say
> it is validated against synthetic physics rather than field-measured outcomes. Then say
> what would change that: a season of actual arrival weights against predictions. An
> invented accuracy figure is the only thing on this list that cannot be recovered from.
