# FoodOS — Hackathon War Plan

**Track:** Food Waste Reduction · **Product:** three interventions, one engine, whole chain · **Build window:** 36 hours · **Hardware:** none

> **One question, asked three times.**
> *What is the highest-value thing to do with this food, right now?* Ask it before the food exists and the answer is a **quantity**. Ask it while the food is alive and the answer is a **placement and a price**. Ask it when loss is already locked in and the answer is a **channel**. Same question, same objective function, three horizons. That is the entire product.

---

## 1. The structural fix — read this before anything else

### Kitchens are not a track. They are a node.

The original three tracks were OPERATE, PRESERVE and FORECAST. There is a hidden problem in that list: **OPERATE is a customer segment (restaurants) wearing the costume of a capability, while PRESERVE and FORECAST are genuine capabilities.** Mixing the two kinds of thing is exactly why three tracks felt like three products that needed three demos and three dashboards.

Redefine the tracks by *when you intervene in the life of the food*, and every one of them applies at every node in the chain:

| Track | When | The answer it produces |
| --- | --- | --- |
| **PREVENT** | Before the food exists | A quantity — how much to harvest, buy, or prep |
| **PRESERVE** | While the food is alive | A placement and a price — where it goes, in what order, at what discount |
| **RECOVER** | When loss is locked in | A channel — the highest-value exit that is still open |

Now the kitchen is simply one node where all three run. So is the farm. So is the mandi. So is the store. You have gone from *three products for three customers* to **one product covering the whole supply chain** — which is precisely what Criterion 1 asks for, at 20% of the score.

### The coverage matrix — put this on a slide

```
                | PREVENT              | PRESERVE             | RECOVER
                | (before it exists)   | (while it lives)     | (when loss is locked in)
----------------+----------------------+----------------------+--------------------------
 FARM / FPO     | harvest to the       | pre-cooling and      | grade-outs to processing
                | cluster forecast,    | first-mile timing    | instead of ploughing
                | not to a standing    | against the heat     | the surplus back in
                | order                | of the day           |
----------------+----------------------+----------------------+--------------------------
 MANDI /        | buy to committed     | FEFO routing: which  | divert to the buyer who
 WAREHOUSE      | demand rather than   | crate goes where,    | can still sell it today,
                | to last week + 20%   | and in what order    | not the one who is nearest
----------------+----------------------+----------------------+--------------------------
 RETAIL /       | order quantity at    | dynamic markdown     | B2B transfer or donation
 STORE          | the priced service   | priced off remaining | while the food is still
                | level                | life, not the date   | legally donatable
----------------+----------------------+----------------------+--------------------------
 KITCHEN        | prep quantity via    | menu planned to      | transfer, staff meal,
                | newsvendor, exploded | consume the lowest-  | processing, animal feed,
                | through the recipe   | RSL stock first      | compost - ranked by value
```

Twelve cells. **One engine fills all twelve.** That is the sentence that turns breadth from a weakness into your strongest claim.

---

## 2. The shared spine — why this is one product and not three

Two objects sit underneath all three tracks.

### The Produce Life Ledger

Every batch of food in the system — a harvest lot, a crate, a shelf facing, a prep container — carries the same record, and it is continuously updated rather than stamped once:

```
Batch TM-4471
  sku            tomato, Kolar hybrid
  quantity       20.0 kg
  node           mandi -> store -> kitchen  (lineage preserved)
  RSL            4.4 days remaining   (NOT the 9 printed on the label)
  value          Rs 640 at current channel price
  waste risk     P(spoil before sale) = 0.31
  CO2e at risk   38 kg CO2e embedded
  recommended    route to Store 12 (high tomato velocity, 2 km)
```

### The Decision Engine

One objective function, evaluated at every node, at every horizon:

```
maximise over available actions a:

  V(a) =  E[ revenue recovered | a ]
        - cost(a)                          logistics, discount, labour
        - P(spoil | a) * value_at_risk
        + lambda * kg_of_produce_saved     the sustainability dial
        + mu * social_impact               donation channels

subject to:
        RSL(batch) >= transit(a) + handling_margin(a)
        food-safety eligibility(a)
```

The three tracks are not three algorithms. They are **the same maximisation over three different action spaces**:

