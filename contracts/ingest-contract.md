# Ingest contract — A → B

**Owner of this document: B.** A drops CSVs into `data/`; `python -m foodos.ingest.seed`
picks them up. Every file is optional — the loader ingests what is present and reports
what was missing, so a partial drop still produces a working database.

Column names are matched case- and punctuation-insensitively through
`foodos/ingest/mapping.py`, so `Business Date`, `business_date` and `date` all resolve.
**Unmapped columns are reported, never silently dropped** — a column the wizard did not
understand is the most common cause of a wrong number downstream.

## Files

### `shelf_life_profiles.csv`
| column | type | notes |
| --- | --- | --- |
| `category` | text | primary key, referenced by `products.shelf_life_category` |
| `base_shelf_life_days` | float | at the reference temperature |
| `ref_temp_c` | float | temperature the base life is quoted at |
| `q10` | float | 2–3 for fresh produce |
| `cut_life_factor` | float | ~0.35 once cut |
| `ethylene_sensitive` | bool | leafy greens |
| `ethylene_emitter` | bool | tomato, banana, apple |

### `products.csv`
`sku`, `name`, `category`, `uom`, `unit_cost`, `unit_price`, `unit_weight_kg`,
`is_dish`, `shelf_life_category`

`unit_weight_kg` is the portion or pack weight and is how a quantity in portions
becomes a quantity in kilograms. **`category` drives the produce share** — use
`vegetable`, `fruit` or `leafy_green` for anything that should count as fruit and veg.

### `recipes.csv`
`dish_sku`, `ingredient_sku`, `qty`, `uom`, `standard_yield_pct`

`qty` is per portion. `standard_yield_pct` is the culinary standard (cauliflower 0.58,
tomato 0.91, coriander 0.60) — the trim detector compares actual yield against it, so
**a wrong value here silently invents or hides avoidable waste.**

### `storage_zones.csv`
`site`, `name`, `mean_temp_c`, `temp_source`

`temp_source` ∈ `declared` | `logged` | `simulated`. All three are digital inputs.
No physical sensor is involved anywhere in this system.

### `batches.csv`
`site`, `sku`, `lot_code`, `received_at`, `printed_expiry`, `qty_received`,
`qty_remaining`, `uom`, `storage_zone`, `intake_grade`, `state`, `unit_cost`,
`excursion_hours`, `excursion_temp_c`

`state` ∈ `whole` | `cut` | `prepared`. `intake_grade` is 0–1.
The two `excursion_*` columns record a temperature excursion — this is where the
"4 hours on the dock at 31 °C" story enters the data.

### `sales.csv`
`business_date`, `site`, `sku`, `qty`, `revenue`, `channel`

Note this is **censored demand**: a POS records what was sold, which is capped at what
was prepared. The forecaster should account for that; the seasonal-naive fallback does not.

### `production.csv`
`business_date`, `site`, `sku`, `planned_qty`, `actual_qty`, `uom`

`actual_qty` is the baseline every PREVENT recommendation is scored against, so it must
be what the site *decided in advance*, never something derived from that day's sales.

### `waste.csv`
`business_date`, `site`, `sku`, `qty`, `uom`, `value`, `reason`, `stage`,
`capture_method`, `note`

`reason` ∈ `overproduction` | `prep_trim` | `spoilage` | `plate_waste` | `quality_rejection`
`stage` ∈ `storage` | `prep` | `production` | `service` | `post_service`

**A owns the reason codes.** B aggregates them; B does not infer them.

### `demand_context.csv`
`business_date`, `site`, `is_holiday`, `festival`, `weather_code`, `temp_max_c`,
`promo_flag`, `covers`

### `channels.csv`
`type`, `name`, `contact`, `distance_km`, `lead_time_hours`, `min_qty`, `max_qty`,
`accepted_categories`, `price_factor`, `fixed_cost`, `cost_per_km`,
`social_value_per_kg`, `eligibility_rules`

`type` ∈ `internal_use` | `staff_meal` | `markdown` | `b2b_transfer` | `donation` |
`processing` | `animal_feed` | `compost`

`accepted_categories` is either a JSON array or a `|`-separated list.
`eligibility_rules` is JSON, e.g. `{"min_rsl_days": 1.0, "min_intake_grade": 0.75}`.

## Tables A writes directly (no CSV)

B ships deterministic fallbacks for these so nothing is ever blocked. A replaces them
by writing rows; neither side imports the other's modules.

| Table | B's fallback | A replaces with |
| --- | --- | --- |
| `forecast` | Empirical quantiles by (product, day-of-week) — the seasonal-naive baseline | LightGBM quantile regression |
| `batch.rsl_days` + `rsl_explanation` | Deterministic Q10 kinetics in `ingest/shelf_life.py` | Kinetic model + learned residual |
| `model_run` | not written | One row per training run, with `metrics_json` |

`forecast` needs `site_id`, `product_id`, `target_date`, `q10`, `q25`, `q50`, `q66`,
`q75`, `q90`, `expected`. The engine reads a stored `Forecast` in preference to its own
fallback, so **the moment A writes rows the engine starts using them** — no code change,
no coordination.

`rsl_explanation` is shown verbatim in the UI. Write a sentence a chef would accept,
not a model dump.
