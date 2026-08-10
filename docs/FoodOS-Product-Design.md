# FoodOS — Product Design Specification

**B2B Food Waste Intelligence Platform** · Software only, no hardware · Hackathon MVP: Track 1

> **FoodOS is not a waste reporting tool. It is a decision engine that helps businesses prevent food from becoming waste in the first place.**

**The loop:** PREDICT → PREVENT → PRESERVE → RECOVER

**The four questions the system answers, in order:**
1. What food is likely to become waste?
2. Why is it likely to become waste?
3. What should the business do right now?
4. How much food and money will that action save?

**The organising principle.** Three customer tracks, one engine. PREVENT, PRESERVE and RECOVER are not tracks and not products — they are the three *action types* the same engine emits, and every track uses all three. What differs between tracks is the connector on the way in, the action space in the middle, and the view on the way out. The core is identical, and that is what makes three tracks buildable by one team.

---

## 1. Product architecture

### Five layers, track-agnostic core

```
  CONNECTORS          CANONICAL            INTELLIGENCE         DECISION            DELIVERY
  ------------        -----------          -------------        ----------          ----------
  CSV / Excel   -->   Site                 Demand forecaster    Action space   -->  Dashboard
  POS export          Product / Dish  -->  (quantile)      -->  generator           Prep card
  Inventory dump      Recipe / BOM         RSL estimator        Feasibility         Digest / alert
  Waste log           Batch                Waste attribution    gate                WhatsApp msg
  Storage log         InventoryEvent       Risk scorer          Optimiser           CSV / API out
  (API, later)        SalesRecord                               Explainer (LLM)
                      WasteEvent
                      |                          |                    |                   |
                      +--------------------------+--------------------+-------------------+
                                                 |
                                          RECOMMENDATION
                                     (the first-class output object)
```

| Layer | Responsibility | Track-specific? |
| --- | --- | --- |
| Connectors | Ingest, map columns, validate, dedupe, backfill | **Yes** — different source systems per track |
| Canonical | One schema for every track. A dish, a retail SKU and a production batch are all `Product` + `Batch` | No |
| Intelligence | Forecast demand, estimate remaining life, attribute past waste, score risk | No — same models, different entities |
| Decision | Generate feasible actions, score them, rank them, explain them | **Partly** — same optimiser, different action space |
| Delivery | Present one number to each role, capture the response | **Yes** — different surfaces per role |

### The Recommendation object — the thing that makes this a decision engine

Most food-waste products stop at a chart. The single architectural choice that separates FoodOS from analytics is that **every recommendation is a persistent, tracked object with a lifecycle and a measured outcome.**

```
Recommendation
  id, site_id, created_at, horizon (PREVENT | PRESERVE | RECOVER)
  subject_type      dish | batch | sku | production_run
  subject_id
  action            {type, parameters}      e.g. {set_prep_qty, 63}
  baseline          what would have happened anyway   e.g. 80 portions
  expected_saving   {kg, money, co2e}
  confidence        derived from forecast interval width
  rationale         structured facts + LLM narrative
  status            pending -> accepted | overridden | expired
  override_reason   free text / picklist, fed back into the model
  outcome           measured after the fact: actual_saving {kg, money}
```

This buys four things at once: an **acceptance rate** metric (a recommendation nobody follows has zero impact), a **realised-vs-projected** savings report that makes the product provable, a **feedback signal** for the models via override reasons, and a clean audit trail so every number in the UI traces back to a model run.

### Non-negotiable boundary: what computes what

```
  ML / statistical models  ->  every forecast, every distribution, every probability
  Deterministic optimiser  ->  every quantity, every ranking, every rupee figure
  LLM                      ->  narrative, root-cause phrasing, menu drafting,
                               message writing, and nothing numerical
  Verifier agent           ->  checks LLM output against the computed facts and
                               the safety rules before any human sees it
```

If a number appears in the interface, it came from the optimiser. The LLM receives computed values as structured input and is never asked to produce one. This is both an engineering rule and the answer to *"how do I know these savings aren't hallucinated?"*

---

## 2. User roles

Design rule: **one number per person.** Only the owner or ops head gets a dashboard; everyone else gets a single artifact they act on.

### Track 1 — Commercial kitchens

| Role | Sees | Decides | Cadence |
| --- | --- | --- | --- |
| Head chef / cook | Tomorrow's prep card, ~8 lines, plus "use first" flags | Accept or override prep quantities | Daily, 6 pm |
| Storekeeper / purchase | Goods-receipt entry, weekly purchase list | Confirms receipts, places orders | Daily + weekly |
| Kitchen / F&B manager | Today screen: at-risk value, ranked actions | Approves rescue actions, markdowns, transfers | Daily |
| Owner / multi-outlet ops | Impact screen: food-cost %, realised savings, outlet ranking | Buys the product, sets targets | Weekly |

### Track 2 — Retail, distribution, cold storage

| Role | Sees | Decides | Cadence |
| --- | --- | --- | --- |
| Store manager | Markdown sheet and FEFO pick list | Applies discounts, executes picks | Twice daily |
| Category / inventory manager | Batch ledger, at-risk value by category | Order quantities, transfers between stores | Daily + weekly |
| Warehouse supervisor | Batch ageing, zone alerts, dispatch priority | Which lot ships where, in what order | Daily |
| Regional ops / shrink owner | Shrink trend, recovery rate, store ranking | Policy, channel partnerships | Weekly |

### Track 3 — Production

