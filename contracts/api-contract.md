# API contract — B → C

**FROZEN AT H3.** Changes after the freeze go through a message to C before the commit,
never after. `backend/foodos/api/schemas.py` is the machine-readable version; if the two
ever disagree, the code wins and this document is stale.

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