```
horizon = BEFORE  ->  a in { harvest_qty, order_qty, prep_qty }
                      closed-form solution: the newsvendor fractile

horizon = DURING  ->  a in { route_to, sequence_first, markdown_pct,
                             fix_storage, re-plan menu }

horizon = AFTER   ->  a in { transfer_b2b, markdown_deep, donate,
                             process, animal_feed, compost }
```

**Say this to the judges.** Three tracks that share one ledger, one objective function and one codebase is an architecture. Three tracks that share a logo is a slide. The difference is the whole pitch, and it is also why you can genuinely build all three in 36 hours.

---

## 3. The reframe that wins Criterion 1

Criterion 1 carries 20% and asks for *direct effectiveness in reducing fruit and vegetable loss across the supply chain.* Criterion 6 names small farmers, mandi traders and local retailers. Criterion 7 names field operators and farmers.

The three-track structure covers the chain physically. But the strongest single claim you have is about **information flowing the other way**:

> **Every kilo of vegetables that rots in a kitchen bin was over-harvested on a farm three days earlier — because somebody guessed.**

A purchase order *is* a demand signal. Today, at every node, that signal is habit plus a fear buffer. Kitchens over-order because running out is loud and waste is silent. Stores over-order because empty shelves are visible and markdowns are not. That inflated signal is what tells the mandi to over-buy, and the mandi is what tells the farmer to over-harvest.

```
TODAY - THE SIGNAL IS A GUESS

    [ Farm ] --harvest--> [ Mandi ] --supply--> [ Store ] --> [ Kitchen ] ===> [ BIN ]
  over-harvest            over-buy            over-order    over-prep     18% of produce
        ^                                                        |
        +< - - - - - - - - - - - - - - - - - - - - - - - - - - - +
             "last week + 20%"  |  no confidence band  |  error compounds upstream


WITH FOODOS - THE SIGNAL IS A FORECAST

    [ Farm ] --harvest--> [ Mandi ] --supply--> [ Store ] --> [ Kitchen ] --> [ bin ]
 harvest to order        buy to order        order to plan   prep to plan   6% of produce
        ^                                                        |
        +<=======================================================+
             3.24 t tomato, week 32, +/-8%  |  per SKU, per day
             aggregated across 47 kitchens and 12 stores in the cluster
```

FoodOS adds no node to the chain. It replaces a guess travelling upstream with a **calibrated forecast carrying a confidence band** — the artifact no mandi trader or FPO has ever had. That is why a product that touches kitchens belongs in an agri track, and you should say it in the first minute.

---

## 4. Inside PREVENT — the intellectual core

### Waste is not a disposal problem. It is a mispricing problem.

Every chef in India over-prepares, and every one of them is being rational. Running out of biryani on a Friday is vivid — an angry table, a bad review, a manager's phone call. Throwing away 19 portions is a bin nobody weighs. One cost is loud, the other silent, so the kitchen optimises against the loud one and preps to roughly the 92nd percentile of demand. The store manager does the identical thing with shelf facings. The mandi trader does it with his standing order.

**That gap between the 92nd percentile and the economically correct percentile is the waste** — at every node. It is not carelessness, it is an unpriced risk. And there is a hundred-year-old, exactly-solvable result for it that almost nobody in a hackathon room will use: the newsvendor problem.

```
C_u  = lost contribution margin if you run out       (loud, felt)
C_o  = ingredient cost + labour + disposal fee
       + lambda * CO2e price                         (silent, unfelt)

q*   = C_u / (C_u + C_o)          <- economically optimal service level
Q*   = F-inverse(q*)              <- the quantity, read off the forecast
                                     *distribution*, not a point estimate

Chicken biryani:   C_u = Rs 186    C_o = Rs 94 + lambda*Rs 9
                   q*  = 0.66             Q* = 63 portions
Kitchen today:     q  ~= 0.92             Q  = 80 portions
```

```
        quantity prepped ->   40        63          80        100
                                         ^           ^
                                         |           |
    cost of running out  ########%%%%::::|...........|..........   falling
    cost of waste        ..........:::::%|%%%%#######|##########   rising
    -------------------------------------+-----------+----------
    TOTAL COST                        MINIMUM     WHERE THEY
                                     q* = 0.66     OPERATE TODAY
                                      FoodOS        q ~= 0.92

                                         |<- 17 portions ->|
                                            = Rs 1,500 / day
```