| Role | Sees | Decides | Cadence |
| --- | --- | --- | --- |
| Production planner | Recommended run quantities with confidence range | Sets the production schedule | Daily |
| Demand planner | Forecast vs actual, promo and holiday uplift | Adjusts assumptions and calendars | Weekly |
| Plant / ops manager | Yield vs plan, waste attribution by line | Line changes, batch sizing | Daily |
| Finance / commercial | Cost of waste, cost of stockout, margin impact | Sets the service-level policy and λ | Monthly |

### System roles (all tracks)

**Admin** — sites, users, cost parameters, λ, integrations. **Analyst** — read-only across sites, exports. **Integration** — API keys, scheduled imports.

Permission verbs: `view` · `capture` · `accept` · `override` · `approve_rescue` · `configure`.

---

## 3. User journeys

### Onboarding — the first 14 days (identical for all tracks)

Time-to-value matters more than feature count. The system must be useful before the forecaster is trained.

| Day | What happens | What the customer gets |
| --- | --- | --- |
| 0 | Upload 30–90 days of history via the mapping wizard | Data validated, gaps flagged |
| 1 | Attribution runs on history | **First insight already**: waste split by cause, top contributors, avoidable trim — needs no forecast |
| 2 | Shelf-life profiles assigned by product category; storage zones entered once | Food Life Ledger live, RSL on every batch |
| 3–9 | Daily capture begins; forecaster trains on history plus new data | Directional prep/order recommendations, marked low-confidence |
| 10 | Forecast crosses the accuracy threshold against the seasonal-naive baseline | Recommendations go full-confidence |
| 14 | First realised-savings report | **Measured** saving vs baseline, plus acceptance rate |

### Track 1 — Commercial kitchen, daily loop

```
  05:30  Overnight batch: forecast refresh, RSL decay, risk rescoring
  07:00  STOREKEEPER  goods receipt -> batch created, RSL initialised
  09:30  CHEF         opens today's prep card (generated 6 pm yesterday)
                      "use first" flags on low-RSL ingredients
  12:00  service
  15:00  CHEF/staff   prep-waste capture: quantity + reason, 30 seconds
  18:00  SYSTEM       tomorrow's plan generated
         CHEF         reviews: 8 dishes, old qty vs recommended qty,
                      accepts or overrides with a reason
  18:15  MANAGER      Today screen: at-risk items, ranked rescue actions
                      approves a transfer or a staff-meal allocation
  22:30  staff        service-waste capture
  Weekly MANAGER      Why screen: attribution trend, biggest driver
         PURCHASE     purchase list, pre-filled from the demand plan
         OWNER        Impact screen: realised savings, acceptance rate
```

### Track 2 — Retail / distribution, daily loop

```
  05:00  Batch run: RSL decay on every lot, demand-before-expiry recomputed,
         waste probability and value-at-risk refreshed
  07:00  STORE MGR    markdown sheet: SKU, batch, current price, recommended
                      discount, units expected to clear
         WAREHOUSE    FEFO pick list ordered by remaining life, not by date
  11:00  SYSTEM       midday deviation check: SKUs selling below forecast
                      escalate from "watch" to "act"
  16:00  STORE MGR    second markdown pass on what did not move
  18:00  SYSTEM       rescue window opens for anything that cannot clear:
                      transfer to a higher-velocity store, B2B buyer,
                      donation (eligibility-gated), processing
  Weekly CATEGORY MGR order recommendations at the priced service level
         OPS          shrink trend, recovery rate by channel
```

### Track 3 — Production, planning loop

```
  Weekly DEMAND PLANNER   14-day forecast with confidence bands per SKU,
                          promo and holiday uplift applied and shown separately
  Daily  PRODUCTION       recommended run quantity per SKU, adjusted for
         PLANNER          current finished inventory, open orders, min batch
                          size, changeover cost and line capacity
                          -> accept or override
  Post-  PLANT MGR        actual yield vs plan, waste attributed by line,
  run                     stage and cause
  Monthly FINANCE         cost of waste vs cost of stockout, realised margin
                          impact, review of the service-level policy and λ
```

---

## 4. Exact features

`M` = hackathon MVP · `1` = version 1 · `2` = later

### Core platform — shared by all three tracks

| # | Feature | What it does |
| --- | --- | --- |
| M | Ingestion & column mapping wizard | Upload CSV/Excel, auto-detect columns, map to canonical schema, validate, report gaps |
| M | Waste ledger | Every waste event with quantity, value, reason, subject and capture method |
| M | Attribution engine | Splits waste into overproduction, prep/trim, spoilage, plate waste, quality rejection — each with its own detector |
| M | Quantile demand forecaster | Predicts the demand *distribution* per entity per day, not a point estimate |
| M | Food Life Ledger | Per-batch remaining shelf life, waste probability, value at risk, recommended action |
| M | Waste risk scorer | P(this quantity is not consumed before its life runs out) |
| M | Action generator + optimiser | Builds the feasible action set, scores each, ranks them |
| M | Savings simulator | "If you follow this plan, expected waste falls from X to Y and you keep ₹Z" |
| M | Backtest / counterfactual | Replays held-out history through the engine and reports **measured**, not projected, savings |
| M | Recommendation lifecycle | Accept / override with reason; acceptance rate tracked as a first-class metric |
| M | LLM explanation layer | Diagnostician narrative, plain-language rationale on every card |
| 1 | Realised savings report | Projected vs actual, per recommendation, rolled up per site |
| 1 | Digest & alerts | Daily WhatsApp/email digest; threshold alerts on value at risk |
| 1 | Multi-site rollup | Site comparison, ranking, benchmark against peer sites |
| 1 | Cost & policy configuration | Per-item cost, disposal cost, margin, λ sustainability weight, service-level floor |
| 2 | POS / ERP connectors | Scheduled pull from common POS and inventory systems |
| 2 | Public API + webhooks | Recommendations out, outcomes in |

