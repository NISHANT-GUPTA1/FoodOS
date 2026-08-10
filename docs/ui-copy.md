# FoodOS — UI copy for the four batch screens

**Owner: D. Consumer: C.** One file, so there is one place a string lives and one person
who changed it. C should be able to paste from here without inventing a sentence.

> This file covers the **four batch screens** of the farm-gate product. The seven kitchen
> screens keep their own strings in
> [`ui-copy-kitchen-node.md`](ui-copy-kitchen-node.md) — Ruling 2 keeps them as the
> platform proof, so C still renders them and still needs that copy. The voice rules
> there apply here too and are not repeated: say what to do rather than what happened,
> never moralise, never apologise for the software, never say "AI".

Placeholders in `{{braces}}` are filled by the frontend from the API response — the same
convention as the kitchen copy and as the agents, for the same reason: **the words are
authored, the numbers are computed.**

Three more rules this copy follows, and why they are not style preferences:

1. **Never state a number in prose that the API also renders.** Write "loss is
   {{loss_pct}}" and not "loss is around 8%". Hardcoded prose numbers survive a model
   change and become the lie on stage.
2. **A degraded state gets a sentence, never a blank.** A blank screen mid-demo reads as
   a crash; a sentence reads as a system that knows what it does not know.
3. **Say what to do, not what happened.** "Move departure to 02:00" beats "high thermal
   exposure detected". The user is holding a phone next to a truck.

Indian digit grouping everywhere: **₹1,22,260**, never ₹122,260. C's formatter must match
`backend/foodos/agents/facts.py::format_indian`, which is asserted in
`tests/test_external/test_content_pack.py`.

---

## 0. The shared vocabulary

Use exactly these words. Three synonyms for the same thing across four screens is how a
judge concludes there are three systems.

| Concept | Word we use | Words we never use |
| --- | --- | --- |
| A consignment | **batch** | lot, load, shipment, consignment |
| Hours of usable life left | **remaining life** | RUL, RSL, freshness |
| Predicted loss | **predicted loss** | wastage, shrinkage, spoilage % |
| A candidate action | **plan** | option, scenario, recommendation |
| The plan we rank first | **recommended plan** | best plan, optimal plan |
| Doing nothing different | **current plan** | baseline, do-nothing, status quo |
| Origin market | **Kolar** | source, farm gate |
| A destination | **the mandi's display name** | market, APMC (alone) |

"Remaining life" appears in the UI. "RUL" appears in the API and in this repo. That is
deliberate: the field name is for engineers, the label is for the person deciding.

### Risk bands

One definition, used on every screen. C's colour tokens key off these three words only.

| Band | Colour | Label | When |
| --- | --- | --- | --- |
| HIGH | red | **High risk** | the API says HIGH |
| MEDIUM | amber | **Needs attention** | the API says MEDIUM |
| LOW | green | **Stable** | the API says LOW |

Never render the raw enum. Never invent a fourth band.

### Confidence

| Value | Label | Tooltip |
| --- | --- | --- |
| HIGH | Confident | Based on a full questionnaire, photos and captured route weather. |
| MEDIUM | Fairly confident | Some inputs are missing or estimated. The range is wider than usual. |
| LOW | Low confidence | Most inputs are estimated. Treat this as a direction, not a figure. |

Confidence is never hidden and never rounded away. A LOW-confidence batch showing a
tight band is the single most damaging thing this UI could do.

### The staleness note

Every panel fed by `external/` renders `source`. Quiet, grey, one line under the panel —
**a note, never a warning**. It is a disclosure we are comfortable with, not an error.

| `source` | Note |
| --- | --- |
| `snapshot` | Captured {{captured_at}}. Working offline. |
| `live` | Live, fetched just now. |
| `model` | Modelled from seasonal normals — no captured data for this route. |

If `days_stale` is present and greater than 1: `Prices from {{arrival_date}}, {{days_stale}} days ago.`

---

## 1. Screen 1 — Command Center

**Purpose:** what needs a decision in the next few hours. Not a dashboard.

