# FoodOS — Production Execution Blueprint, reconciled

**What this is.** The *Production Execution Blueprint* proposes FoodOS as an open
infrastructure kernel for Indian post-harvest agriculture: four pipeline tracks (A–D),
Arrhenius decay over IoT telemetry, AgStack / AGMARKNET / Beckn / ONDC integration, and
a six-tier cascading diversion waterfall.

This document is the ruling on it. Each proposal is **adopted**, **deferred** with an
unlock condition, or **rejected** with the reason. Nothing is left as an open question,
because an open question in a spec becomes an argument at hour 30.

The short version: the blueprint is a good description of where the product goes, and a
poor description of what to build next. Most of its RECOVER machinery already exists in
[engine/rescue.py](../backend/foodos/engine/rescue.py) under different names; most of its
Track A and Track B machinery is on the existing kill list for reasons that have not
changed. Three things in it were genuinely additive and cheap, and those are built.

---

## 1. The word "track" now means three things. It means one.

| Usage | Where | Meaning |
| --- | --- | --- |
| Track 1 / 2 / 3 | [Product Design §2](FoodOS-Product-Design.md) | **customer segments** — kitchen, retail, production |
| PREVENT / PRESERVE / RECOVER | [War Plan §2](FoodOS-Hackathon-War-Plan.md) | **action spaces** — one objective function, three feasible sets |
| Track A / B / C / D | the blueprint | **pipeline stages** — harvest, storage, allocation, diversion |
| A / B / C / D | `git log` | **people** — the four owners |

Four meanings across two letters and three numbers. The ruling: **the blueprint's Track
A–D vocabulary is not adopted.** Two reasons.

The first is mechanical. Commits on this branch are literally `[A]` and `[B]`; a file
called `track_b.py` would be ambiguous between "person B's module" and "the storage
stage" on the day it matters most.

The second is architectural, and it is the same objection
[War Plan §1](FoodOS-Hackathon-War-Plan.md) already resolved once. The original tracks
were OPERATE / PRESERVE / FORECAST, and the problem was that OPERATE is a customer
segment wearing the costume of a capability. Redefining tracks by *when you intervene in
the life of the food* is what collapsed three products into one engine. The blueprint's
A–D reintroduces the same category error in a new coat: Track A is a **place** (the
farm), Track B is a **capability** (shelf life), Track C is a **market**, Track D is an
**action space**. Mixing those is what makes three tracks feel like three products.

So blueprint capabilities are filed against the coverage matrix that already exists —
node × horizon — rather than given a track letter of their own:

```
                | PREVENT              | PRESERVE             | RECOVER
----------------+----------------------+----------------------+----------------------
 FARM / FPO     | Track A scheduler    | Track A vision grade |
                | (deferred)           | -> g_intake (SHIPPED)|
----------------+----------------------+----------------------+----------------------
 MANDI /        | Track C arbitrage    | Track B twin = the   | Track D waterfall
 WAREHOUSE      | (price feed SHIPPED, | Produce Life Ledger  | = rescue.py
                |  routing deferred)   | (SHIPPED)            | (SHIPPED)
----------------+----------------------+----------------------+----------------------
 RETAIL / STORE | newsvendor (SHIPPED) | markdown (SHIPPED)   | rescue.py (SHIPPED)
----------------+----------------------+----------------------+----------------------
 KITCHEN        | newsvendor (SHIPPED) | use-first, relocate  | rescue.py (SHIPPED)
                |                      | (SHIPPED)            |
```

---

## 2. The cascading waterfall: vocabulary adopted, ladder refused