### Track 1 — Commercial Kitchen Intelligence

| # | Feature | What it does |
| --- | --- | --- |
| M | Recipe / BOM management | Dish → ingredients with quantity and standard yield |
| M | Prep card generator | Tomorrow's quantities per dish, printable A5, with "use first" flags |
| M | Overproduction detector | Produced vs sold vs forecast, per dish, trended |
| M | Trim-yield benchmarking | Actual yield vs standard culinary yield table → avoidable trim in kg and ₹ |
| M | Ingredient explosion | Dish plan → ingredient requirement in kg, and from there the purchase list |
| M | At-risk ingredient rescue | Ranked actions for ingredients whose life will expire before use |
| 1 | FEFO-aware menu suggestions | Draft a menu or special that consumes the lowest-RSL stock, ranked by margin and predicted demand |
| 1 | Quick waste capture | Reason-coded entry in under 30 seconds; optional photo with a reference card for item ID and rough mass |
| 1 | Plate-waste analysis | Served vs returned → portion-size recommendations |
| 2 | Event & banquet mode | One-off large-volume forecasting from guest count and menu |

### Track 2 — Inventory & Shelf-Life Intelligence

| # | Feature | What it does |
| --- | --- | --- |
| 1 | Batch / lot tracking | Receipt to depletion with lineage, quantity and storage zone |
| 1 | RSL engine at scale | Remaining life per batch, decayed daily against storage conditions |
| 1 | Demand-before-expiry | Expected units sold before life runs out → quantity at risk |
| 1 | FEFO pick list | Pick order by remaining life rather than printed date |
| 1 | Dynamic markdown engine | Recommended discount and timing to maximise expected recovered revenue |
| 1 | Transfer recommendations | Move stock to a site with higher velocity for that SKU |
| 1 | Shrink reporting | Loss by category, cause and store, with recovery rate by channel |
| 2 | Rescue channel directory | B2B buyers, processors, NGOs with eligibility rules and pickup windows |
| 2 | Donation compliance pack | Eligibility gate, handover record, impact reporting |

### Track 3 — Production Intelligence

| # | Feature | What it does |
| --- | --- | --- |
| 1 | Production run recommendation | Quantity per SKU per run, from the demand distribution and waste/stockout economics |
| 1 | Confidence range display | The interval, shown explicitly, so a planner can see when to trust it |
| 1 | Constraint-aware lot sizing | Min batch size, line capacity, changeover cost, shelf-life of the finished good |
| 1 | Raw material requirement plan | Production plan exploded into inputs, timed against their own shelf life |
| 1 | Promotion & holiday uplift | Modelled separately and shown as a separate component of the forecast |
| 2 | SKU rationalisation | Which SKUs structurally overproduce and cost more than they earn |
| 2 | Multi-plant allocation | Which plant makes what, given demand geography and shelf life |

---

## 5. Data model

Canonical schema. A restaurant dish, a retail SKU and a manufactured product are all `Product`; a prep container, a crate and a production lot are all `Batch`.

```sql
-- ORGANISATION -------------------------------------------------------------
Organization(id, name, track, timezone, currency)
Site(id, org_id, name, type)            -- kitchen | store | warehouse | plant
User(id, org_id, name, role, phone, locale)
UserSite(user_id, site_id, permissions[])

-- CATALOGUE ----------------------------------------------------------------
Product(id, org_id, sku, name, category, uom,
        unit_cost, unit_price, is_dish, perishable)

Recipe(id, product_id, yield_qty, yield_uom)          -- dish or manufactured SKU
RecipeLine(recipe_id, ingredient_product_id, qty, uom,
           standard_yield_pct)                        -- e.g. cauliflower 0.58

ShelfLifeProfile(id, category, base_shelf_life_days, ref_temp_c,
                 q10, cut_life_factor, ethylene_sensitive,
                 ethylene_emitter)

StorageZone(id, site_id, name, mean_temp_c, temp_source)
                                        -- 'declared' | 'logged' | 'simulated'

-- INVENTORY ----------------------------------------------------------------
Batch(id, site_id, product_id, lot_code,
      received_at, produced_at, printed_expiry,
      qty_received, qty_remaining, uom,
      storage_zone_id, intake_grade,     -- 0..1, from entry or vision
      unit_cost, state)                  -- whole | cut | prepared
    -- derived, recomputed nightly:
    -- rsl_days, waste_probability, value_at_risk, co2e_at_risk

InventoryEvent(id, batch_id, ts, type, qty, ref)
      -- type: receive | move | consume | adjust | waste | transfer | markdown

StorageReading(id, storage_zone_id, ts, temp_c, source)

-- DEMAND & PRODUCTION ------------------------------------------------------
SalesRecord(id, site_id, product_id, business_date, qty, revenue, channel)
ProductionRecord(id, site_id, product_id, business_date,
                 planned_qty, actual_qty, uom)
DemandContext(site_id, business_date, dow, is_holiday, festival,
              weather_code, temp_max_c, promo_flag, covers, footfall)

-- WASTE --------------------------------------------------------------------
WasteEvent(id, site_id, business_date, product_id, batch_id,
           qty, uom, value, reason, stage, capture_method, note)
      -- reason: overproduction | prep_trim | spoilage
      --       | plate_waste | quality_rejection
      -- stage : storage | prep | production | service | post_service
      -- capture: manual | photo | pos_derived | inferred

-- INTELLIGENCE OUTPUT ------------------------------------------------------
Forecast(id, site_id, product_id, target_date, model_run_id,
         q10, q25, q50, q66, q75, q90, expected)

ModelRun(id, model_name, version, trained_at, window_start, window_end,
         metrics_json)                  -- pinball loss, MAPE, coverage

RiskScore(batch_id, as_of, rsl_days, expected_consumption_before_expiry,
          qty_at_risk, waste_probability, value_at_risk)

-- DECISION -----------------------------------------------------------------
Recommendation(id, site_id, created_at, horizon,
               subject_type, subject_id,
               action_type, action_params_json,
               baseline_value, recommended_value,
               expected_saving_kg, expected_saving_money, expected_co2e,
               confidence, rationale_facts_json, rationale_text,
               status, override_reason, expires_at, model_run_id)

RecommendationOutcome(recommendation_id, measured_at,
                      actual_value, actual_saving_kg, actual_saving_money)

-- RECOVER ------------------------------------------------------------------
Channel(id, org_id, type, name, contact, geo, lead_time_hours,
        min_qty, accepted_categories[], price_factor, eligibility_rules_json)
      -- type: internal_use | staff_meal | markdown | b2b_transfer
      --     | donation | processing | animal_feed | compost

RescueOffer(id, batch_id, channel_id, qty, expected_recovery,
            status, sent_at, responded_at)
```