| Element | Copy |
| --- | --- |
| Page title | Command Center |
| Subtitle | Batches in transit and awaiting dispatch |
| Group headers | {{n}} high risk · {{n}} need attention · {{n}} stable |
| Primary CTA | Register a batch |
| Row: route | Kolar → {{destination}} |
| Row: quantity | {{qty_kg}} kg {{commodity}} |
| Row: remaining life | {{rul_hours}} h left |
| Row: remaining life, under 12 h | **{{rul_hours}} h left** — in red, regardless of band |
| Row: loss | {{loss_pct}} predicted loss · {{loss_kg}} kg |
| Row: action line | {{best_plan.label}} |
| Row: no action needed | On plan. Nothing to change. |
| Sort note | Sorted by remaining life, shortest first |

**Empty state.** No batches at all:

> **Nothing in transit.**
> Register a batch and FoodOS will start tracking its remaining life from the moment it
> is packed.
> [ Register a batch ]

**Empty state.** Filtered to nothing:

> No batches match this filter. [ Clear filters ]

**Empty state.** Everything is fine — the one nobody writes and everybody needs:

> **All {{n}} batches are on plan.**
> Nothing needs a decision right now. The next batch reaches its dispatch window at
> {{time}}.

**Error state.** The list endpoint failed:

> **Can't reach the batch list.**
> The engine may still be starting up. [ Try again ]

---

## 2. Screen 2 — Create Batch

**Purpose:** get a real consignment into the system in under thirty seconds, standing at a
collection hub. Every extra sentence here costs a real second.

The wizard is five steps. **Step titles come from `GET /api/questionnaire` — the copy
below is what that endpoint returns, not what C should hardcode.** It is repeated here so
D and C can review the wording in one place.

| Step | Title | Sub |
| --- | --- | --- |
| 1 | What are you shipping? | |
| 2 | How much, and where to? | |
| 3 | Condition of the lot | Answer what you know. You can skip any of these. |
| 4 | Add photos | 3 to 5 photos of the open crates. Optional. |
| 5 | Vehicle and packing | |

| Element | Copy |
| --- | --- |
| Progress | Step {{n}} of 5 |
| Skip link | Skip |
| Back | Back |
| Next | Next |
| Final CTA | Assess this batch |
| Quantity field | Quantity (kg) |
| Origin field | Picked up from |
| Destination field | Going to |
| Harvest field | Picked at |
| Photo drop zone | Tap to add photos of the open crates |
| Photo help | Natural light, whole crate in frame. Three is plenty. |
| Photo skip | Skip photos — the assessment still works, with a wider range. |
| Photo uploading | Reading photo {{n}} of {{total}}… |
| Photo failed | Couldn't read that photo. It won't be used. [ Try another ] |
| Submitting | Assessing this batch… |

**The submit wait.** Rotate these while the model runs. Never show a bare spinner for
more than two seconds — the judge's attention is on the screen and silence reads as a hang.

> Reading the questionnaire…
> Checking the route weather for {{destination}}…
> Working out how much life is left…
> Comparing what you could do about it…

**Validation.** One sentence, under the field, never a modal.

| Case | Copy |
| --- | --- |
| No quantity | How many kilograms? |
| Quantity absurd | That's more than a truck holds. Split it into separate batches. |
| No destination | Where is it going? |
| Harvest time in the future | That's in the future. When was it actually picked? |

**Error state.** The submit failed:

> **The assessment didn't come back.**
> Your answers are saved. [ Try again ]

Nothing the user typed is ever lost to an error. C should keep the wizard state.

---

## 3. Screen 3 — Batch Intelligence

**Purpose:** the hero. One screen that explains a number well enough to act on it.

### Hero block

| Element | Copy |
| --- | --- |
| Title | Batch {{id}} · {{qty_kg}} kg {{commodity}} |
| Route | Kolar → {{destination}} · departs {{depart_time}} |
| Remaining life | **{{rul_hours}} h** remaining life |
| Remaining life sub | Transit to {{destination}} takes {{transit_hours}} h |
| Remaining life, when transit exceeds it | **Arrives {{n}} h past its remaining life** |
| Predicted loss | **{{loss_pct}}** predicted loss · {{loss_kg}} kg |
| Loss band | Range {{low}} to {{high}} |
| Quality | Quality {{quality_score}}/100 · grade {{grade}} |
| Maturity | {{maturity}} |
| Field heat | {{field_heat_hours}} h above 30 °C before loading |