The blueprint's six tiers already exist as `ChannelType` values in
[enums.py:90-98](../backend/foodos/schema/enums.py#L90-L98) — `staff_meal`, `markdown`,
`b2b_transfer`, `donation`, `processing`, `animal_feed`, `compost`. Nothing needed
building. What the blueprint adds is a **name** for each band, and a name is worth
having: "Tier 2" is faster to say to a category manager than "processing at a 0.34 price
factor".

What the blueprint also adds is a **rule** — assign the tier from remaining life alone:

```
RUL > 48 h    -> Tier 0 fresh retail        6-12 h  -> Tier 3 donation
24-48 h       -> Tier 1 B2B kitchens        2-6 h   -> Tier 4 animal feed
12-24 h       -> Tier 2 processing          < 2 h   -> Tier 5 biorefinery
```

**That rule is refused.** It is strictly less informed than
[optimiser.py](../backend/foodos/engine/optimiser.py)`::score()`, which already ranks the
same exits on recovered value net of logistics, risk, the sustainability weight and the
social term, behind a feasibility gate. A band drawn on remaining life alone cannot see
distance, minimum quantity, accepted categories, or a handover window.

This is not a theoretical objection. Here is the seeded demo's spinach batch, straight
out of `GET /api/rescue` — 23.4 kg at risk, ₹702 exposed, **19.4 hours of remaining
life**, which lands squarely in the ladder's Tier 2 processing band:

```
  ladder says   TIER_2_PROCESSING
  engine says   TIER_1_B2B_KITCHENS   Nalapaka Kitchen (400 m)   net Rs 375

  X  TIER_2  Nandini Puree Unit      does not accept leafy
  X  TIER_3  Feeding Hands NGO       requires 1 day of life for handover; has 0.8
  X  TIER_4  Dairy co-op feed line   needs 22 h (18 h lead + 4 h handling); 19 h left
```

The ladder routes this batch to a processor **that would physically reject it** — the
puree unit does not take leafy greens. Tiers 3 and 4 are shut too, on a handover rule and
a lead time. The one open exit is a kitchen 400 m away, and only the optimiser finds it.

Across the seeded site the ladder and the engine agree on **19 of 35** at-risk batches.
That is a high enough agreement rate for the tier to be a useful label and a low enough
one for the ladder to be a bad decision rule.

### What was built

Both are now reported on every rescue item, so the disagreement is visible rather than
hidden — [engine/waterfall.py](../backend/foodos/engine/waterfall.py):

| field | meaning |
| --- | --- |
| `waterfall_tier`, `waterfall_tier_rank` | per action — which tier this exit belongs to |
| `ladder_tier` | what the blueprint's RSL bands would have picked |
| `engine_tier` | what `score()` actually ranked first |
| `tier_agrees` | whether they match |

`ranked[]` order is untouched. `tier_agrees: false` is the interesting case, not an
error, and it is common on this screen by construction: a batch only reaches Rescue
because forecast demand will not clear it, so "keep selling it fresh" is usually the
wrong answer even when the food still has fresh-retail life left.

One mapping note. The blueprint's Tier 0 is *external* fresh retail; this is a kitchen,
so Tier 0 here means the batch is consumed as intended at this node — `use_first`,
`relocate`, `replan_menu`, `staff_meal`. Discounted human consumption elsewhere
(`markdown`, `b2b_transfer`) is Tier 1.

---

## 3. Arrhenius and Q10 are the same physics

The blueprint specifies `k = A·exp(−Ea/RT)`. The engine ships
`k(T) = k_ref · Q10^((T−T_ref)/10)` in
[ingest/shelf_life.py:8](../backend/foodos/ingest/shelf_life.py#L8). These are not
competing models — Q10 is the linearised Arrhenius form, and it is the one used in food
science precisely because `Q10 ≈ 2.5` for leafy produce is a number a chef can argue
with, while `Ea` in joules per mole is not. **No change.**

The blueprint's `RUL = (Q(t) − Q_crit) / k(T_forecast)` is a genuinely different
formulation from the engine's accumulated-life-fraction model, and it is not adopted: it
assumes a single forward decay rate, where the ledger accumulates life consumed per
interval, which is what lets the system say *"your spinach lost 2.1 days on the dock at
31 °C"* rather than just reporting a number.

The real gap is **scale, not physics**. The blueprint works in hours because it models
crates in transit; this engine works in days because it models stock at a node.
`waterfall.py` converts at the boundary and nothing else changes.

---

## 4. What was built

Three slices, all additive. No existing API field moved, was renamed, or changed value —
`contracts/mock/*.json` is byte-identical after the new keys are stripped.

### AGMARKNET / e-NAM mandi prices — [ingest/agmarknet.py](../backend/foodos/ingest/agmarknet.py)

A **file connector, not a network client**: AGMARKNET publishes daily arrivals and prices
as a CSV, and that is what is read. No socket is opened, so the aeroplane-mode rehearsal
still passes. Drop `agmarknet.csv` beside the dataset and it loads; leave it out and
every screen behaves as before.

- Published prices are **per quintal**; the table stores **per kilogram**. The ÷100 lives
  in the loader, because getting it wrong inflates every produce price by 100×.
- A commodity alias table bridges two vocabularies that do not match on a string compare
  — a kitchen says "Coriander leaves", the mandi says `Coriander(Leaves)`.
- 66 rows of Karnataka sample data ship in `backend/data/sample/agmarknet.csv`, covering
  all 22 produce SKUs across three arrival days.

It surfaces as `market_reference` on each rescue item — *context beside the recovery
figure, not a term inside it.* It deliberately does **not** feed `score()`. A wholesale
quotation from a market this batch is not in is information for a human; wiring it into
the objective would move every rupee figure in the demo on the strength of a name match.

### AgStack GeoID — `Site.geo_id`

A nullable 16-character field on `Site`, read from `sites.csv` if present, exposed on
`GET /api/health`. **Carried, never computed** — B has no boundary geometry to hash. It
is empty today and populates the day a registration step supplies it, in the same
no-code-change way the engine already prefers a stored `Forecast` row over its own
baseline.

### Waterfall tiers — [engine/waterfall.py](../backend/foodos/engine/waterfall.py)

Section 2. Nine tests in
[tests/test_engine/test_waterfall.py](../backend/tests/test_engine/test_waterfall.py),
including one that fails if a future change ever lets the ladder gate the ranking.

---

## 5. Deferred, with the unlock condition

| Blueprint capability | Unlock condition |
| --- | --- |
| Track C split-batch route optimiser | more than one site with real velocity data. The action type exists (`transfer`); what is missing is a second destination worth solving for. Greedy by value density is correct at demo scale; a Hungarian solve at production scale. |
| Track C dynamic reserve pricing on e-NAM | the markdown engine already chooses depth against the demand distribution. Publishing that price to an external exchange is a channel adapter, and it needs a counterparty. |
| Track A micro-climate harvest scheduler | a farm node in the dataset. This is the newsvendor with `harvest_qty` in the action space — the same closed form, different cost terms. It is a config change, not a product, which is exactly the platform claim. |
| Track A vision grading at the farm gate | already specified as `g_intake` in the RSL formula and listed as optional in Product Design §6. The hook exists; the model does not. |
| Beckn / ONDC catalogue broadcast | a real BPP counterparty. As a **channel adapter** under RECOVER this is reasonable and cheap. See §6 for the version of it that is rejected. |

---

## 6. Rejected, and why

Each of these is already on the kill list in
[Product Design §12](FoodOS-Product-Design.md) or
[War Plan §11](FoodOS-Hackathon-War-Plan.md). The blueprint does not supply a new argument
for any of them, so the rulings stand.

| Proposal | Ruling |
| --- | --- |
| `POST /api/v1/telemetry/ingress` — BLE / cellular IoT | **Rejected.** Item one on both kill lists. Storage conditions are accepted as digital input: declared, uploaded or simulated. Track B has no data source without hardware, which makes it the one blueprint track that cannot be built at all. |
| LSTM thermal excursion prediction | **Rejected.** Training a model from scratch, on telemetry that does not exist, to predict an excursion the Q10 model already prices when it happens. |
| Beckn / ONDC auction as the **primary** surface | **Rejected as the product**, deferred as a channel. "A marketplace as the primary product" is a named kill-list entry: matching needs density first, and leading with it makes the intelligence look like a side feature. |
| Solar evacuation router, live logistics routing | **Rejected.** War Plan §13 is explicit: routing turns a sharp pitch diffuse and cannot be faked convincingly. The FEFO placement decision gives 80% of the story at 5% of the cost. |
| Fixed RUL → tier ladder as the routing rule | **Rejected.** §2. Adopted as a label. |
| A second objective function for any of the above | **Rejected.** [backend/README.md](../backend/README.md): one `score()`, three action spaces, or the platform claim is fiction. |

---

## 7. Where the blueprint is right, and it matters

Two things in it are better than what the existing docs say, and both are kept.

**The farm-gate loss data is the stronger framing.** Guava at 11.59% farm-level loss
against 3.46% at market, tomato at 8.37% against 3.25% — that is a sharper statement of
where produce actually dies than anything currently in the deck, and it argues for
opening at the farm rather than the kitchen, which
[War Plan §13](FoodOS-Hackathon-War-Plan.md) already recommends on rubric grounds.

**Naming the tiers is a real improvement.** The engine had seven channel types and no
vocabulary above them. "Tier 2" is a unit of thought; `price_factor: 0.34` is not.

---

## 8. Frontend impact

Additive only. Ignoring every new field leaves all seven screens exactly as they are.
Contract detail in [api-contract.md](../contracts/api-contract.md); mocks regenerated.

- `SiteOut.geo_id` — null today.
- `ActionOut.waterfall_tier` / `waterfall_tier_rank` — a chip on the row. Null on the
  do-nothing baseline. **Do not sort by these.**
- `RescueItemOut.ladder_tier` / `engine_tier` / `tier_agrees` — render disagreement as a
  note, never as a warning.
- `RescueItemOut.market_reference` — nullable; null for meat, dairy, spices and prepared
  dishes, which have no mandi quotation. Flag `days_stale > 1` as stale.