**Two design notes worth defending in a review.** First, `RiskScore` is *derived*, not modelled — it falls out of the forecast distribution and the RSL, so there is no separate model to train or explain. Second, `Recommendation` stores `baseline_value` alongside `recommended_value`, which is the only way the savings number can be honestly computed and later verified.

---

## 6. AI / ML models

| Model | Type | Input | Output | Used by |
| --- | --- | --- | --- | --- |
| Demand forecaster | LightGBM quantile regression, one model per quantile | Lags, rolling means, day-of-week, month, holiday and festival calendar, weather, promo flag, covers/footfall, price | q10 … q90 per product per day | PREVENT, risk scoring |
| RSL estimator | Deterministic kinetic model + learned residual correction | Product category profile, age, storage temperature, intake grade, handling, cut state | Remaining shelf life in days | PRESERVE, risk scoring |
| Waste attribution | Rules + benchmark comparison (deliberately not ML) | Produced, sold, waste log, recipe standard yields | Waste split across five causes, with the top contributors | All |
| Risk scorer | Derived, no training | Forecast distribution + RSL + quantity on hand | P(waste), quantity at risk, value at risk | PRESERVE, RECOVER |
| Markdown response | Log-log price elasticity per category, shrunk toward a prior | Historical discount and uplift pairs | Expected units sold at discount d | RECOVER |
| Vision assist *(optional)* | Vision-language model, no training | Photo of a bin or a crate, with a printed reference card for scale | Item identification, rough mass, intake grade | Capture, PRESERVE |
| Agent layer | LLM | Structured computed facts only | Narrative, menu draft, outbound message | Explanation |

### Forecaster specifics

Baseline to beat: **seasonal naive** (same weekday last week). Report the improvement over it — a forecast that cannot beat seasonal naive should not be allowed to change a prep quantity, and the system should say so rather than pretend.

Metrics: **pinball loss** across quantiles (the correct metric for a distributional forecast), MAPE at the median for human intuition, and **interval coverage** — if the 10–90 band is honest, roughly 80% of actuals fall inside it. Coverage is the number that makes the confidence range trustworthy.

Cold start: hierarchical fallback. `site × product` → `site × category` → `org × category` → `category prior`. Shrink toward the specific level as its own data accumulates, so the system is useful on day one and sharp in about three weeks.

### RSL estimator specifics

Explainable by construction, and never described as "AI freshness detection":

```
k(T)   = k_ref * Q10 ^ ((T - T_ref) / 10)        Q10 ~ 2 to 3 for fresh produce

dLife  = (dt / base_shelf_life) * Q10 ^ ((T - T_ref) / 10)

RSL    = base_shelf_life
         * (1 - sum(dLife))                       accumulated life consumed
         * g_intake                               quality at receipt, 0..1
         * g_handling                             bruising, ethylene adjacency
         * g_cut                                  ~0.35 once cut or prepared
```

Every factor is a stated assumption a chef or a category manager can argue with, which is exactly what you want. Storage temperature comes from a declared zone value, an uploaded log, or a simulated profile — all three are digital inputs, no sensor is required. A learned residual model is layered on later, once observed spoilage outcomes exist to calibrate against.

### Agent layer

| Agent | Job | Guardrail |
| --- | --- | --- |
| Diagnostician | Turns the attribution output into a root-cause narrative | Receives only computed facts; may not introduce a number |
| Planner | Drafts a menu, special, or shelf plan that consumes low-RSL stock | Must respect margin floor, allergens and category rules |
| Communicator | Writes the outbound message to a buyer, NGO or supplier | Templated fields; quantities injected, never generated |
| Verifier | Checks every agent output against the computed facts and the safety rules before it surfaces | Blocks on mismatch; failures are logged, not silently retried |

---

## 7. Decision and optimisation logic

### One objective function, three action spaces

```
For each subject s (a dish, a batch, a run) choose the action a
from the feasible set A(s) that maximises:

  V(a) =  E[ value recovered | a ]
        - cost(a)                            discount, logistics, labour, disposal
        - P(loss | a) * value_at_risk
        + lambda * kg_food_saved             sustainability weight, configurable
        + mu     * social_impact             donation channels only

subject to:
        RSL(s) >= lead_time(a) + handling_margin(a)
        eligibility(a, s)                    safety, category, contractual
        capacity and minimum-quantity constraints
```

The three intervention types are the same maximisation over different action sets:

```
PREVENT   A = { set_prep_qty, set_order_qty, set_production_qty }
PRESERVE  A = { sequence_first, transfer, markdown, re-plan menu,
                fix storage placement }
RECOVER   A = { deep markdown, b2b transfer, donate, process,
                animal feed, compost }
```