**Why this wins the technical criterion.** Every other team will forecast a *number*. You forecast a *distribution* — quantile-regression LightGBM — and then solve for where the two costs balance. It survives hostile questioning because it is a proven result rather than a heuristic, and it produces the savings figure as an **output** rather than an assumption. The lambda term is your sustainability dial: turn it up and the optimum slides left, trading a little margin for a lot of avoided produce loss. Put it on a slider and let a judge drag it.

The identical maths sets the FPO's harvest quantity and the store's order quantity. Only the cost terms change.

---

## 5. Inside PRESERVE — give every crate a life, not a date

### Remaining Shelf Life from spoilage physics, not a claimed freshness model

```
k(T) = k_ref * Q10^((T - T_ref)/10)        Q10 ~= 2.5 for leafy produce

dLife = (dt / SL_ref) * Q10^((T - T_ref)/10)

RSL   = SL_ref * (1 - sum(dLife)) * g_intake * g_handling * g_cut

  g_intake    <- vision model grades the crate at goods-receipt
                 (ripeness stage, defect fraction, bruising)
  g_cut       ~= 0.35   once produce is cut, life collapses
  g_handling  <- ethylene adjacency: tomatoes stored beside
                 leafy greens cost the greens ~0.8 days
```

```
  remaining life
     100% |o
          | \o
          |  |  <- 4 h on the mandi dock at 31 C = 2.0 days of life, gone
          |  |
          |  o
          |   \o          o o o    held at 4 C
      50% |     \o             o o o
          |       \o                 o o o
          |         \o                     o o o
          |           \o                         o o o
       0% +-------------o-----------------------------o--------
          0    1    2    3   ^ 4    5    6    7       ^   8   days
                             |                        |
                      ACTUALLY DEAD             LABEL SAYS
                         day 3.8                  day 7
```

Two crates, same label, three days of difference in usable life — and no system anywhere in the chain can currently tell them apart. So the chain either bins good produce or ships dead produce. The Ledger tracks the gap; FEFO routing and the markdown engine act on it.

> *"Your spinach didn't expire. It lost 2.1 days of life on the receiving dock at 31 °C."*

**Why physics and not "our AI predicts freshness".** Explainable to a chef and to a mandi trader, defensible to a judge, needs zero training data on day one, and calibrates against observed spoilage outcomes later. Teams claiming a black-box freshness model get asked *"trained on what?"* and have no answer. You have one.

### Waste attribution — five channels, each with its own detector

Overproduction, avoidable trim, spoilage, plate waste, quality rejection. The trim detector benchmarks actual yield against standard culinary yield tables and is the most produce-specific thing in the entire product:

> *"Your cauliflower yield is 51% against a 58% standard. That is 34 kg a month of edible florets going out as trim."*

---

## 6. Inside RECOVER — never a binary keep-or-bin

When loss is already locked in, the engine ranks every exit that is still open by recoverable value, under a hard food-safety gate:

| Exit | Typical recovery | Gate |
| --- | --- | --- |
| Use in today's menu / shelf | 100% of value | RSL > service time |
| Deep markdown | 55–70% | RSL > shelf dwell |
| B2B transfer to a nearby buyer | 60–80% | RSL > transit + handling margin |
| Processing (puree, pickle, juice) | 25–40% | quality grade above threshold |
| NGO donation | 0% cash, high impact | donation eligibility rules |
| Animal feed | 5–10% | not spoiled, no contaminants |
| Compost | 0% | last resort, still beats landfill |

> *"42 kg at risk. Best open exit is a B2B transfer 400 m away: Rs 1,650 recovered against Rs 0 for doing nothing."*

---

## 7. AI implementation — Criterion 4, 15%

| Layer | What it does | Which track |
| --- | --- | --- |
| Vision (VLM) | Grades produce crates at goods-receipt into g_intake; identifies and mass-estimates items in a bin photo against a printed reference card. No hardware. | PRESERVE, RECOVER |
| Forecasting (ML) | LightGBM quantile regression per SKU per node. Features: day-of-week, weather, festival calendar, promo, local events, footfall/covers, lags, rolling windows. Predicts the distribution, not the mean. | PREVENT |
| Optimisation (OR) | Newsvendor critical fractile for quantities. Constrained assignment for routing and rescue. Deterministic, auditable, instant. | all three |
| Agents (LLM) | Diagnostician writes the root-cause narrative. Planner drafts a menu or a shelf plan that consumes low-RSL stock. Broker writes the WhatsApp to the nearby buyer or the FPO. Verifier gates every recommendation against food-safety and feasibility rules before a human sees it. | all three |

