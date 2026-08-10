# API contract — B → C

**FROZEN AT H3.** Changes after the freeze go through a message to C before the commit,
never after. `backend/foodos/api/schemas.py` is the machine-readable version; if the two
ever disagree, the code wins and this document is stale.

> **Post-freeze changes, all additive — nothing existing moved or was renamed.**
> `2026-08-10` · `SiteOut.geo_id`, and on `/api/rescue`: `waterfall_tier` /
> `waterfall_tier_rank` per action, plus `ladder_tier`, `engine_tier`, `tier_agrees`
> and `market_reference` per item. Existing fields are byte-identical — see
> `docs/FoodOS-Blueprint-Reconciliation.md` for why they exist. Ignoring all of them
> leaves every screen exactly as it was.

- Base URL: `http://localhost:8000`
- Interactive docs: `/docs` (generated from the same Pydantic models)
- Exact response bodies: `contracts/mocks/*.json`, regenerated with
  `python scripts/dump_mocks.py` — **never hand-edited**, so they cannot drift.

## Shared query parameters

Every screen endpoint accepts these. None are required.

| param | type | meaning |
| --- | --- | --- |
| `site_id` | int | defaults to the first site. Get the list from `/api/health`. |
| `lambda` | float, 0–5 | sustainability weight. **Moves `C_o`, which moves `q*`, which moves every quantity in the plan.** This is what the slider sends. |
| `today` | date | overrides the demo clock. Leave unset. |

Errors are FastAPI's standard shape: `{"detail": "..."}` with 404 (unknown id),
400 (bad upload) or 503 (empty database — tell the user to run the seed).

## The 11 screen endpoints

| # | Method | Path | Screen |
| --- | --- | --- | --- |
| 1 | GET | `/api/today` | Today |
| 2 | GET | `/api/attribution` | Why |
| 3 | GET | `/api/plan` | Plan |
| 4 | GET | `/api/frontier` | Plan — the lambda slider chart |
| 5 | GET | `/api/ledger` | Ledger |
| 6 | GET | `/api/rescue` | Rescue |
| 7 | GET | `/api/impact` | Impact |
| 8 | POST | `/api/recommendations/{id}/accept` | any card |
| 9 | POST | `/api/recommendations/{id}/override` | any card |
| 10 | GET | `/api/tracks/retail` | Track 2 |
| 11 | GET | `/api/tracks/production` | Track 3 |

Plus two infrastructure endpoints: `GET /api/health` and `POST /api/ingest/upload`.

## The recommendation card

Every card on every screen renders the same object. Five things, always present:

```jsonc
{
  "id": 1,
  "horizon": "PREVENT",              // PREVENT | PRESERVE | RECOVER — drives the chip
  "subject_label": "Chicken Biryani",
  "action_type": "set_prep_qty",
  "baseline_value": 86,              // what happens if nobody acts
  "recommended_value": 68,           // what we recommend  -> render "86 → 68"
  "saves": { "kg": 7.4, "money": 1304.0, "co2e": 18.5 },
  "confidence": "HIGH",              // HIGH | MEDIUM | LOW
  "rationale_text": "Reduce tomorrow's Chicken Biryani from 86 to 68 portion...",
  "rationale_facts": { "cu": 186.0, "co_effective": 107.3, "q_star": 0.634 },
  "status": "pending",               // pending | accepted | overridden | expired
  "override_reason": null,
  "expires_at": "2026-02-13T06:00:00"
}
```

`baseline_value` and `recommended_value` are **always quantities in the subject's own
unit**, never scores. For a PRESERVE/RECOVER card the baseline is `0` (doing nothing
actions nothing) and the recommended value is the quantity to move. The objective
function's value lives in `rationale_facts.objective_value` if you want it.

**Render rules.** Show `saves.money` as the headline. `rationale_text` is one sentence
and already written — do not summarise it. `confidence: LOW` should be visibly hedged.

## Notable response shapes

