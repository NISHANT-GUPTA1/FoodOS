# FoodOS

**Decision infrastructure for perishable inventory.**
One objective function, three action spaces, three horizons: **PREVENT → PRESERVE → RECOVER**.

FoodOS forecasts perishable demand, scores every batch by remaining shelf life, and then *decides* —
how much to produce, what to preserve, and where to route stock that is going to be lost anyway.
Every recommendation carries the numbers behind it: kg saved, ₹ saved, CO₂e avoided, and the
attribution that explains *why*.

---

## 1. The problem

Food businesses lose money in three distinct ways, and they treat all three as one vague "wastage" line:

| Loss | Root cause | Correct intervention |
|---|---|---|
| Over-production | Forecast error, no cost asymmetry model | **PREVENT** — produce the right quantity |
| Spoilage in storage | Shelf life ignored until it's zero | **PRESERVE** — act while the batch still has life |
| Unsold saleable stock | No channel to move it in time | **RECOVER** — route it to the best remaining channel |

Existing tools report waste *after* it happens. FoodOS acts *before* it does, and puts a rupee figure
and a CO₂e figure on every action so the trade-off is explicit rather than moral.

---

## 2. The core idea — one objective function

Everything in this system optimises the same value function `V(a)` over an action `a`.

```
V(a) = margin(a) − holding(a) − disposal(a) − λ · sustainability(a)

sustainability(a) = co2e_price · co2e(a) + waste_externality · kg_food(a)
```

The **PREVENT** horizon reduces to a newsvendor with the sustainability term:

```
q*  = Cu / (Cu + Co + λ · sustainability_per_unit)
Q*  = forecast.quantile(q*)
```

- `Cu` — cost of under-producing (lost contribution margin)
- `Co` — cost of over-producing (ingredient cost + labour + disposal cost)
- `λ`  — the sustainability weight, `0 → 1`, exposed as a live UI slider

`λ = 0` is a pure-profit plan. `λ = 1` prices the full cost of wasted food. **Moving the slider
must change the plan** — that is the demo's central interaction, and it is the proof that the
objective is real and not decorative.

**Why two terms and not carbon alone.** At any defensible carbon price, carbon is rounding error
next to an Indian restaurant's contribution margin — priced honestly it would not move the plan at
all, and a slider that does nothing is worse than no slider. The externality term is the rest of the
damage: land, water, nutrient loss, landfill methane. It is set at roughly a quarter of the FAO
full-cost-accounting figure, so the argument runs from a conservative number rather than a
flattering one. Both constants live in [costs.yaml](backend/foodos/content/costs.yaml) under
`lambda_price`, with the reasoning in the file.

Dish-level quantities are exploded through the recipe BOM into ingredient quantities using standard
culinary yields (`content/yield_table.yaml`), so a plan in dishes becomes a purchase list in kilograms.

> **Architectural hard rule:** there is exactly **one** `V(a)`, in `engine/optimiser.py`.
> Track 1 (kitchen), Track 2 (retail) and Track 3 (production) are three *action spaces* passed into
> the same optimiser — roughly 80 lines each, not three new modules. A second objective function
> anywhere in the codebase makes the platform claim fiction.

---

## 3. The three horizons

| Horizon | Question | Engine module | Output |
|---|---|---|---|
| **PREVENT** | How much should we make? | `engine/prevent.py` | Per-dish quantity `80 → 63`, with saving |
| **PRESERVE** | What is dying and what do we do today? | `engine/rescue.py` + RSL model | Batch ledger ranked by remaining shelf life |
| **RECOVER** | Where does the doomed stock go? | `engine/rescue.py` | Ranked channels with ₹ recovered each |

**Remaining Shelf Life (RSL)** is temperature-adjusted via a Q10 model over the storage zone's actual
temperature, with penalties for cut/processed product and ethylene exposure — not a naive
`expiry_date − today`.

**Feasibility gate before ranking.** In RECOVER, channels that fail eligibility (lead time exceeds
remaining shelf life, category not accepted, minimum quantity not met) are excluded *before* the
ranking, and are returned to the UI **with their exclusion reason attached**. Excluded options are
shown greyed out, never hidden — an operator who cannot see why an option vanished does not trust
the system again.

---

## 4. Agents — the LLM never computes a number

Four agents, all Claude (`claude-sonnet-5`) via the Anthropic SDK:

| Agent | Input (computed, structured) | Output (language only) |
|---|---|---|
| **Diagnostician** | Attribution facts | One-sentence root cause |
| **Planner** | Low-RSL stock + recipes | Menu / special draft |
| **Communicator** | Transfer details | B2B WhatsApp message |
| **Verifier** | Every agent output + the computed facts | Pass, or **block** on mismatch |