> **The LLM never computes a number.**
> Optimisers compute; the language model explains, plans and communicates. Say this sentence out loud — it is the strongest maturity signal available to you, and it pre-empts the question every serious judge is holding: *"how do I know these savings aren't hallucinated?"*

---

## 8. Who uses it, and who pays

### The principle: downstream pays, upstream gets it free.

This is the question a judge will definitely ask, and a vague answer costs you more than the 5% on Criterion 8 — it makes the whole three-track story sound like it has no centre. The answer is one sentence:

> **Kitchens and stores pay us Rs 3,000 a month to save Rs 41,000. Farmers and FPOs get the forecast free, because their accuracy is what makes our downstream predictions good. And we take a cut of everything we rescue.**

That is not charity to the farmer. It is the only structure that works, for three reasons: FPOs and mandi traders have almost no software budget and near-zero SaaS adoption; the downstream nodes have both budget and a payback measured in days; and the forecast we hand upstream is only *possible* because of the downstream nodes we already serve. Giving it away is what builds the network nobody can copy.

### The eight people who touch the product

Divide by node and by what single thing they need to see. **One number per person** is the design rule — nobody except the owner gets a dashboard.

| Who | The one thing they see | Channel | Cadence | Pays? |
| --- | --- | --- | --- | --- |
| Chef / kitchen manager | Tomorrow's prep card — about 8 lines | WhatsApp + printed A5 | daily, 6 pm | no (owner does) |
| F&B owner / ops head | Food-cost %, rupees saved, outlet ranking | Dashboard | weekly | **YES** |
| Store / category manager | Today's markdown sheet by SKU | Tablet + shelf labels | twice daily | no (chain does) |
| Chain purchase manager | Pre-filled purchase order with confidence band | Dashboard, ERP export | weekly | **YES** |
| Mandi trader / commission agent | "Sell this lot first" routing list | WhatsApp, voice in local language | daily, 5 am | free |
| FPO manager | "Cluster needs 3.24 t tomato, ±8%, harvest Tue–Thu" | one WhatsApp message | weekly, Sunday | free |
| NGO / food bank coordinator | Donation offers: quantity, RSL, pickup window | WhatsApp | on trigger | free |
| Processor / feed buyer | Surplus lots with grade and asking price | web listing | on trigger | take-rate |

**Show four of these on stage, not eight** — the chef, the store manager, the FPO manager and the owner's dashboard. Those four span the chain and directly answer Criterion 7, which names non-technical field operators.

### Three revenue lines

| Line | Who pays | Price | Share of year-1 revenue |
| --- | --- | --- | --- |
| Subscription | kitchens and retail stores | Rs 3,000 per outlet / month, Rs 5,000 per store / month | ~85% |
| Rescue take-rate | whoever transacts the rescue | 6% of value recovered | ~15% |
| Committed-volume contracts | buyer cluster ↔ FPO | 1–2% of contract value | 0% in year 1 — the large one later |

The take-rate matters more than its size suggests: **it aligns our incentives with the outcome.** We earn more only when more food is actually rescued, and that is a sentence worth saying out loud. For chains, offer a savings-share alternative — 20% of verified savings, capped — which is zero-risk for the buyer and forces us to genuinely deliver.

### Unit economics, one restaurant

```
Mid-size multi-cuisine restaurant, 200 covers/day

  monthly food purchase           Rs 10,50,000
  food wasted (6.5%)              Rs     68,400   | 412 kg | 61% is produce
  recoverable by FoodOS (60%)     Rs     41,000   | 248 kg
  FoodOS subscription             Rs      3,000
  ------------------------------------------------------------------
  net monthly gain                Rs     38,000   | ROI 13.7x

  The subscription pays for itself in the first 3 days of every month.
```