### `GET /api/today`

```jsonc
{
  "kpis": {
    "kg_at_risk": 57.3,
    "value_at_risk": 1770.0,
    "recoverable_today": 296.0,        // rupees, from taking the best open action
    "preventable_share": 0.90,         // overproduction + trim, as a share of value
    "produce_share_of_weight": 0.26    // the fruit-and-veg headline
  },
  "waste_drivers": [ { "reason": "overproduction", "kg": 0, "value": 0, "share": 0.78 } ],
  "recommendations": [ /* cards, best first */ ]
}
```

`waste_drivers` is pre-sorted and `share` sums to 1 — render it as the bar list without
recomputing anything.

### `GET /api/plan`

`lines[]` carries `baseline_qty`, `recommended_qty`, `delta`, the forecast band
(`forecast_low` / `forecast_median` / `forecast_high`) and `economics` — the full cost
pair behind `q_star`. Put `economics` behind a "why this number" disclosure; it is the
strongest thing on the screen under questioning.

`ingredient_requirement[]` is the dish plan exploded through the recipe BOM, grossed up
by standard yield.

### `GET /api/frontier`

`points[]` is a lambda sweep: `{lambda, total_recommended_qty, expected_waste_kg,
saving_kg, saving_money, saving_co2e}`. Plot it once, then move a marker as the slider
moves — **do not refetch `/api/plan` on every drag**, refetch on release.

### `GET /api/ledger`

One row per open batch. `severity` ∈ `critical` | `high` | `medium` | `low` — already
combines remaining life and waste probability, so colour straight from it.
`rsl_explanation` is a plain sentence meant to be shown verbatim.

### `GET /api/rescue`

Each item carries **two** lists:

- `ranked[]` — feasible options, best first
- `excluded[]` — options ruled out, each with `exclusion_reason`

**Render `excluded` too.** A chef who cannot see that donation was ruled out on a
handover window will assume the system forgot about it. Grey them out with the reason.

Note `net_recovery` and `score` differ: `net_recovery` is cash (`recovered − cost`),
`score` is the objective value including the risk, sustainability and social terms.
Show cash to the user; `terms{}` has the full breakdown for a tooltip. A donation row
can legitimately show ₹0 cash and still rank first.

#### Waterfall tiers — a label, not the order

Post-freeze additive change (2026-08-10). Every `ActionOut` now carries
`waterfall_tier` (`TIER_0_PRIMARY_FRESH` … `TIER_5_BIOREFINERY`) and
`waterfall_tier_rank` (0–5); both are `null` on the do-nothing baseline. Use them as
a chip on the row.

**Do not sort by them.** `ranked[]` is already ordered by `score` and that order is
the product. Each item also reports the comparison:

| field | meaning |
| --- | --- |
| `ladder_tier` | the tier a fixed remaining-life ladder would assign from `rsl_days` alone |
| `engine_tier` | the tier of the option the optimiser actually ranked first |
| `tier_agrees` | whether those two match |

`tier_agrees: false` is **not an error state** — it is the interesting case, and it is
common on this screen by construction (a batch only reaches Rescue because forecast
demand will not clear it, so "keep selling it fresh" is usually wrong even when it
still has fresh-retail life). Render the disagreement as a note, never as a warning.

#### `market_reference`

Nullable per item. When AGMARKNET mandi data is loaded and the product maps to a
recognised commodity, this is the latest quotation on or before `as_of`:

```jsonc
{
  "commodity": "Spinach",
  "market": "Bangalore",
  "arrival_date": "2026-02-12",
  "days_stale": 0,
  "modal_price_per_kg": 13.4,
  "min_price_per_kg": 11.4,
  "max_price_per_kg": 15.8,
  "source": "agmarknet"
}
```

`null` is normal — meat, dairy, spices and prepared dishes have no mandi quotation.
It is **context beside the recovery figure, not a term in it**: no number in
`ranked[]` is derived from it. Show `days_stale > 1` as stale.