The loss figure renders as a **band, not a point.** A single number implies a precision
the model does not have, and the band is what makes the confidence label honest.

### Drivers block

| Element | Copy |
| --- | --- |
| Header | What's driving the loss |
| Sub | Ranked by contribution. From the model, not a checklist. |
| Bar label | {{driver.text}} |
| Bar value | {{contribution}} |
| Empty | The model didn't find a dominant driver — the loss is spread across several small ones. |

Driver sentences are model output. Where A needs a human phrasing for a feature name,
use these:

| Feature | Sentence |
| --- | --- |
| `field_heat_hours_over_30c` | Picked in the afternoon and left in the sun |
| `maturity_stage` | Fruit was already red and firm when packed |
| `damage_level` | Bruising visible across most crates |
| `transport_mode` | Travelling uncovered on an open truck |
| `packaging_type` | Packed in sacks rather than ventilated crates |
| `crate_fill` | Crates heaped above the rim — the stack rests on the fruit |
| `transit_hours` | {{transit_hours}} h on the road to {{destination}} |
| `mean_temp_c` | Route runs at {{mean_temp_c}} °C on average |
| `surface_moisture` | Packed damp |
| `yard_hold_hours` | {{yard_hold_hours}} h between packing and departure |

### Recommended plan card

| Element | Copy |
| --- | --- |
| Header | Recommended plan |
| Label | {{plan.label}} |
| Gain | Saves {{delta_vs_baseline}} against the current plan |
| Loss | Loss drops from {{baseline.loss_pct}} to {{plan.loss_pct}} |
| Kg | {{kg_saved}} kg of fruit that arrives saleable |
| Accept | Accept this plan |
| Override | Do something else |
| Override prompt | What are you doing instead? |
| Override help | This is recorded against the batch. It's how the model learns where it's wrong. |
| Accepted | Accepted at {{time}} |
| Overridden | Overridden at {{time}} — {{reason}} |

### Plan matrix

| Element | Copy |
| --- | --- |
| Header | Every plan we considered |
| Sub | Including the ones we ruled out, and why. |
| Columns | Plan · Loss · Loss (kg) · Logistics cost · Revenue · Net value · vs current |
| Current plan row | Current plan — badged, never called "baseline" |
| Best row badge | Recommended |
| Excluded row | greyed, with `exclusion_reason` shown in full |

**Exclusion reasons.** These are the strings D owns; the engine emits the key.

| Key | Copy |
| --- | --- |
| `lead_time_exceeds_rul` | Arrives after this batch runs out of life |
| `vehicle_unavailable` | No {{transport}} available at Kolar within {{availability_hours}} h |
| `absorption_exceeded` | More than {{destination}} clears in a day |
| `below_min_qty` | Below this buyer's minimum quantity |
| `above_max_qty` | More than this buyer can take |
| `grade_not_accepted` | This buyer doesn't take grade {{grade}} |
| `past_cutoff` | Past today's cutoff for this route |
| `chilling_injury_risk` | Too cold for tomato — below {{chilling_injury_below_c}} °C causes chilling injury |
| `not_economic` | Costs more to run than it recovers |

**An excluded plan is never hidden.** An operator who watches an option vanish without
explanation stops trusting the system, and a judge who sees only the winning option
assumes we cherry-picked it.

**Empty / degraded states**

| Case | Copy |
| --- | --- |
| No photos supplied | No photos on this batch — the assessment uses the questionnaire only, so the range is wider. |
| Photo model unavailable | Photo analysis is unavailable. The questionnaire answers still score this batch. |
| Only one plan | The current plan is the only one available for this batch right now. |
| Plans still computing | Comparing plans… |
| Plans failed | **Couldn't compare plans.** The batch assessment above is still valid. [ Try again ] |

---

## 4. Screen 4 — What-If Simulator

**Purpose:** the judge touches something and a number moves. It must feel instant.