This is a **spend-to-save sale, not a software sale** — which is why it closes in one meeting and why churn is low. The customer can see the saving on their own P&L as a food-cost percentage, independent of anything we report.

### Go to market: cluster-first, not city-first

This is the part most teams get wrong, and it is your best answer to "how does this scale".

> **We are not selling to 500,000 kitchens. We are selling to 200 outlets inside a 3 km radius — because density is what switches the product on.**

- The **rescue network** only works if there is a buyer 400 m away, not 40 km away. Below a certain density, RECOVER degrades to "discount or bin".
- The **upstream forecast** is only meaningful to an FPO once it aggregates real tonnage. One kitchen ordering tomatoes is noise; 47 kitchens and 12 stores is a harvest plan.
- **Sales cost** per outlet in one neighbourhood is a fraction of a city-wide campaign, and word of mouth between neighbouring kitchens is the cheapest channel in food service.

So: land 50 kitchens in one cluster. The network effects switch on around 30. Then walk to the FPO with committed volume — and that is a conversation nobody else in India is currently able to have.

### Why it compounds

Every node added makes every other node's forecast better, because they share the same demand pool. After twelve months in one cluster we know actual per-SKU, per-day produce consumption at the edge better than the trader, the retailer or the government does — and nobody else is collecting it, because everyone else stops at the transaction and we continue to the plate.

That dataset is the input to procurement contracts today and to **planting decisions** eventually. It is also the reason the later revenue line is the biggest one.

### Who else buys this later

- **Food processors** wanting predictable, graded surplus supply instead of spot-market scraps.
- **Hotel and QSR chains** facing mandatory food-waste and Scope 3 reporting — an ESG budget line that is growing fast and is separate from the ops budget.
- **Insurers** pricing spoilage and crop risk against real consumption data.
- **Municipal bodies** with organic-waste diversion mandates.

### Market sizing — label it as extrapolation when you say it

```
Year 1 target        1 cluster, 200 outlets            ~Rs 72 L ARR
One city (Bengaluru) ~5,000 addressable outlets        ~Rs 18 Cr ARR    [extrapolation]
India, organised     500,000+ food service outlets
                     plus organised food retail
```

State the year-1 number with conviction and the city number with the word "extrapolation" attached. Judges have heard a hundred national TAM claims; the team that marks its own uncertainty is the one they believe.

---

## 9. The demo — follow one crate

### Five minutes. One crate of tomatoes. Three kinds of waste stopped.

This is how you get breadth and depth at the same time. Do **not** demo three dashboards — that reads as three half-products. Demo **one crate travelling through all three tracks**, and the breadth arrives as narrative rather than as surface area.

Crate **TM-4471** — 20 kg of tomatoes, Kolar, harvested Tuesday 06:40.

**0:00 — THE LINE.** *"Every kilo of vegetables that rots in a kitchen bin was over-harvested on a farm three days earlier — because somebody guessed."* Then: *"We're going to follow one crate of tomatoes from that farm to a plate, and stop three different kinds of waste on the way."* No slide. Just the line.

**0:25 — PREVENT, at the farm.** Why does this crate exist? Because on Sunday, FoodOS sent the FPO an aggregated forecast: 47 kitchens and 12 stores in this cluster will consume 3.24 t of tomato in week 32, ±8%, per day, per SKU. The farmer harvested to that number. Show the counterfactual — without it, the trader's standing order over-buys by 18% and 580 kg never leaves the mandi. **Loss prevented before the crate existed.**

**0:55 — PRESERVE, at intake.** Photograph the crate. The vision model grades it: ripeness stage 4, 6% defect → true shelf life 6.2 days, not the 9 everyone assumed. Then it sat four hours on the dock at 31 °C: minus 1.8 days. Show the depletion curve. **The label was wrong by three days and nobody in the chain knew.**

**1:30 — PRESERVE, routing.** Because it has 4.4 days and not 9, FEFO sends it to Store 12 two kilometres away with high tomato velocity — not to the warehouse, where the same crate would have been 40% written off. The markdown engine prices the tail in advance.

**2:05 — PREVENT, at the kitchen.** 8 kg reaches Spice Garden. Newsvendor: prep 63 biryani, not 80 — q* = 0.66 against a habitual 0.92. Exploded through the recipe BOM that is 4.2 kg of tomato, not 5.6. Attribution adds: your tomato trim yield is 84% against a 91% standard, half a kilo a day leaving as peel.