### PREVENT — the quantity decision

The correct quantity under demand uncertainty is the newsvendor solution, and it is a closed form:

```
C_u = contribution margin lost if you run out           (felt keenly)
C_o = unit cost + labour + disposal cost
      + lambda * co2e_price                             (felt by nobody)

q*  = C_u / (C_u + C_o)              the economically optimal service level
Q*  = Forecast.quantile(q*)          read straight off the distribution
```

**Worked example — Track 1.** Chicken biryani: `C_u = ₹186`, `C_o = ₹94`. Then `q* = 186/280 = 0.66`, and the 66th percentile of tomorrow's forecast is **63 portions**. The kitchen habitually prepares 80, which is roughly the 92nd percentile — because running out is visible and waste is not. The 17-portion gap is the waste, and it is a pricing error rather than carelessness.

**Track 3 adds constraints.** Same `q*`, then round to feasible lot sizes and amortise changeover cost:

```
Q_final = argmax over feasible lot sizes L of
          [ E[revenue | L] - production_cost(L) - changeover_cost(L)
            - E[waste value | L] ]
```
Expected demand 8,000 units, habitual run 10,000, `q*` at the 0.62 fractile gives 8,180, rounded up to the 8,400 minimum lot → **recommend 8,400**.

**λ is the product's most demonstrable control.** Raising it shifts `C_o` up, `q*` down, and the whole plan toward less waste at a small margin cost. Expose it as a slider and show the frontier — it converts an abstract sustainability claim into a visible trade-off.

### PRESERVE — the sequencing and pricing decision

```
qty_at_risk = qty_on_hand - E[ consumption before RSL expires ]

where E[consumption before expiry] integrates the demand distribution
over the remaining-life window, NOT over the printed date window
```

**Worked example — 20 kg spinach, RSL 1.2 days.** Expected usage in that window is 8 kg, so **12 kg is at risk** with a value at risk of ₹480. Actions evaluated: promote spinach into tomorrow's menu (recovers full value on ~5 kg, gated by predicted dish demand), transfer 4 kg to a nearby site with higher spinach velocity, discount or rescue the remainder. The ranked plan recovers ₹390 of the ₹480 rather than ₹0.

Markdown depth is chosen, not guessed:
```
choose d maximising   price * (1 - d) * E[ units sold | d ]
                    - holding cost - P(unsold | d) * disposal cost
```

Storage placement is a real, cheap win: the ethylene-adjacency check flags an emitter (tomato, banana, apple) stored beside a sensitive item (leafy greens), which measurably shortens the sensitive item's life. It costs nothing to fix and it makes the product sound like it has been inside a kitchen.

### RECOVER — the channel decision

Rank every channel by net recovery, then apply the feasibility gate **before** ranking is shown, so an ineligible option never appears:

| Channel | Typical recovery | Gate |
| --- | --- | --- |
| Use in today's menu / shelf | ~100% of value | RSL > service window |
| Staff meal | cost avoidance | RSL > service window |
| Markdown | 55–70% | RSL > expected shelf dwell |
| B2B transfer to a nearby buyer | 60–80% | RSL > transit + handling margin |
| Processing (puree, pickle, juice) | 25–40% | quality grade above threshold |
| Donation | no cash, high social value | eligibility rules, handover window |
| Animal feed | 5–10% | not spoiled, no contaminants |
| Compost | 0% | last resort, still beats landfill |

With several batches and several channels this becomes a small assignment problem — a greedy pass by value density is sufficient at demo scale and exactly correct with a Hungarian solve at production scale.

**The output is never "keep or bin".** It is a ranked list with a rupee figure on each row and one reason each option was excluded.

---

## 8. Dashboard structure

Seven screens. Role determines the landing screen: chef → Plan, manager → Today, owner → Impact.

| Screen | Question it answers | Primary content |
| --- | --- | --- |
| **Today** | What should I do right now? | Three KPIs: kg at risk, ₹ at risk, ₹ recoverable today. Then ranked recommendation cards. |
| **Why** | Why is this happening? | Attribution breakdown by cause, top contributing dishes/SKUs, trend, avoidable-trim callout |
| **Plan** | How much should I make or buy tomorrow? | Old vs recommended quantity per item, λ slider, expected waste and savings updating live |
| **Ledger** | What is the state of everything I hold? | Food Life Ledger table: batch, quantity, RSL, risk, value at risk, recommended action |
| **Rescue** | What do I do with what is already at risk? | At-risk items with ranked channels, excluded options and reasons, one-tap outreach |
| **Impact** | Is this actually working? | Realised vs projected savings, acceptance rate, backtest, forecast accuracy vs baseline |
| **Settings** | — | Costs, margins, λ, service-level floor, recipes, storage zones, channels, users |

### The recommendation card — the atomic UI unit

Every card, on every screen, carries the same five things:

```
+--------------------------------------------------------------+
|  [PREVENT]                              confidence: HIGH      |
|                                                               |
|  Reduce tomorrow's biryani prep                               |
|  80 portions  ->  63 portions                                 |
|                                                               |
|  WHY   Friday demand has been overestimated by 23% for        |
|        12 days. Median forecast 61, optimal service level     |
|        0.66 given a Rs 186 margin and Rs 94 unit cost.        |
|                                                               |
|  SAVES  8.4 kg   |   Rs 1,500   |   21 kg CO2e                |
|                                                               |
|  [ Accept ]   [ Override... ]              expires 06:00      |
+--------------------------------------------------------------+
```

**What · why · how much · how confident · one tap to act.** A card without a rupee figure and a reason is analytics, not a decision engine.

