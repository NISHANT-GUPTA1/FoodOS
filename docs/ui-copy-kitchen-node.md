# UI copy

> **This is the kitchen node's UI copy, from the v1 team split.** It is not superseded and
> not deleted: `FoodOS-Team-Split-v2.md` Ruling 2 keeps the seven kitchen screens as the
> platform proof, shown for about twenty seconds. C still renders them and still needs these
> strings. The farm-gate batch product's UI copy is in [`ui-copy.md`](ui-copy.md).

**Owner:** Person D. **Consumer:** Person C.
**Rule:** every string a user can see is in this file. If a screen needs a sentence that is
not here, ask for it rather than writing it — copy written at 3 a.m. is how a demo starts
sounding like a student project.

Placeholders in `{{braces}}` are filled by the frontend from the API response. They are the
same convention the agents use, for the same reason: the words are authored, the numbers
are computed.

---

## Voice

Working English, in the kitchen's own vocabulary. Cover, service, prep, mise, chiller,
outlet, station, batch.

- **Say what to do, not what happened.** "Cut Gobi Manchurian to 63" beats "Gobi Manchurian
  is over-produced."
- **Never moralise.** No "help save the planet", no "reduce your footprint". The operator is
  running a business at a thin margin. Carbon is a cost line, and we treat it like one.