Every agent receives numbers as structured input and **may never produce one**. The Verifier
re-checks each output against the computed facts and blocks on mismatch, logging the failure.

This is enforced in code, not asserted on a slide. The model is shown fact *keys*, never fact
*values*, and replies with a template full of `{{tokens}}`; Python substitutes the computed numbers
after the model has finished writing. A digit in raw model output is rejected outright. The
mechanism, its three legs, and the tests behind each are documented in [docs/agents.md](docs/agents.md).

```bash
python -m foodos.agents.runner all --demo   # all three agents, no backend, no API key
python -m foodos.agents.demo                # the Verifier blocking, formatted for a screenshot
```

---

## 5. Repository structure

```
foodos/
├── backend/
│   ├── foodos/
│   │   ├── data/          # A — synthetic dataset generator
│   │   ├── models/        # A — forecaster, RSL, attribution, backtest
│   │   ├── schema/        # B — SQLAlchemy tables + Pydantic DTOs
│   │   ├── engine/        # B — optimiser, prevent, rescue, recommendation, simulator
│   │   ├── api/           # B — FastAPI routers
│   │   ├── ingest/        # B — CSV loader, column mapping, seed
│   │   ├── agents/        # D — Diagnostician, Planner, Communicator, Verifier
│   │   ├── content/       # D — recipes, yields, costs, shelf life, channels (YAML)
│   │   └── config.py      # B — λ, costs, paths
│   ├── tests/
│   │   ├── test_models/   # A
│   │   ├── test_engine/   # B
│   │   └── test_agents/   # D
│   ├── data/              # generated CSVs + foodos.db (GITIGNORED except data/sample/)
│   └── pyproject.toml     # B
│
├── frontend/              # C — entire folder, nobody else opens it
│   └── src/
│       ├── screens/       # Today, Why, Plan, Ledger, Rescue, Impact, Settings
│       ├── components/    # RecommendationCard, LambdaSlider, KpiRow, charts
│       ├── api/           # fetch wrappers + types
│       └── mocks/         # copied from contracts/mock at H3
│
├── contracts/             # B + C jointly, FROZEN AT H3
│   ├── api-contract.md    # every endpoint, request, response
│   └── mock/              # one .json per endpoint — C's fixtures
│
├── docs/                  # D — deck, demo script, copy
└── README.md
```

---

## 6. Setup

**Prerequisites, installed before hour 0:**

- Python **3.11.x**
- Node **20.x LTS**

### Backend

```bash
cd backend
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -e .
cp .env.example .env          # then add ANTHROPIC_API_KEY
```

### Frontend

```bash
cd frontend
npm install
```

---

## 7. The two commands that matter

**Rebuild the entire demo database from scratch:**

```bash
cd backend
python -m foodos.ingest.seed
```

This is sacred. It runs 50 times before the demo. It must always work, from a clean checkout, in one
command, with no manual steps. If it breaks, nothing else matters.

**Run the stack:**

```bash
# terminal 1
cd backend && uvicorn foodos.api.main:app --reload --port 8000

# terminal 2
cd frontend && npm run dev
```

- API: <http://localhost:8000> — interactive docs at `/docs`
- UI: <http://localhost:5173>

---

## 8. API

`contracts/api-contract.md` is the **single source of truth** and is **frozen at H3**. The backend
matches it byte for byte; the frontend builds against `contracts/mock/` until each endpoint is live.

Endpoint families:

| Area | Purpose |
|---|---|
| `/api/today` | 3 KPIs (kg at risk, ₹ at risk, % preventable) + ranked recommendations |
| `/api/why` | Attribution — contributors to today's risk, trim callout |
| `/api/plan?lambda=` | PREVENT plan: dish, current qty, recommended qty, Δ, saving |
| `/api/ledger` | Batch ledger: qty, RSL days, risk %, value at risk, action |
| `/api/rescue` | RECOVER: ranked channels + excluded channels with reasons |
| `/api/impact` | Backtest — actual vs forecast vs baseline, accuracy, acceptance rate |
| `/api/recommendations/{id}/accept` · `/override` | Recommendation lifecycle |
| `/api/simulate` | Savings simulator |
| `/api/tracks/retail` · `/api/tracks/production` | Track 2 + Track 3 action spaces |

`lambda` is a query parameter that flows from the URL → objective function → **every** response
that depends on it. A response computed at a given λ reports that λ back.

---

## 9. Tech stack — exact, nothing else

Adding a library that is not on this list requires sign-off from Person B with a one-sentence
justification.

### Backend