### The Today screen

```
+---------------------------------------------------------------------+
|  FoodOS   Spice Garden, Koramangala          Thu 12 Feb   [Manager]  |
+---------------------------------------------------------------------+
|                                                                      |
|   42.6 kg            Rs 18,420           71%                         |
|   at risk today      value at risk       judged preventable          |
|                                                                      |
+---------------------------------------------------------------------+
|  WASTE DRIVERS, LAST 30 DAYS                                         |
|    Overproduction   ###########################   54%                |
|    Prep / trim      ##########                    19%                |
|    Spoilage         #######                       14%                |
|    Plate waste      #####                          9%                |
|    Quality          ##                             4%                |
+---------------------------------------------------------------------+
|  ACTIONS, RANKED BY VALUE                                            |
|                                                                      |
|  [PREVENT]  Biryani 80 -> 63 tomorrow      8.4 kg | Rs 1,500  [>]    |
|  [PRESERVE] Spinach RSL 1.2 d, use first   12 kg  | Rs   480  [>]    |
|  [RECOVER]  Paneer 4 kg -> transfer 400 m  4 kg   | Rs   620  [>]    |
|  [PRESERVE] Move tomatoes away from greens 0.8 d  | Rs   140  [>]    |
+---------------------------------------------------------------------+
```

### Surfaces beyond the dashboard

**Prep card** — printable A5, generated 6 pm, eight lines, no login. **Digest** — one WhatsApp or email message per day per role. **Capture** — a 30-second reason-coded entry form, optionally a photo. **Exports** — purchase list and markdown sheet as CSV.

---

## 9. Hackathon MVP

### Scope

**Built fully — Track 1, Commercial Kitchen Intelligence**

Ingestion of 30–90 days of CSV · attribution across all five causes · quantile demand forecaster · newsvendor prep planner with the λ slider · Food Life Ledger over 12–15 ingredients · at-risk rescue ranking · recommendation cards with accept and override · savings simulator · backtest on held-out days · LLM explanation layer · four screens (Today, Why, Plan, Ledger) plus Impact if time allows.

**Stubbed deliberately — Tracks 2 and 3**

One screen each, running on **the same engine** with a different action space and a small sample dataset. Retail shows the batch ledger with markdown recommendations; production shows a run-quantity recommendation with its confidence range. This proves the "one engine" claim in sixty seconds without building two more products — and the proof is the point, because it is what makes the platform story credible rather than aspirational.

**Not built** — see section 12.

### Build order — 36 hours, four people

| Hours | Priority | Work |
| --- | --- | --- |
| 0–3 | P0 | **Synthetic dataset generator first.** 90 days, 14 dishes, 40 ingredients, recipe BOM, POS lines, goods receipts with storage zones, realistic weekday and festival seasonality. Then plant three faults on purpose: Friday biryani over-prep, a bad cauliflower trim yield, a storage excursion. |
| 3–10 | P0 | Canonical schema, ingestion, attribution engine, RSL engine, quantile forecaster. Pure Python, CLI-testable, unit-tested against the planted faults. Frontend shell built in parallel against a JSON contract frozen at hour 3. |
| 10–18 | P0 | Action generator, newsvendor optimiser, rescue ranking, Recommendation object and lifecycle. Today / Why / Plan screens. |
| 18–25 | P0 | Ledger screen, savings simulator, backtest view, λ slider. This is the minimum complete story. |
| 25–30 | P1 | LLM agent layer with the Verifier. Track 2 and Track 3 stub screens on the same engine. |
| 30–33 | P1 | Prep card, capture flow, polish, empty and error states. |
| 33–36 | P0 | **Freeze.** Seed the database, rehearse six times, record a backup video, run once with networking disabled to catch hidden calls. |

**Fallback, decided at hour 25.** If behind, cut the Track 2 and Track 3 stubs and the LLM layer before cutting the backtest. A working Track 1 with a backtest beats a broken three-track demo by a wide margin.

### Work division — four people

Ownership is by **module, not by task**, so nobody waits on a code review and merge conflicts stay rare. The thing that makes genuine parallel work possible is the **JSON contract frozen at hour 3**: after that, C builds against mock responses and B builds the real ones, and neither blocks the other.

| | Owner | Owns end to end |
| --- | --- | --- |
| **A** | Data & Models | Synthetic dataset generator, attribution engine, quantile forecaster, RSL engine, backtest harness, all accuracy metrics |
| **B** | Engine & API | Canonical schema, ingestion, action generator, optimiser, rescue ranking, Recommendation lifecycle, every endpoint |
| **C** | Frontend | All seven screens, the recommendation card component, λ slider, charts, print stylesheet |
| **D** | Agents, content & demo | LLM agent layer and Verifier, recipes and yield tables, cost data, channel rules, all UI copy, deck, script, rehearsals |

**Pick A first and start them immediately.** The dataset is the critical path — B, C and D are all partly blocked until sample data exists, so A writes the generator before anyone writes anything else.

#### Person A — Data & Models

```
H0-3    Synthetic dataset generator. 90 days, 14 dishes, 40 ingredients,
        recipe BOM, POS lines, goods receipts, storage zones, weekday and
        festival seasonality. Plant three faults deliberately (Friday
        biryani over-prep, cauliflower trim yield, storage excursion).
        SHIP A SAMPLE FILE BY H3 - everyone else is blocked on it.
H3-6    Attribution engine: five causes, each with its own detector.
H6-10   Quantile forecaster + seasonal-naive baseline + pinball loss,
        MAPE and interval coverage.
H10-14  RSL engine: kinetic model, category profiles, cut and handling
        factors, ethylene adjacency check.
H14-18  Backtest harness: train days 1-20, evaluate 21-30, counterfactual
        savings, accuracy against the baseline.
H18-25  Tuning. Verify all three planted faults are actually detected.
        Markdown elasticity priors.
H25-30  Sample datasets for the Track 2 and Track 3 stub screens.
H30-36  Verify every number that appears in the demo. Support only.
```

