# A ↔ D: two sources of commodity constants, reconciled

**Raised by D at the A/D merge. Owner of the decision: A, with D.
Deadline: the H8 gate.**

When `feat/a-intelligence` and `feat/d-telemetry` met, the repo had **two sets of tomato
biophysical constants** written independently:

| | A | D |
| --- | --- | --- |
| File | `backend/foodos/agri/commodity.py` | `backend/foodos/content/commodities.yaml` |
| Form | frozen dataclass, Arrhenius | YAML, Q10 |
| Owner per §1 | A owns `models/`, `agents/`, `cv/`, `data/` | D owns `content/` |
| Owner per Contract 3 | — | **D**, for `base_shelf_life_hours`, `ref_temp_c`, `q10`, `respiration_rate`, `q_crit`, `nabcons_*` |

Ruling 1 is explicit: *"If your task tempts you to write a second decay model, a second
objective function, or a second recommendation shape — stop and message the owner
instead. The platform claim in the pitch is false the moment there are two of anything."*

This document is that message. Nothing has been deleted from A's folder.

---

## 1. What already agrees — now pinned by tests

These are asserted in `tests/test_external/test_content_pack.py` and will fail the build
if either side drifts.

| Thing | A | D | |
| --- | --- | --- | --- |
| NABCONS farm loss | 8.37% | 8.37% | ✅ |
| NABCONS market loss | 3.25% | 3.25% | ✅ |
| Maturity stage names | `mature_green · breaker · turning · pink · light_red · red` | identical | ✅ *(D renamed `red_ripe` → `red` at the merge)* |
| Maturity ordering | monotone, green longest | identical | ✅ |
| Chilling threshold sits above 0 °C and below the reference temp | 12.5 °C | 10.0 °C | ✅ both, though see §3 |

---

## 2. What disagreed and has been resolved — D deferred to A

Two tables were duplicated outright. **D removed its copies**, because A owns the
model's coefficients and neither was on Contract 3's list of what D supplies.

### `maturity_factors` — removed from `commodities.yaml`

Life multiplier by ripening stage. Both files had one, from different sources.

| Stage | A (USDA Handbook 66) | D (removed) | gap |
| --- | --- | --- | --- |
| mature_green | 1.75 | 1.35 | 30% |
| breaker | 1.30 | 1.10 | 18% |
| turning | 1.00 | 0.95 | 5% |
| pink | 0.78 | 0.85 | 9% |
| **light_red** | **0.58** | **0.78** | **34%** |
| red | 0.42 | 0.60 | 43% |

`light_red` is T1024's maturity, so this one was live on the demo path — a 34% swing in
remaining life from which file you happened to read. **A's table stands.** D keeps only
the stage *names* (the questionnaire has to offer them) and the display-band mapping.

### `damage_factors` — reframed, not duplicated

D's table was life multipliers, competing with A's single
`Commodity.damage_life_penalty = 1.30`. It is now `damage_level_index` on 0–1 —
**what the human's answer means as a number**, which A multiplies by its own penalty.

| Answer | index |
| --- | --- |
| Clean lot | 0.00 |
| A few marked fruit | 0.15 |
| Bruising in most crates | 0.40 |
| Crushing or rot starting | 0.75 |

The split is the point: D owns what *"bruising in most crates"* means, A owns what that
does to shelf life. A judge can audit the two halves separately, and neither owner can
silently overwrite the other.

---

## 3. What is still open — the H8 decision

**The base kinetics differ, and only A can close it**, because A's model is the one that
runs and D's file is the one Contract 3 says A should be reading.

| | A | D |
| --- | --- | --- |
| Reference temperature | 20.0 °C | 13.0 °C |
| Reference life | 8.0 days (192 h) | 264 h (11 d) |
| Kinetics | Arrhenius, Ea = 70 kJ/mol | Q10 = 2.2, flat |
| Chilling threshold | 12.5 °C | 10.0 °C |
| Quality floor | `critical_spoilage_fraction` 0.10 | `q_crit` 45 (quality score) |

Both cite real sources. A's 8 d at 20 °C is USDA Handbook 66; D's 11 d at 13 °C is the UC
Davis optimum-storage figure. **They are not the same claim**, and converting one to the
other is where they part company.

### The size of the gap, at the reference maturity

```
  temp        A        D     A/D
  13 °C     388 h    264 h   1.47x     <- cold storage. Not modelled in the MVP.
  20 °C     192 h    152 h   1.26x
  25 °C     119 h    102 h   1.16x
  30 °C      74 h     69 h   1.08x
  34 °C      52 h     50 h   1.03x     <- what T1024 actually travels at.
```

**This is the good news and it is why this is an H8 item rather than a fire.** The two
formulations converge as it gets hotter, and at the pulp temperature of an open truck on
the Kolar–Delhi corridor in August they agree within 3%. The divergence lives at
cold-storage temperatures, and there is no cold chain at Kolar — that absence is the
premise of the product. **No demo figure moves either way.**

The implied Q10 also differs, and differs *with temperature*, because Arrhenius and Q10
are the same physics only locally:

| at | A's implied Q10 | D's flat Q10 |
| --- | --- | --- |
| 13 °C | 2.70 | 2.20 |
| 20 °C | 2.58 | 2.20 |
| 30 °C | 2.43 | 2.20 |

A's temperature-varying Q10 is the more correct formulation. D's flat 2.2 is the form
`ingest/shelf_life.py` already uses for the kitchen node, which is why it was written
that way — the same physics the existing engine runs, restated in hours.

### The three options, with D's recommendation

1. **A reads D's constants** (`ref_temp_c`, `base_shelf_life_hours`, `q10`) and derives
   `Ea` from `q10`. Matches Contract 3 literally. Costs A a refit, since the calibrated
   scalars in `calibrate.py` were solved against the current kinetics.
2. **D restates its constants in A's reference frame** — `ref_temp_c: 20.0`,
   `base_shelf_life_hours: 192`, and an `ea_j_per_mol` beside the `q10` — so the YAML
   becomes the single source and A reads it without changing formulation. Cheapest for A,
   and D's UC Davis figure survives as a comment rather than as a competing number.
3. **Leave both and document it.** What this file does today. Acceptable only until H8.

**D recommends option 2.** It honours Contract 3 (the constants live in content, where a
judge can read them beside their citations), it does not force A to refit at H8, and it
keeps A's better temperature-varying kinetics. D will make the change on A's word — it is
D's file, but it is A's model, and D is not going to move a number under a running
calibration without being asked.

---

## 4. One thing to fix regardless of which option wins

`agri/commodity.py::NabconsBaseline.combined_pct` returns `farm + market = 11.62`.

Farm operations and market level are **consecutive stages of one chain, not addends.**
Adding them is exactly how the widely quoted "30–40% of Indian produce is wasted" figure
gets built, and a judge who knows the sector will go straight at it. `commodities.yaml`
carries an explicit `nabcons_note` warning against it, and `demo-script.md` has the
rebuttal prepared.

The property is currently unused. **Suggest removing it, or renaming it to something that
cannot be quoted as a headline** — `farm_plus_market_do_not_quote` would do. A one-line
change that closes off the single most likely way this demo loses credibility on stage.

---

## 5. Vocabulary joins made at the merge, for the record

Three enums now describe overlapping things. D's content was aligned to them; none of
A's or B's code was touched.

| Concept | Authority | D's content now |
| --- | --- | --- |
| Packaging | `schema/enums.py::PackagingType` — persisted on `ShipmentJourney` | keys renamed to `loose`, `jute_sack`, `ventilated_plastic_crate`, `cfb_carton` |
| Transport | `schema/enums.py::TransportMode` | already matched |
| Maturity, physical | `agri/commodity.py::MaturityStage` — six USDA stages | `red_ripe` renamed to `red` |
| Maturity, displayed | `schema/enums.py::MaturityStage` — `low`/`medium`/`high` | new `maturity_display_band` maps the six onto the three |

Two enums share the name `MaturityStage` in different modules. That is confusing and
worth renaming one day; today the join lives in exactly one place
(`commodities.yaml::maturity_display_band`) rather than being spelled three ways across
three call sites.

### There is a third packaging vocabulary, and it is A's

`agri/scenario.py::Packaging` — the labels A's synthetic generator trains on — is a
different set again, and its reefer is spelled `refrigerated`:

| | A `agri/scenario.py` | B `schema/enums.py` | D content |
| --- | --- | --- | --- |
| loose | `loose_bulk` | `loose` | `loose` |
| sack | `gunny_bag` | `jute_sack` | `jute_sack` |
| plastic crate | `ventilated_plastic_crate` | `ventilated_plastic_crate` | ✅ same |
| wooden crate | `wooden_crate` | **absent** | parked in `pending_enum` |
| carton | **absent** | `cfb_carton` | `cfb_carton` |
| reefer | `refrigerated` | `reefer` | `reefer` |

The questionnaire writes B's spelling, because that is what the database stores and what
Contract 2 returns. A's model was trained on A's labels. **Something has to join them**,
and the join belongs in content rather than in whichever call site B writes first — so
every entry in `packaging.yaml` and `transport_modes.yaml` now carries an
`agri_scenario_key`, asserted against A's enums by
`test_the_content_pack_joins_B_s_persisted_names_onto_A_s_generator_names`.

Two gaps the join cannot close, and does not pretend to:

- **`cfb_carton` maps to `null`.** A's generator has no carton class. A batch in cartons
  still scores; its packaging feature degrades to the defaults rather than being mapped
  onto a class it is not. Mapping it to `ventilated_plastic_crate` because both are
  rigid would be an invented number wearing a real label.
- **`wooden_crate` is the mirror image** — A has the class, B has no enum member, so it
  is not offered. One enum member on B's side closes the loop and the constants are
  already written.

The cheapest permanent fix is for A's generator and B's schema to share one spelling.
Until they do, this table is the only place the mismatch is written down, and it fails
the build if either side moves.

**Open request to B:** `PackagingType` has no `wooden_crate`, which is a common pack on
this corridor. Its constants are parked under `pending_enum` in `packaging.yaml` and are
not offered in the questionnaire, because a batch that cannot be saved is worse than a
pack we do not offer. One enum member and the block moves up unchanged.