| Thing | Choice | Version |
|---|---|---|
| Language | Python | 3.11 |
| API | FastAPI + Uvicorn | 0.115 / 0.32 |
| DB | SQLite at `backend/data/foodos.db` | stdlib |
| ORM / models | SQLAlchemy 2.0 + Pydantic 2 | 2.0 / 2.9 |
| Dataframes | pandas + numpy | 2.2 / 1.26 |
| Forecasting | LightGBM quantile regression | 4.5 |
| Metrics | scikit-learn (metrics only) | 1.5 |
| LLM | Anthropic SDK, `claude-sonnet-5` | latest |
| Config | python-dotenv | 1.0 |
| Tests | pytest | 8.3 |
| Packaging | pip + venv | — |

**Not allowed:** Postgres, Docker, Alembic, Celery, Redis, PyTorch, TensorFlow, Prophet,
statsmodels, any training from scratch.

### Frontend

| Thing | Choice | Version |
|---|---|---|
| Build | Vite | 5.x |
| Framework | React + TypeScript | 18 / 5.6 |
| Styling | Tailwind CSS **v3** (not v4) | 3.4 |
| Routing | react-router-dom | 6.x |
| Data fetching | @tanstack/react-query | 5.x |
| Charts | Recharts | 2.x |
| Icons | lucide-react | latest |
| Packaging | npm | — |

**Not allowed:** Next.js, Redux, MUI, shadcn, Chakra, styled-components, Framer Motion, any CSS-in-JS.

---

## 10. Ownership

Four owners, non-overlapping folders. Nobody edits someone else's directory — you call their API or
you ask them.

| Person | Owns | Never touches |
|---|---|---|
| **A** — Models | `data/`, `models/`, `tests/test_models/` | engine, api, frontend, agents |
| **B** — Engine & API | `schema/`, `engine/`, `api/`, `ingest/`, `config.py`, `pyproject.toml`, `contracts/`, `README.md`, `tests/test_engine/` | models, data, agents, content, frontend |
| **C** — Frontend | the entire `frontend/` folder | anything under `backend/` |
| **D** — Agents, Content, Demo | `agents/`, `content/`, `docs/`, `tests/test_agents/` | models, engine, api, frontend |

### Git workflow

```
main                  <- always runnable, never broken
├── feat/a-models     <- Person A
├── feat/b-engine     <- Person B
├── feat/c-frontend   <- Person C
└── feat/d-agents     <- Person D
```

Merge to `main` only when `python -m foodos.ingest.seed` still succeeds and the demo path still runs.

---

## 11. Build timeline (36 hours)

| Hours | B — Engine & API | C — Frontend | D — Agents & Demo |
|---|---|---|---|
| H0–3 | Repo skeleton, schema, draft contract | Vite scaffold, tokens, app shell, co-author contract | Pathologies with A, deck skeleton |
| H3–8 | `ingest/` + `seed.py` | RecommendationCard, Today screen | All content YAML — recipes, yields, costs, shelf life, channels |
| H8–14 | `optimiser.py`, `prevent.py`, BOM explosion | Why + Plan screens | Agent prompts + UI copy → C |
| H14–20 | `rescue.py`, `recommendation.py`, `simulator.py`, λ plumbing | λ slider, Ledger, Rescue, Impact | Wire agents to B's API, capture Verifier blocking |
| H20–28 | All 11 endpoints live against the frozen contract | Swap mocks for real API, empty/loading/error states | Deck + demo script timed to 4:40 |
| H28–33 | Track 2 + Track 3 action spaces | Track stub screens, polish, print stylesheet | Rehearsals 1–3, record backup video |
| H33–36 | Freeze, reseed, demo-path bugs only | Freeze, walk the demo path ten times | Rehearsals 4–6, one run with wifi off |

**Contract freeze is H3.** After that, the frontend never waits on the backend — it builds on
`src/mocks/` and swaps endpoint by endpoint as they ship.

---

## 12. Tests

```bash
cd backend
pytest                      # everything
pytest tests/test_engine    # B
pytest tests/test_models    # A
pytest tests/test_agents    # D
```

The tests that must never go red:

1. `seed.py` rebuilds the database from a clean state.
2. Changing λ changes the plan.
3. An excluded rescue channel is returned with a reason, not dropped.
4. The Verifier blocks an agent output whose numbers disagree with the computed facts.

---

## 13. Non-negotiables

- **One `V(a)`.** Three action spaces, one objective function.
- **The LLM never computes a number.** Enforced by the Verifier, in code.
- **`python -m foodos.ingest.seed` always works.** One command, clean checkout, no manual steps.
- **Excluded options are shown with their reason.** Never silently hidden.
- **No blank screens.** Every screen has an empty, loading and error state — a blank screen mid-demo
  reads as a crash.