#### Person B — Engine & API

```
H0-3    Repo skeleton, canonical schema, and the JSON contract drafted
        jointly with C. FREEZE THE CONTRACT AT H3.
H3-8    Ingestion, column mapping, validation, seed loader.
H8-12   Action generator + newsvendor optimiser (PREVENT).
H12-16  Rescue ranking, feasibility gates, Recommendation object and its
        accept/override lifecycle.
H16-20  Savings simulator; λ plumbed from settings through to output.
H20-25  Endpoints for all screens; seed script that rebuilds the demo
        state from scratch in one command.
H25-30  Track 2 and Track 3 action spaces - same optimiser, different
        action set. This is the proof that the platform claim is real.
H30-36  Freeze, reseed, bug triage on the demo path only.
```

#### Person C — Frontend

```
H0-3    Shell, routing, design tokens, chart setup. Co-author the JSON
        contract with B.
H3-8    Build against mock JSON: Today screen and the recommendation card
        component (every screen reuses it - build it properly once).
H8-14   Why screen (attribution breakdown), Plan screen (old vs
        recommended table).
H14-18  λ slider with live recomputation. Ledger screen.
H18-22  Rescue screen with excluded-option reasons. Impact screen with
        the backtest chart.
H22-28  Swap mocks for the real API. Empty, loading and error states -
        a blank screen mid-demo reads as a crash.
H28-33  Polish, responsive behaviour, print stylesheet for the prep card.
H33-36  Freeze. Walk the demo path ten times looking for dead ends.
```

#### Person D — Agents, content & demo

```
H0-3    Dataset realism spec with A: which pathologies, and what numbers
        must fall out of them. Deck skeleton.
H3-10   Real content, and it is real work: recipes, standard culinary
        yield tables, ingredient costs, dish margins, channel rules and
        safety gates. Wrong costs make every rupee figure wrong.
H10-16  Agent prompts (Diagnostician, Planner, Communicator) and the
        Verifier's rule set. UI copy for every card and empty state.
H16-22  Wire the agent layer to B's API. Verify the Verifier actually
        blocks a bad output - then keep that as a slide.
H22-28  Deck and demo script, timed to 4:40.
H28-33  Rehearsals 1-3. Record the backup video after rehearsal 3.
H33-36  Rehearsals 4-6, aeroplane-mode run, contingency plan.
        D PRESENTS - they did not build the backend, so they will
        explain it in language a judge understands.
```

#### Sync points — 15 minutes each, standing up

| Hour | Gate | Fails if |
| --- | --- | --- |
| **H3** | Contract freeze + sample dataset shipped | Either is missing — everything downstream slips |
| **H10** | Models return real output through B's engine | Forecaster still not beating seasonal naive |
| **H18** | First end-to-end run: upload → attribution → plan → saving | Any hop still mocked |
| **H25** | **Fallback decision.** Are the stubs and the agent layer in, or out? | Decide honestly here; do not decide at H33 |
| **H30** | Feature freeze. Bugs only after this. | Anyone is still adding |
| **H33** | Code freeze, database seeded, backup video recorded | Rehearsal has not started |

#### Rules that prevent the usual failures

- **Nobody edits another person's module.** File a request; the owner fixes it. Four people in one file at hour 30 is how demos die.
- **Everything runs from the seed script.** One command rebuilds the whole demo state. If a demo depends on a database someone hand-edited, it will not survive a laptop restart.
- **If a person falls behind, they cut scope, not quality.** A shipped Today screen beats a half-built Today screen plus a half-built Rescue screen.
- **A slips → everyone helps A.** Nothing else matters if the dataset is not real enough for the engine to find something true.
- **The demo path is sacred.** After H30, a bug outside the demo path is not a bug.

---

## 10. Demo flow

Five minutes. One restaurant, one narrative, no feature tour.

| Time | Beat | What the audience sees |
| --- | --- | --- |
| 0:00 | **The frame** | "Food businesses don't waste food because they're careless. They waste it because they make four decisions a day with no information. We fix the decisions." |
| 0:20 | **Upload** | Drop in 30 days of a real-shaped restaurant's sales, production, inventory and waste data. Mapping wizard resolves the columns live. |
| 0:45 | **The total** | ₹68,400 and 412 kg wasted last month. State it flatly — this is the part everyone else's product also does. |
| 1:05 | **The causes** | Attribution: 54% overproduction, 19% avoidable trim, 14% spoilage. Biryani and naan are the top contributors. |
| 1:30 | **The pattern** | Click through to biryani: 12 days of production against sales, over by 23% every Friday. The Diagnostician narrates the cause in one sentence. |
| 2:00 | **The forecast** | Tomorrow's demand distribution, not a single number. Median 61, 10–90 band shown, accuracy against the seasonal-naive baseline displayed next to it. |
| 2:25 | **The decision** | Recommended prep 63, not 80 — with the reasoning visible: margin ₹186, cost ₹94, optimal service level 0.66. Then hand a judge the λ slider and let them drag it. |
| 2:55 | **The saving** | 8.4 kg and ₹1,500 tomorrow. Roll it forward: ₹41,000 and 248 kg a month. |
| 3:20 | **The ledger** | Switch to inventory. Spinach, 20 kg, RSL 1.2 days, 12 kg at risk, ₹480 exposed — and the reason the life is 1.2 days and not the 4 on the label. |
| 3:45 | **The rescue** | Ranked actions: use first in tomorrow's menu, transfer 4 kg, discount the rest. ₹390 recovered against ₹0. Two channels shown greyed out with the reason they were excluded. |
| 4:10 | **The proof** | Backtest. Trained on days 1–20, evaluated on days 21–30 the model never saw, measured against a naive baseline. "This is not a projection." |
| 4:35 | **The platform** | Two clicks: the same engine on a supermarket batch ledger, and on a bakery production run. "Same forecaster, same shelf-life model, same optimiser — only the available actions change." |
| 4:50 | **The close** | "FoodOS is not a waste reporting tool. It's a decision engine that stops food becoming waste in the first place." |