**2:45 — RECOVER.** 3 kg left, RSL 0.4 days. The router ranks the open exits, the safety gate closes two of them, and B2B transfer to a kitchen 400 m away wins on value. The Broker agent drafts the WhatsApp. **Send it live**, with a teammate's phone on stage receiving it.

**3:20 — MONEY SHOT ONE: the crate ledger.** One crate. 20.0 kg harvested → 19.1 kg eaten by a human. Baseline: 13.2 kg. Then hand a judge the lambda slider and let them drag it from profit-optimal to planet-optimal and watch the whole chain re-plan.

**3:50 — MONEY SHOT TWO: the backtest.** *"This isn't a projection."* Trained on days 1–20, evaluated on days 21–30 the model never saw, against a naive same-as-last-week baseline. Measured counterfactual savings, with the forecast accuracy shown next to it. Almost no hackathon team validates on held-out data; the ones who do get remembered.

**4:20 — THE LOOP CLOSES.** Today's actual consumption updates Sunday's forecast to the FPO. Show the arrow completing. *"Every decision in this demo makes the next harvest more accurate. That is the part nobody else is building."*

**4:45 — THE CLOSE.** Unit economics × scale, explicitly labelled as extrapolation. Then the ask. Say the word "extrapolation" out loud — judges trust teams that mark their own estimates.

---

## 10. Rubric map — build to the weights

| Weight | Criterion | What earns it |
| --- | --- | --- |
| 20% | Impact on waste reduction | Three interventions × four nodes = the whole chain, demonstrated on one crate. Produce share attached to every headline number. Backtested, not projected. |
| 15% | Innovation & originality | One objective function across three horizons. Newsvendor framing of food waste. Physics-based RSL instead of a claimed freshness model. Trim-yield benchmarking. The upstream demand signal. |
| 15% | Technical execution | One engine, three action spaces, four thin views. Deterministic optimiser with LLM only at the edges. Held-out validation. |
| 15% | AI implementation | All four named modalities present and each justified: vision, predictive ML, multi-agent, LLM workflow. Plus "the LLM never computes a number". |
| 10% | Scalability | Adding a node is adding an action space, not a product. Hierarchical priors solve cold start. Stateless services, nightly batch, cluster aggregation without retraining. |
| 10% | Cost-effectiveness | Zero hardware anywhere in the chain. A POS export and a Rs 6,000 phone. Contrast with smart-scale rigs needing per-bin installation. |
| 10% | User experience | **One number per person.** The FPO gets a harvest quantity on WhatsApp. The mandi trader gets a routing list. The store manager gets a markdown sheet. The chef gets a printed prep card at 6 pm. Only the owner gets a dashboard. |
| 5% | Business viability | Rs 3,000/outlet/month against Rs 41,000 recovered — pays for itself in 3 days. Three revenue lines, one of them a take-rate that aligns us with the outcome. Cluster-first GTM with a real network effect. See section 8. |

### Differentiation — have this ready, you will be asked

| Them | What they do | Your line |
| --- | --- | --- |
| Winnow / Leanpath | Smart scale and camera over each bin. Measures what was thrown. | Hardware per bin, installation, weeks to deploy — and it stops at the kitchen door. We need a phone, and we run the length of the chain. |
| KITRO | Automated waste analytics for hospitality. | They answer *what* you threw away. We answer what to harvest, buy, prep and rescue — and we send the number upstream. |
| Too Good To Go | Consumer surplus marketplace. | They sell food that already became surplus. We stop it becoming surplus, and route it B2B when it does. |
| Ninjacart / Fruuto-style | Move produce through the chain more efficiently. | They optimise the *movement*. We optimise the *decision* — how much should exist, where it should go, and what to do when it is dying. Complementary, not competing. |
| Any BI dashboard | Charts of historical waste. | A chart is not a decision. Ours outputs a quantity someone can act on before service. |

---

## 11. Execution — 36 hours, four people, one engine

**The honest risk:** three tracks is more build surface than one. The mitigation is architectural, and you must commit to it at hour zero — **the three tracks share roughly 90% of the code.** One Ledger, one forecaster, one objective function, one attribution engine. What differs between tracks is only the action space and the view. Build three apps and you will not finish. Build one engine and three tracks costs perhaps 30% more than one.