| Element | Copy |
| --- | --- |
| Page title | What if? |
| Sub | Change the plan and watch the loss move. Nothing is saved until you accept. |
| Departure slider | Departure |
| Departure value, earlier | {{n}} h earlier · leaves {{time}} |
| Departure value, later | {{n}} h later · leaves {{time}} |
| Departure value, zero | As planned · leaves {{time}} |
| Transport toggle | Vehicle |
| Transport options | Open truck · Tarpaulin · Reefer |
| Destination picker | Send it to |
| Split slider | Split the load |
| Split value | {{a}} kg to {{mandi_a}} · {{b}} kg to {{mandi_b}} |
| Reset | Back to the current plan |
| Save CTA | Accept this plan |

**The comparison line — always on screen, never replaced.**

> Current plan {{baseline.loss_pct}} · **{{sim.loss_pct}}** with these changes
> **{{delta}}** {better|worse}

Words, not just colour: `better` / `worse` in text. A colour-only delta is invisible to a
colour-blind judge and to a projector with the contrast turned down.

| Case | Copy |
| --- | --- |
| Simulating | (no text — keep the previous figure on screen and dim it) |
| Simulation failed | Couldn't run that combination. The last result is still shown. |
| Combination infeasible | **Not possible.** {{exclusion_reason}} |
| No change from baseline | No change — this is the current plan. |
| Reefer selected, unavailable | No reefer available at Kolar within {{availability_hours}} h. Shown for comparison only. |

**Never blank the number while recomputing.** Dim the old figure and animate to the new
one. A field that empties for 300 ms and refills reads as a bug to everyone watching.

---

## 5. Global

| Element | Copy |
| --- | --- |
| App name | FoodOS |
| Nav: batch screens | Command Center · Register batch · Batch intelligence · What if? |
| Nav group: kitchen | Kitchen node |
| Kitchen node tooltip | The same engine running a restaurant kitchen. Different inputs, one objective function. |
| Generic error | **Something went wrong.** [ Try again ] |
| Offline | Working offline. Route and price data are from the captured snapshot. |
| Loading, first paint | Loading… |
| 404 | That batch doesn't exist. [ Back to Command Center ] |

### Number formatting

| Kind | Format | Example |
| --- | --- | --- |
| Money | `₹` + Indian grouping, no decimals | ₹1,22,260 |
| Money, under ₹100 | one decimal | ₹19.5 |
| Mass | Indian grouping + ` kg` | 10,000 kg |
| Percent | one decimal + `%` | 8.4% |
| Hours | integer + ` h` | 31 h |
| Temperature | one decimal + ` °C` | 34.2 °C |
| Delta | signed | +₹7,700 / −2.1% |

Never abbreviate money to `1.2L` or `₹1.2 lakh` in a figure. Lakh notation is fine in
prose on the deck; in a table it invites a conversion error in the judge's head.

**Verified at the A/B/C/D merge.** C's `frontend/src/utils/format.ts` uses
`Intl.NumberFormat('en-IN')`; the backend uses `agents/facts.py::format_indian`. They
agree on every figure the demo shows:

| value | `en-IN` (C) | `format_indian` (backend) |
| --- | --- | --- |
| 122260 | `1,22,260` | `1,22,260` |
| 153760 | `1,53,760` | `1,53,760` |
| 10000 | `10,000` | `10,000` |
| 1234567 | `12,34,567` | `12,34,567` |

The backend side is pinned by `tests/test_external/test_content_pack.py`. The two
implementations are independent, so if either is swapped for a hand-rolled grouper this
table is the check to re-run.

---

## 6. What this copy deliberately does not say

- **"AI-powered"** anywhere. The screens show a physics model, a gradient-boosted
  predictor and four agents that are forbidden from producing a number. Calling that "AI"
  in the UI trades something specific for something generic.
- **"Optimal"**, ever. We rank candidates under a stated objective. "Recommended" is what
  we can defend.
- **"Guaranteed"**, "**will** save", or any figure without a band behind it.
- **"Detected"** for anything a human told us. The questionnaire answers are claims, not
  observations, and the photo features are probabilistic. "You told us" is the honest verb.
