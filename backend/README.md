# FoodOS backend — Engine & API

Owner: **B**. Everything under `foodos/schema/`, `foodos/engine/`, `foodos/api/`,
`foodos/ingest/`, `foodos/config.py`, `pyproject.toml`, `../contracts/` and
`tests/test_engine/`.

> Predict which food will become waste, explain why, and recommend the highest-value
> action while there is still time to take it.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows
# source .venv/bin/activate       # macOS / Linux

cd backend
pip install -e ".[dev]"
```

Python 3.11.x is the team standard. Do not use conda or poetry.

## The two commands that matter

```bash
cd backend

# 1. Rebuild the whole demo database from scratch. Sacred — runs 50x before the demo.
python -m foodos.ingest.seed

# 2. Serve the API
uvicorn foodos.api.app:app --reload --port 8000
```

Then open <http://localhost:8000/docs>.

```bash
pytest tests/test_engine    # B's tests
pytest                      # everyone's (needs A's lightgbm installed)
```

### Where seed gets its data

In order, first one that exists:

| # | Source | When |
| --- | --- | --- |
| 1 | `backend/data/*.csv` | A has run their generator locally |
| 2 | `backend/data/sample/*.csv` | fresh clone — committed on purpose |
| 3 | built-in fixture | `--source fixture`, or neither of the above |

Force one with `--source generated | sample | fixture`. The built-in fixture is **B's**,
not a substitute for A's data — it exists so the engine and API are never blocked.

## Handoff with A

A writes rows; B reads them. Neither imports the other's modules. Full column contract
in `../contracts/ingest-contract.md`.

| What A supplies | How B uses it |
| --- | --- |
| `open_batches.rsl_days`, `life_used` | Used directly. B's Q10 estimate only fills batches A has not scored. |
| `products.is_produce` | The fruit-and-veg share headline. Authoritative — never inferred from category. |
| `products.plannable` | Which products get a PREVENT quantity. Not the same as `is_dish`. |
| `products.co2e_kg_per_uom` | Per-product CO2e. Falls back to a global intensity only when absent. |
| `products.portion_kg` | Converts portions to kilograms. |
| `waste.reason` | Attribution. A owns the reason codes; B aggregates them, never infers them. |
| `Forecast` table *(not yet written)* | The engine already prefers a stored `Forecast` row over its own empirical baseline — **the day A writes rows, the engine starts using them with no code change.** |

A's ids are readable strings (`ING_TOMATO`, `B01609`). The database keeps integer keys;
`ingest/loader.py` holds the translation.

## Handoff with C

`../contracts/api-contract.md` — **frozen at H3**. Exact response bodies in
`../contracts/mock/`, regenerated with:

```bash
python -m foodos.ingest.seed
python ../scripts/dump_mocks.py
```

Never hand-edit a mock; regenerate it, then tell C in the same breath.

## Handoff with D

Rescue channels are D's content, not A's data. B ships defaults in
`ingest/channels.py` and reads `foodos/content/channels.json` (or `.yaml`, if PyYAML is
around) the moment it appears.

## The architecture rule

There is **one** objective function: `engine/optimiser.py::score()`.

```
V(a) =  E[value recovered | a]
      - cost(a)
      - P(loss | a) * value_at_risk
      + lambda * waste_aversion_per_kg * kg_food_saved
      + mu     * social_value
```

PREVENT, PRESERVE and RECOVER are three **action spaces** scored by that one function.
The newsvendor fractile is not a second objective — it is the closed-form maximiser of
`V(Q)` over the quantity action space, and
`tests/test_engine/test_prevent.py::test_closed_form_is_the_argmax_of_the_objective`
grid-searches the objective to prove it, across three lambdas and three margin
structures.

**If you catch yourself writing a second objective function, stop and add an action type
instead.** One V(a), three action spaces, or the platform claim in the pitch is fiction.

Related rule: nothing numerical comes from a language model. Optimisers compute; the LLM
explains. Every figure in an API response traces to `score()` or to a stored model run.

## Layout

```
foodos/
  config.py           settings, cost defaults, lambda, the demo clock
  db.py               engine + session
  schema/             SQLAlchemy 2.0 tables + enums
  ingest/
    loader.py         A's CSVs -> canonical schema
    mapping.py        column-name aliases
    validation.py     coercion + gap reporting
    profiles.py       category -> shelf-life constants (B reference data)
    shelf_life.py     deterministic Q10 fallback
    channels.py       rescue channels (D's content, B defaults)
    sample_data.py    B's built-in fixture
    seed.py           *** python -m foodos.ingest.seed ***
  engine/
    context.py        DecisionContext — lambda, mu, costs
    actions.py        Action + the do-nothing baseline
    optimiser.py      *** V(a) — the only objective function ***
    risk.py           derived risk: qty at risk, P(waste), value at risk
    distribution.py   quantile grid -> usable demand distribution
    prevent.py        newsvendor + BOM explosion
    preserve.py       use-first, relocate
    rescue.py         channel ranking + feasibility gate
    planner.py        orchestration (holds no business rules)
    recommendation.py Recommendation lifecycle + acceptance rate
    simulator.py      savings simulator + backtest counterfactual
    tracks.py         retail + production action spaces
    queries.py        every SELECT lives here
  api/                FastAPI app — 11 screen endpoints + health + upload
tests/test_engine/
```