- **Never apologise for the software.** "Not enough data yet" — not "Sorry! We couldn't find
  anything :("
- **Numbers carry their unit and never their own adjective.** "9.6 kg", never "a hefty 9.6 kg".
- **Never say "AI".** Say what it did: "checked against the computed figures".

---

## Global

| Key | Copy |
|---|---|
| `app.name` | FoodOS |
| `app.tagline` | Decide before it spoils |
| `nav.today` | Today |
| `nav.why` | Why |
| `nav.plan` | Plan |
| `nav.ledger` | Ledger |
| `nav.rescue` | Rescue |
| `nav.impact` | Impact |
| `nav.settings` | Settings |
| `horizon.prevent` | Prevent |
| `horizon.preserve` | Preserve |
| `horizon.recover` | Recover |
| `horizon.prevent.tooltip` | Make the right amount in the first place |
| `horizon.preserve.tooltip` | Buy shelf life on stock you already have |
| `horizon.recover.tooltip` | Move what cannot be saved to its best remaining home |
| `error.generic.title` | Could not load this screen |
| `error.generic.body` | The backend did not answer. Nothing has been changed. |
| `error.generic.action` | Try again |
| `loading.generic` | Working it out… |
| `offline.banner` | Showing the last figures received. Not live. |

---

## RecommendationCard

The one component every screen reuses.

| Key | Copy |
|---|---|
| `card.why.label` | Why |
| `card.saves.label` | Saves |
| `card.confidence.label` | Confidence |
| `card.expires.label` | Act by |
| `card.expires.value` | {{expires_in}} left |
| `card.expires.urgent` | Act within the hour |
| `card.accept` | Accept |
| `card.override` | Override |
| `card.accepted` | Accepted |
| `card.overridden` | Overridden |
| `card.accepted.toast` | Accepted. It is on the prep sheet. |
| `card.overridden.toast` | Overridden. We have logged the reason. |
| `card.quantity.change` | {{old_qty}} → {{new_qty}} |
| `card.verified` | Checked against the computed figures |
| `card.unverified` | Explanation withheld — figures unaffected |

**Override reasons** (the picker, in this order — the first three cover most real overrides):

1. Demand will be higher than the forecast
2. A booking or event is not in the system
3. Ingredient will not keep until tomorrow anyway
4. Cannot execute this at the station today
5. I disagree with the recommendation
6. Other

> Override copy matters more than it looks. An override is not a failure — it is the
> operator telling us something the model does not know, and the acceptance rate on the
> Impact screen is only meaningful if overriding feels legitimate.

---

## Today

| Key | Copy |
|---|---|
| `today.title` | Today |
| `today.subtitle` | {{date}} · {{outlet_name}} |
| `today.kpi.kg.label` | At risk today |
| `today.kpi.kg.unit` | kg |
| `today.kpi.value.label` | Value at risk |
| `today.kpi.preventable.label` | Preventable |
| `today.kpi.preventable.hint` | Share that a different decision this morning would have avoided |
| `today.list.title` | What to do now |
| `today.list.subtitle` | Ranked by what each action is worth |
| `today.empty.title` | Nothing at risk today |
| `today.empty.body` | Every batch has enough life left and today's plan matches the forecast. Check back after the evening count. |
| `today.error.title` | Could not load today's actions |

---

## Why

| Key | Copy |
|---|---|
| `why.title` | Why |
| `why.subtitle` | What put {{value_at_risk}} at risk today |
| `why.chart.title` | Contributors |
| `why.chart.hint` | Each bar is a share of today's value at risk, not a share of waste |
| `why.rootcause.label` | Root cause |
| `why.trim.title` | Trim loss |
| `why.trim.body` | {{trim_kg}} of today's risk never reached a plate — it was lost at prep. {{worst_ingredient}} is the largest single source. |
| `why.top.label` | Largest contributor |
| `why.empty.title` | Not enough history yet |
| `why.empty.body` | Attribution needs at least a fortnight of production and sales. Come back once the ledger has filled in. |

---

## Plan

| Key | Copy |
|---|---|
| `plan.title` | Plan |
| `plan.subtitle` | Tomorrow's production, priced against waste |
| `plan.lambda.label` | Sustainability weight |
| `plan.lambda.min` | Profit only |
| `plan.lambda.max` | Waste priced in full |
| `plan.lambda.hint` | Prices the full cost of wasted food — carbon, land, water, disposal — into every quantity below |
| `plan.table.dish` | Dish |
| `plan.table.current` | Planned |
| `plan.table.recommended` | Recommended |
| `plan.table.delta` | Change |
| `plan.table.saving` | Saving |
| `plan.totals.label` | Across the menu |
| `plan.totals.portions` | {{portions}} fewer portions |
| `plan.totals.kg` | {{kg}} less input |
| `plan.totals.value` | {{value}} kept |
| `plan.totals.co2e` | {{co2e}} avoided |
| `plan.unchanged` | No change |
| `plan.empty.title` | No plan for tomorrow yet |
| `plan.empty.body` | The forecast runs after the evening close. This screen fills in once it has. |
| `plan.accept.all` | Accept the whole plan |
| `plan.accept.all.confirm` | This replaces tomorrow's prep sheet. The kitchen sees it immediately. |

---

## Ledger

| Key | Copy |
|---|---|
| `ledger.title` | Ledger |
| `ledger.subtitle` | Every open batch, by how long it has left |
| `ledger.table.batch` | Batch |
| `ledger.table.item` | Item |
| `ledger.table.qty` | Quantity |
| `ledger.table.rsl` | Life left |
| `ledger.table.risk` | Risk |
| `ledger.table.value` | At risk |
| `ledger.table.action` | Do this |
| `ledger.rsl.critical` | Today |
| `ledger.rsl.warning` | {{days}} left |
| `ledger.rsl.fine` | {{days}} left |
| `ledger.zone.warm` | {{zone_name}} is running warm |
| `ledger.zone.warm.tooltip` | This zone has been above its set point, so these batches are ageing faster than their labels say |
| `ledger.empty.title` | Nothing open |
| `ledger.empty.body` | Every batch has been consumed or closed off. |
| `ledger.filter.all` | All |
| `ledger.filter.critical` | Needs action today |

---

## Rescue

| Key | Copy |
|---|---|
| `rescue.title` | Rescue |
| `rescue.subtitle` | {{item_name}} · {{qty}} · {{rsl}} left |
| `rescue.options.title` | Where it can go |
| `rescue.options.subtitle` | Ranked by what comes back, after commission and transport |
| `rescue.excluded.title` | Not available for this batch |
| `rescue.excluded.hint` | Shown so you can see what was ruled out and why |
| `rescue.option.value` | {{value}} back |
| `rescue.option.baseline` | Disposal · {{value}} |
| `rescue.option.vs_baseline` | {{delta}} better than binning it |
| `rescue.option.lead` | Needs {{lead_time}} |
| `rescue.option.capacity` | Capped at {{max_qty}} |
| `rescue.message.title` | Message to send |
| `rescue.message.copy` | Copy message |
| `rescue.message.copied` | Copied |
| `rescue.message.withheld` | The message could not be checked against the figures, so it was not drafted. The transfer is still the right call — send it yourself. |
| `rescue.empty.title` | Nothing needs rescuing |
| `rescue.empty.body` | No batch is close enough to the end of its life to be worth moving. |

**Exclusion reasons** — these come from the API (`exclusion_reason`), and match
`content/channels.yaml`. Render them verbatim:

| Code | Copy |
|---|---|
| `lead_time_exceeds_rsl` | Not enough shelf life left to reach this channel in time |
| `state_not_accepted` | This channel does not accept stock in this state |
| `category_not_accepted` | This channel does not accept this product category |
| `below_min_qty` | Below this channel's minimum pickup quantity |
| `above_max_qty` | Above what this channel can absorb today |
| `day_unavailable` | This channel does not operate today |
| `past_cutoff` | Past today's cutoff time for this channel |
| `missing_requirement` | A required condition is not met |
| `cold_chain_unavailable` | No cold chain available for the transfer |
| `licence_restriction` | Food safety rules do not permit this route for this stock |

---

## Impact

| Key | Copy |
|---|---|
| `impact.title` | Impact |
| `impact.subtitle` | What the system has been worth, measured on days it did not see |
| `impact.chart.title` | Forecast against what actually happened |
| `impact.chart.actual` | Actual |
| `impact.chart.forecast` | Forecast |
| `impact.chart.baseline` | Last week, same day |
| `impact.chart.heldout` | Held-out days |
| `impact.chart.hint` | Shaded days were never used to fit the model |
| `impact.accuracy.label` | Forecast error |
| `impact.accuracy.hint` | Mean absolute error, held-out days only |
| `impact.baseline.label` | Against the naive plan |
| `impact.acceptance.label` | Recommendations accepted |
| `impact.acceptance.hint` | Of {{total}} recommendations shown |
| `impact.savings.label` | Kept so far |
| `impact.empty.title` | Not enough history to measure yet |
| `impact.empty.body` | Impact needs held-out days to be honest. This fills in after the first full week. |

---

## Settings

| Key | Copy |
|---|---|
| `settings.title` | Settings |
| `settings.lambda.title` | Sustainability weight |
| `settings.lambda.body` | Sets the default for the Plan screen. Prices carbon and the wider cost of wasted food into every production quantity. |
| `settings.costs.title` | Costs and prices |
| `settings.costs.body` | Ingredient prices, menu prices and disposal costs. Every rupee figure in FoodOS is derived from these. |
| `settings.channels.title` | Recovery channels |
| `settings.channels.body` | Where surplus can go, what each returns after commission, and the rules that make a channel unavailable. |
| `settings.zones.title` | Storage zones |
| `settings.zones.body` | Set points and measured temperatures. Shelf life is calculated against the measured figure, not the set point. |

---

## Track 2 and Track 3 stubs

| Key | Copy |
|---|---|
| `track.retail.title` | Retail |
| `track.retail.body` | Same objective, different actions: markdown timing, shelf facing, transfer between stores. |
| `track.production.title` | Production |
| `track.production.body` | Same objective, different actions: batch sizing, run sequencing, changeover timing. |
| `track.stub.note` | Running on the same optimiser as the kitchen. Only the action set changes. |

---

## Copy that must never appear

- "AI-powered", "intelligent", "smart", "revolutionary"
- "Oops", "Uh oh", "Something went wrong"
- "surplus", "leftover", "expiring" in any message sent to another outlet
- Any number that did not come from the API
