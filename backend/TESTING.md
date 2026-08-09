# Testing the backend — Person A (data & models)

How to prove this half of FoodOS works, on any machine, from a clean clone.

Everything below runs from the `backend/` folder. On Windows use
`.\venv\Scripts\python.exe`; on Mac/Linux use `venv/bin/python`. The examples
use the Windows form.

---

## 0. One-time setup

Python **3.10** (not 3.11 — 3.10 is what the pinned versions have wheels for).

```powershell
cd backend
py -3.10 -m venv venv
.\venv\Scripts\python.exe -m pip install --upgrade pip
.\venv\Scripts\python.exe -m pip install numpy==1.26.4 pandas==2.2.3 lightgbm==4.5.0 scikit-learn==1.5.2 pytest==8.3.3
```

Check it took:

```powershell
.\venv\Scripts\python.exe -c "import numpy, pandas, lightgbm, sklearn; print('ok')"
```

`venv/` is gitignored, so every person creates their own. It is ~313 MB and
must never be committed.

---

## 1. The single command that answers the question

```powershell
.\venv\Scripts\python.exe -m foodos.verify
```

This rebuilds the dataset from scratch, runs every model over it, and checks
that all three planted faults are rediscovered. It ends with:

```text
  14/14 checks passed
```

and exits with code `0`. **If you see 14/14 and exit code 0, the backend works.**
Anything less prints `FAIL` next to the specific check that broke.

Check the exit code explicitly:

```powershell
.\venv\Scripts\python.exe -m foodos.verify; echo "exit=$LASTEXITCODE"
```

`exit=0` is a pass. Any other value is a failure, so this is safe to wire into
a git hook or a CI step.

---

## 2. The test suite

```powershell
.\venv\Scripts\python.exe -m pytest tests/ -q
```

Expected: **22 passed** in roughly 30 seconds.

To see what each test actually asserts:

```powershell
.\venv\Scripts\python.exe -m pytest tests/ -v
```

To run one group while debugging:

```powershell
# the three planted faults — 6 tests, ~2 s
.\venv\Scripts\python.exe -m pytest tests/ -v -k "fault_1 or fault_2 or fault_3"

# forecaster and backtest — 4 tests, ~30 s (these are the slow ones)
.\venv\Scripts\python.exe -m pytest tests/ -v -k "forecast or backtest or lambda"

# shelf-life engine — 2 tests, ~2 s
.\venv\Scripts\python.exe -m pytest tests/ -v -k "rsl"
```

Note `-k "fault"` on its own selects **all** 22 tests, because the filename
`test_planted_faults.py` contains the word. Use the three-way form above.

---

## 3. Running each piece on its own

Each module prints a human-readable report when run directly. Use these when a
`verify` check fails and you need to see what the module actually produced.

| Command | What it shows |
| --- | --- |
| `python -m foodos.data.generate` | Rebuilds the 11 CSVs, prints the waste summary and the three planted faults |
| `python -m foodos.models.attribution` | Where the waste is, split five ways, plus the yield gaps |
| `python -m foodos.models.rsl` | The Food Life Ledger — every open batch, true life vs printed date |
| `python -m foodos.models.forecast` | Trains, scores against seasonal naive, prints tomorrow's demand range |
| `python -m foodos.models.backtest` | The proof number: measured savings on 30 unseen days |

(Prefix each with `.\venv\Scripts\python.exe -m` …)

---

## 4. What the numbers should look like

The generator is seeded, so these are **exact**, not approximate. If yours
differ, something has changed.

### `foodos.data.generate`

```text
  revenue          Rs    9,066,353
  purchases        Rs    3,129,832   (food cost 34.2% of revenue)
  waste            Rs      189,560   2,096 kg   (6.1% of purchases)
  per month        Rs       63,187   699 kg

    overproduction      52.9%
    prep_trim           18.5%
    spoilage            15.4%
    plate_waste          9.0%
    quality_rejection    4.1%

  fruit & veg share of wasted weight   60.2%
```

Sanity: food cost should sit in the high 20s to mid 30s percent of revenue, and
waste should be 4–10% of purchases. Outside those ranges the restaurant has
stopped being believable and a judge who knows food service will notice.

### The three planted faults

```text
  1. Chicken Biryani over-produced 36.2% on Fri vs 20.6% overall
  2. Cauliflower yield 0.512 against a 0.58 standard — 268.4 kg (Rs 10,735) avoidable
  3. Batch B01674: 23.4 kg spinach, label says 4 days left, really has 0.81
     — overstated by 3.2 days
```