### `GET /api/impact`

`backtest` is the credibility firewall — trained on one window, evaluated on days it
never saw. Surface `improvement_vs_naive` and `interval_coverage` next to the savings;
a coverage far from 0.8 means the confidence band is not honest and should be said so.

### `POST /api/recommendations/{id}/override`

```jsonc
{ "reason": "Friday footfall is always higher", "value": 72 }
```

`reason` is required. It is a signal, not a failure — it is stored and handed back to A.

## Rules of the road

1. **Every number comes from the API.** No arithmetic in the frontend beyond formatting.
   If a figure you need is not in a response, ask B to add it — do not derive it.
2. **Money is INR, weight is kg, CO2e is kg.** No unit conversion anywhere in C.
3. `null` means "not computed", not zero. `acceptance_rate` is `null` until something
   has been decided; render "—", not "0%".
4. Build against `contracts/mocks/` until B says an endpoint is live.


---

# Contract 2b — the agri batch surface

Added at H2–3 per `FoodOS-Team-Split-v2.md` §2. **Frozen at H3.**

This section is **additive**. Every one of the 11 kitchen endpoints above keeps
working byte for byte, and `tests/test_engine/` proves it on every run — that
regression suite is the platform claim, not a slide.

Same base, `http://localhost:8000`. Same error envelope. Same recommendation
card shape: `GET /api/batches/{id}.recommendation` is the card documented
above, unchanged, so C reuses `RecommendationCard` rather than writing a second.

## The 11 batch endpoints

| # | Method | Path | Screen |
| --- | --- | --- | --- |
| 1 | GET | `/api/questionnaire?commodity=tomato` | 2 — Create Batch, steps 1–3 |
| 2 | POST | `/api/batches` | 2 — submit answers + logistics |
| 3 | POST | `/api/batches/{id}/photos` (multipart, 3–5) | 2 — step 4 |
| 4 | GET | `/api/batches?status=&risk=` | 1 — Command Center |
| 5 | GET | `/api/batches/{id}` | 3 — Batch Intelligence hero |
| 6 | GET | `/api/batches/{id}/plans` | 3 — action evaluation matrix |
| 7 | POST | `/api/batches/{id}/simulate` | 4 — What-If |
| 8 | POST | `/api/plans/{id}/accept` | any card |
| 9 | POST | `/api/plans/{id}/override` body `{reason}` | any card |
| 10 | GET | `/api/markets?commodity=&near=` | 3/4 — destination price context |
| 11 | GET | `/api/health` | unchanged, already above |

## Shared query parameters

`lambda` behaves exactly as it does on the kitchen endpoints — it is the same
`DecisionContext.lam` reaching the same `score()`. On this surface it is
surfaced to C as `w_preserve`; both spellings are accepted and mean one thing.
There is one objective function.

## `GET /api/batches/{id}` — the Batch Profile

```jsonc
{
  "id": "T1024", "commodity": "tomato", "qty_kg": 10000,
  "origin": "Kolar Collection Hub", "destination": "Delhi APMC",
  "harvested_at": "2026-08-10T06:00:00", "transport": "open_truck",
  "packaging": "ventilated_plastic_crate",
  "state": { "quality_score": 72, "grade": "B+", "maturity": "high",
             "damage_factor": "moderate", "field_heat_hours_over_30c": 4.2 },
  "risk": { "loss_pct": 8.4, "loss_kg": 840, "low": 6.7, "high": 10.9,
            "rul_hours": 31, "level": "HIGH", "confidence": "HIGH" },
  "drivers": [ { "name": "field_heat_hours", "contribution": 0.31, "text": "..." } ],
  "best_plan_id": 4,
  "recommendation": { /* the frozen card shape, unchanged */ }
}
```

Field notes C should build against:

| field | meaning |
| --- | --- |
| `id` | the public code (`T1024`), not the database key. Safe to display. |
| `risk.low` / `risk.high` | the quantile band. **Render a band, never a point.** A missing band means the row was scored by the deterministic fallback, not by A's model. |
| `risk.level` | `LOW` \| `MEDIUM` \| `HIGH`. Drives Screen 1 grouping and the risk colour token. |
| `risk.confidence` | `LOW` \| `MEDIUM` \| `HIGH`. **Independent of `level`.** A batch can be HIGH risk at LOW confidence; that pairing is the reason the band exists. |
| `drivers[]` | ranked, `contribution` sums to ~1.0. Model output — never a hardcoded list. |
| `state.*` | any field may be `null` before the questionnaire or photos land. Screen 3 must render a partial profile rather than blank. |
| `best_plan_id` | points into `/plans`. `null` until plans are generated. |

## `GET /api/batches/{id}/plans` — the action evaluation matrix

```jsonc
{ "id": 4, "label": "Split 6T Delhi / 4T Jaipur + depart 6h earlier",
  "loss_pct": 3.9, "loss_kg": 390, "logistics_cost": 31500,
  "gross_revenue": 153760, "net_value": 122260,
  "delta_vs_baseline": 7700, "is_baseline": false, "is_best": true,
  "feasible": true, "exclusion_reason": null,
  "terms": { /* every term of V(a), so no number is unattributable */ } }
```

Rules this endpoint guarantees:

- **The baseline is always present**, exactly one row with `is_baseline: true`.
  `delta_vs_baseline` on every other row is measured against it.
- **Infeasible plans are returned, not filtered.** `feasible: false` with a
  populated `exclusion_reason`. Grey the row and show the reason — a hidden
  option looks like the engine never considered it.
- Exactly one row carries `is_best: true`, and it matches
  `batch.best_plan_id`.
- `terms` is the full V(a) breakdown. If a judge asks where `net_value` came
  from, the answer is in this object.

## `POST /api/batches/{id}/simulate` — What-If

Request is exactly Screen 4's four controls:

```jsonc
{ "departure_shift_hours": -6, "transport": "tarpaulin",
  "destinations": [{"mandi": "delhi_apmc", "qty_kg": 6000},
                   {"mandi": "jaipur_apmc", "qty_kg": 4000}] }
```

Response is **the same plan object** as a `/plans` row, through the same
`score()`. This is not a similar code path — it is the same one. If the
simulator and the recommendation ever disagree on stage, one of them is a
second objective function and the pitch is fiction.

`destinations[].qty_kg` must sum to the batch `qty_kg`; a mismatch returns 422
rather than silently rescaling.

## `GET /api/questionnaire?commodity=tomato`

Returns D's adaptive tree from `content/questionnaire/{commodity}.yaml` as
data. Every node carries the `feature_key` it writes into A's `fuse()`.

**C never hardcodes a question in TSX.** Adding a second commodity has to be a
content change, not a frontend release.

## `POST /api/batches/{id}/photos`

Multipart, 3–5 images. Returns the updated `state` block.

Photos are optional at every step. A batch registered with zero photos still
scores through A's rule-based fallback, at lower `confidence`. The upload
endpoint existing is not the same as the upload being required.

## `GET /api/markets?commodity=&near=`

Destination price context from D's `external/agmarknet.py`, per kilogram.

Carries `source: "snapshot" | "live"`. **Render it.** Ruling 3 — the demo runs
offline, prices come from a committed snapshot, and a stale price shown as
live is the one number a judge could catch us on.

## Degradation contract

A is the only owner of a model, and A may not have landed one yet. Every field
above that comes from A has a deterministic placeholder behind the same shape:

- `risk.*` — a Q10 fallback, `model_run_id: null`, `confidence: "LOW"`.
- `drivers[]` — may be `[]`. Screen 3 hides the block rather than showing an
  empty chart.
- `state.quality_score` — may be `null` before the questionnaire.

**An A outage degrades the number. It never 500s the screen.**