**Hours 0–3 · P0 — Chain-wide synthetic dataset. Everything is blocked on this.**
90 days across four nodes with batch lineage preserved: farm harvest lots → mandi → store → kitchen. 40 produce SKUs, 14 dishes, recipe BOM, POS lines, goods-receipt logs with storage temperatures. Realistic day-of-week and festival seasonality. Then *plant one pathology per node on purpose*: an inflated standing order at the mandi, a dock-temperature excursion at intake, over-ordering at the store, Friday biryani over-prep and a bad cauliflower yield at the kitchen. **Your engine will discover them live on stage, and a system finding a real planted fault is far more convincing than one reciting a total.**

**Hours 3–10 · P0 — The spine.** Produce Life Ledger, RSL engine, attribution engine, quantile forecaster. One `decide(batch, horizon)` entry point with a pluggable action space. Pure Python, CLI-testable, unit-tested against the planted faults. Frontend shell built in parallel against a JSON contract frozen at hour 3.

**Hours 10–18 · P0 — The three action spaces.** Newsvendor for BEFORE. FEFO routing and markdown for DURING. Rescue ranking with the safety gate for AFTER. All three call the same objective function — if you find yourself writing a second one, stop and refactor.

**Hours 18–26 · P1 — Four thin views.** FPO harvest card, mandi routing list, store markdown sheet, kitchen prep card, plus the owner dashboard. These are *thin*. If time runs out, cut views, never the engine.

**Hours 26–32 · P1 — The demo flow.** "Follow one crate" as a scripted walkthrough, the backtest view, the lambda slider, the closing loop animation. These are your money shots — ship them even if the markdown sheet is rough.

**Hours 32–36 · P0 — Freeze. Seed the database. Rehearse six times. Record a backup video.**
Run once in aeroplane mode to catch every hidden network call. Time each rehearsal — five minutes means four minutes forty. The person who did *not* build the backend should present, because they will explain it in language a judge understands.

**Fallback, decided at hour 26:** if you are behind, ship KITCHEN + the upstream FPO forecast card only. Two nodes still tells the whole three-track story, and a working two-node demo beats a broken four-node one by a wide margin.

### Kill list — every one of these has sunk a hackathon team

- IoT sensors / ESP32 / MQTT / real telemetry
- Blockchain traceability
- Auth and multi-tenancy
- Payments and marketplace escrow
- Native mobile app
- Real WhatsApp Business API integration (mock the UI faithfully instead)
- Live truck routing and map animation
- Training any model from scratch
- A separate codebase per track

Every hour spent on these is an hour not spent on the backtest view, and the backtest view is worth more than all nine combined.

### Suggested stack

Frontend: React + Tailwind + Recharts. Backend: FastAPI + Postgres, or SQLite if it is faster to seed. Models: Python, LightGBM quantile regression, plain NumPy for the optimisers. Agents: Claude for the Diagnostician / Planner / Broker / Verifier layer and for the vision calls. No fine-tuning, no training from scratch.

---

## 12. Judge Q&A — rehearse the answers, not the questions

**"You're doing three things at once. Isn't that too broad for one product?"**
It is one thing asked three times. Same ledger, same objective function, same codebase — the only difference between the tracks is the set of actions available at that moment. Before the food exists the action is a quantity; while it lives it is a placement and a price; when loss is locked in it is a channel. That is why we could build all three in 36 hours, and it is why adding a fifth node is a config change rather than a new product.

**"This looks like restaurant software. How does it reduce loss on farms?"**
Two ways, and the second is bigger. Directly: the kitchen and the store are where produce actually dies, and 61% of wasted weight in our data is fruit and veg that nobody currently measures. Indirectly: a purchase order is a demand signal, and today that signal is habit plus a fear buffer. We replace it with a per-SKU, per-day forecast with a confidence band, aggregated across the cluster and delivered to the FPO. Over-harvest at the farm gate is downstream of over-ordering at the kitchen door.

**"How do I know these savings numbers aren't made up?"**
They are backtested, not projected. We train on days 1–20 and evaluate on days 21–30 the model never saw, then report the counterfactual against a naive same-as-last-week baseline. And the savings figure is an *output* of the optimiser rather than an input — it is the gap between where the operator sits today and the cost minimum. The language model never touches a number.