**The three beats that carry the score:** the λ slider at 2:25 (interactive, and it makes the economics visible), the backtest at 4:10 (verifiable rather than claimed), and the two-click platform proof at 4:35 (turns one product into a platform without three demos).

---

## 11. Long-term roadmap

| Phase | Scope | Unlock condition |
| --- | --- | --- |
| **V1 — Kitchen GA** (0–3 months) | Track 1 hardened. POS connectors for two or three common systems. Prep card, capture flow, realised-savings reporting, multi-outlet rollup. | Ten paying outlets with a measured, verified saving |
| **V2 — Shelf-life** (3–6 months) | Track 2. Batch tracking at scale, FEFO pick lists, dynamic markdown, transfers between sites, shrink reporting. | Batch-level inventory data available from a retail partner |
| **V3 — Production** (6–12 months) | Track 3. Run planning with capacity and changeover constraints, raw-material requirement planning, promo and holiday modelling. | A manufacturer with clean production and waste history |
| **V4 — Rescue network** (9–15 months) | Channel directory as a network: B2B buyers, processors, NGOs, feed. Matching, scheduling, compliance records. Take-rate on recovered value. | Enough site density in one cluster that a nearby buyer usually exists |
| **V5 — Upstream demand signal** (15 months+) | Aggregate verified consumption across sites into forward demand for distributors, wholesalers, FPOs and mandis. *"100 kitchens need 3.24 t of tomatoes next week, ±8%."* | A cluster large enough that the aggregate is meaningful and stable |

V5 is the long-term prize and the reason the data compounds — but it is explicitly **not** the hackathon MVP, and claiming it as one would undercut everything demonstrable. It belongs in the last thirty seconds of the pitch as direction, not as a feature.

---

## 12. What NOT to build

| Do not build | Why |
| --- | --- |
| IoT sensors, ESP32, MQTT, physical probes | Out of scope by decision. Storage conditions are accepted as digital input — declared, uploaded or simulated. |
| A consumer app | Different product, different distribution, different economics. B2B is where the decisions are made. |
| A generic donation app | Donation is one channel inside RECOVER, not the product. |
| A marketplace as the primary product | Matching is a V4 feature that needs density first. Leading with it makes the intelligence look like a side feature. |
| A generic analytics dashboard | This is the thing being displaced. Every screen must end in an action with a rupee figure. |
| Blockchain traceability | Adds no decision quality. |
| Auth, multi-tenancy, payments, native mobile | Real product work, zero demo value at a hackathon. |
| Training any model from scratch | Gradient-boosted trees on tabular data plus a kinetic shelf-life model beat anything trainable in 36 hours. |
| Real messaging-platform API integrations | Mock the interface faithfully; the integration eats a day and adds nothing. |
| Live logistics routing | A different problem with different infrastructure. |
| Any claim of "AI freshness detection" | Unsupportable, and the first thing a knowledgeable judge will attack. RSL is an explainable estimate and should always be described as one. |
| A separate codebase per track | The whole architectural claim collapses. Three tracks, one engine, or the platform story is fiction. |

---

## 13. Differentiation

| Category | Examples | What they do | Why FoodOS is different |
| --- | --- | --- | --- |
| Waste measurement hardware | Winnow, Leanpath, Orbisk | Smart scale and camera over each bin; automated measurement of what was thrown away | They tell you what you lost, after you lost it, and they need a capital purchase and an install per bin. We predict the loss beforehand and recommend the action, on a CSV and a phone. |
| Hospitality waste analytics | KITRO | Automated waste analytics for hotels and restaurants | Measurement and reporting. We add the forecast, the optimiser and the ranked action — the difference between a report card and a plan. |
| Surplus marketplaces | Too Good To Go, Karma | Sell food that has already become surplus, to consumers | They monetise surplus at the end. We prevent surplus, and route what is unavoidable through B2B and processing channels where recovery is higher. |
| Enterprise demand planning | RELEX, Blue Yonder, o9 | Retail and supply-chain forecasting and replenishment | Six-month implementations at enterprise prices, optimising availability with waste as a secondary constraint. We invert the objective, cost days not months, and start from a spreadsheet. |
| ERP inventory modules | SAP, Oracle, Petpooja, Posist | Record inventory, expiry dates and stock movements | They store the date. We estimate remaining *life* against storage conditions, convert that into risk and value at risk, and decide what to do. A date is a field; a decision is a product. |
| Produce supply-chain platforms | Ninjacart and similar | Move produce through the chain more efficiently | They optimise the movement. We optimise the decision — how much should exist, what to use first, and what to do with what is dying. Complementary rather than competing. |
| Generic BI | Power BI, Tableau, in-house dashboards | Charts of historical waste | A chart is not a decision. Every FoodOS screen ends in a quantity someone can act on before the next service. |

### The one-sentence positioning

> Everyone else in this category measures waste that has already happened, or moves food that has already become surplus. **FoodOS predicts which food will become waste, explains why, and recommends the highest-value action while there is still time to take it.**