These are the demo. If any one of them stops being detected, stop and fix it
before doing anything else — a system that no longer finds the fault you planted
has nothing to show on stage.

### `foodos.models.backtest`

```text
  forecast   pinball 2.689 vs seasonal-naive 4.110  (+34.6%)   10-90 coverage 89%
  decision   over-production 2109 -> 1016 portions (52% cut)
  measured   Rs 33,055 and 373 kg saved per month
```

Three things to check here:

- **Beats seasonal naive.** If the improvement goes negative, the forecaster is
  worse than "same as last Friday" and must not be allowed to set a quantity.
- **Coverage near 80%.** The 10–90 band should contain about 80% of actuals.
  Much below and the confidence range is decoration; much above and it is so
  wide it says nothing. 72–95% is the accepted window.
- **Savings positive.** Both rupees and kilos.

### The λ dial

```text
      lambda    Rs / month   kg / month
           0        33,055          373
          50        32,456          444
         150        19,206          523
```

Kilos must rise and rupees must eventually fall. If both rise, λ has leaked into
the thing being measured and the slider is manufacturing money — see the comment
in `backtest.run_backtest`.

---

## 5. The determinism check

Same seed, same bytes. Re-running the generator must not change a single
committed file:

```powershell
.\venv\Scripts\python.exe -m foodos.data.generate
cd ..
git status --porcelain backend/data/sample/
```

**Expected: no output at all.** If git reports changes, something in the
simulation has become non-deterministic and every number in the demo has just
become unreproducible. The usual cause is a new random draw added to the wrong
RNG stream — the generator deliberately uses three separate ones
(`rng_ctx`, `rng`, `rng_inv`) so that changing an inventory parameter cannot
alter demand.

---

## 6. Looking at the data by hand

The 11 CSVs in `data/sample/` open in Excel. The ones worth eyeballing:

| File | Look for |
| --- | --- |
| `open_batches.csv` | Sort by `rsl_days` ascending — this is the Ledger screen |
| `waste.csv` | Filter `reason` to see each cause separately |
| `production.csv` + `sales.csv` | `actual_qty` vs `qty` is the over-production gap |
| `goods_receipt.csv` | Filter `dock_dwell_hours > 2` to find the excursion batch |

Or from Python:

```powershell
.\venv\Scripts\python.exe -c "from foodos.models import loader; t = loader.load_all(); print(t['waste'].groupby('reason')['value'].sum())"
```

---

## 7. When something fails

| Symptom | Cause and fix |
| --- | --- |
| `ModuleNotFoundError: No module named 'foodos'` | You are not in `backend/`. `cd backend` first. |
| `FileNotFoundError: ...data/sample/... is missing` | Run `python -m foodos.data.generate` first. |
| `ValueError: 'product_id' is both an index level and a column label` | A merge against `tables["products"]`, which is indexed by `product_id`. Add `.reset_index(drop=True)` to the slice. |
| Yield detector reports an implausible yield (e.g. 0.12) | Some ingredient is being consumed without a recipe behind it, so gross usage has no net to compare against. Every kilo drawn from stock needs a BOM line — that is why the sides are modelled as a dish. |
| `assert 0.0 > 0` in the RSL test | The category under test has too short a shelf life to survive the test window. Use a longer-life category or a shorter horizon. |
| Tests pass but `verify` fails | `verify` regenerates the data first; the tests run against whatever is on disk. Regenerate, then re-run both. |
| Mass-balance test fails | Something is consuming or wasting stock that was never received. Check the consume loop in `generate.py` — burial must reorder the pick, never skip a batch. |

---

## 8. What Person B should call

These five signatures are frozen. Everything else in `foodos/models/` is
internal and may change.

```python
from foodos.models import (
    attribute,           # (site_id, start, end)          -> dict
    train,               # (sales_df, context_df)         -> model_run_id
    predict_quantiles,   # (site_id, product_id, date)    -> {q10..q90, expected}
    compute_rsl,         # (batch, zone_temp_c, profile)  -> days
    run_backtest,        # (site_id)                      -> dict
)
```

Quick smoke test that the contract holds:

```powershell
.\venv\Scripts\python.exe -c "from foodos.models import predict_quantiles as p; print(p(product_id='DSH_CHBIRYANI'))"
```

One note: `backtest.py` carries its own copy of the newsvendor so the forecaster
could be evaluated before the engine existed. At integration that should be
deleted and replaced with a call into `engine/prevent.py`. Two objective
functions in one codebase is the failure mode the build plan warns about.