**"Who is your customer, if you serve farmers, mandis, stores and kitchens?"**
Kitchens and stores pay; farmers and FPOs do not. An outlet pays Rs 3,000 a month to recover Rs 41,000 — the subscription clears itself in the first three days of every month, so it is a spend-to-save sale, not a software sale. The FPO gets the aggregated forecast free, because their compliance with it is what makes every downstream prediction better, and because handing it over is what builds a network nobody can copy. On top of that we take 6% of the value of anything we rescue, which means we only earn more when more food is actually saved. Land where the money is, expand toward where the leverage is.

**"Four nodes and eight user types. How is that not an unfocused product?"**
Because we do not sell to four nodes. We sell to one *cluster* — roughly 200 outlets inside a 3 km radius — and everything else in the cluster comes along free. Density is what switches the product on: the rescue network needs a buyer 400 m away, and the upstream forecast is meaningless to an FPO until it aggregates real tonnage. One kitchen ordering tomatoes is noise; 47 kitchens and 12 stores is a harvest plan. We land 50 kitchens in one neighbourhood, the network effects switch on around 30, and then we walk to the FPO with committed volume.

**"A new node has no history. What does your model do on day one?"**
Hierarchical priors by cuisine, SKU category and node type, shrinking toward the specific node as its own data arrives. On day one you already get the Produce Life Ledger and trim-yield benchmarking, which need no history at all — just goods-receipt times and a standard yield table. The forecaster is useful in about ten days and sharp in three weeks.

**"You have no temperature sensors. How is your shelf-life model not a guess?"**
Q10 spoilage kinetics is established food science, and the inputs are things the chain already records or can record in one tap: goods-receipt timestamp, storage zone, dwell time on the dock. Zone temperatures are near-constant and entered once. Where a cold room already has a digital logger, we read it. And the model calibrates against observed spoilage outcomes, so it improves without ever needing a sensor per crate.

**"What if the chef or the trader ignores the recommendation?"**
Then we learn from it. Every override is logged with a reason, and persistent overrides shift the model — someone who always orders 10% above us on Fridays is telling us something our features missed. We track acceptance rate as a first-class metric, because a recommendation nobody follows has zero impact regardless of its accuracy.

**"Isn't 'buy less, prep less' just going to cause stockouts?"**
That is exactly the risk we price rather than ignore. The optimum is where the expected cost of a stockout equals the expected cost of waste — we are not minimising waste at any cost, we are minimising total cost, and running out sits *in* the objective function with its real margin attached. The lambda slider then lets an operator choose their own point on the frontier if they want to be more conservative than the maths.

**"Winnow and Leanpath already exist. Why you?"**
They need a smart scale and a camera rig per bin — a capital purchase and an installation visit, which is why they are in hotel chains rather than the 500,000 independent kitchens that make up most of Indian food service. We need a phone. And they stop at the kitchen door, measuring what was already thrown. We run the length of the chain and decide what should happen next.

---

## 13. Positioning discipline — what to cut

- **Three tracks, one demo.** The tracks are the architecture; the crate is the story. Never split the demo into three walkthroughs — follow TM-4471 and let the tracks reveal themselves as it moves.
- **Say "produce" and "fruit and vegetables" constantly.** Not "food", not "inventory". The rubric uses those words; use them back, and attach a produce share to every headline number.
- **Lead with the node the judges care about.** Open at the farm, not at the kitchen. The kitchen is where your best data and your fastest sale are, but the farm is where the rubric's attention is.
- **Do not build dynamic truck diversion.** Your original instinct was right. Routing turns a sharp pitch diffuse, and the demo needs infrastructure you cannot fake convincingly in 36 hours. The FEFO placement decision gives you 80% of the same story at 5% of the cost.
- **Label every extrapolation as an extrapolation.** Show the per-node unit economics and one honest multiplier. Judges have heard a hundred national TAM claims; the team that marks its own uncertainty is the one they believe.
- **Put the non-builder on the mic.** Whoever wrote the optimiser will explain the optimiser. You need someone who will explain the Rs 1,500.

> One line to open with, one crate to follow, and a number in the middle you can defend under pressure. That is the entire difference between second place and first.
