# The three planted pathologies

**Owner:** Person D, agreed with Person A at H0–3.
**Status:** numbers below are derived from `backend/foodos/content/` and enforced by
`backend/tests/test_agents/test_content.py`. Person A's generator must reproduce them
within a rounding. If it does not, one of the two is wrong and we find that out in
rehearsal, not on stage.

A demo dataset with no structure produces a demo with nothing to say. These three
pathologies are planted deliberately, one per horizon, so that each screen has a real story
and the judges see three different kinds of failure rather than three views of one.

> ## ⚠ This document is out of date — read this before the deck
>
> The three sections below describe pathologies that **are not the ones in the dataset.**
> `FoodOS-Team-Split.md` §5 froze the planted faults at H0–3, and Person A's generator
> implements those exactly — `python -m foodos.verify` passes 14/14 against them. This
> file drifted from that list, so the deck and demo script built on it describe a demo
> that will not appear on screen.
>
> **What is actually planted, with the numbers the code produces today:**
>
> | # | Planted fault (§5, authoritative) | Horizon | Measured value |
> |---|---|---|---|
> | 1 | Friday over-prep of Chicken Biryani | PREVENT | **36.2% over on Fri**, vs 20.6% overall |
> | 2 | Cauliflower trim yield below the standard table | PRESERVE | **0.512 actual vs 0.58 standard** — 268.4 kg / ₹10,735 avoidable |
> | 3 | Dock temperature excursion on a spinach receipt | PRESERVE | batch B01674 — label says 4 days, really 0.81 days, **overstated by 3.2** |
>
> **What this file currently says instead:** plan drift on *Gobi Manchurian* (§1), an
> *under-counter chiller* (§2), and a *Sunday chicken* over-order with no route to sell
> (§3). The first two are the right mechanism attached to the wrong subject. The third
> has no counterpart in the data at all, and the cauliflower trim yield — a real planted
> fault, and the one that demonstrates the trim detector — is missing from this file
> entirely.
>
> The header above already anticipated this: *"Person A's generator must reproduce them
> within a rounding. If it does not, one of the two is wrong."* A is right; this file is
> wrong. **Person D owns the rewrite of the three narrative sections below.** They are
> left in place rather than deleted so the prose can be re-pointed rather than rewritten
> from nothing.

| # | Pathology | Horizon | Screen it lands on | Agent that speaks |
|---|---|---|---|---|
| 1 | Chronic over-production of a soft-weekday dish | PREVENT | Today → Why → Plan | Diagnostician |
| 2 | Fast decay in a chiller running above set point | PRESERVE | Ledger → Rescue | Planner |
| 3 | Sunday over-order with no route to sell it | RECOVER | Rescue | Communicator |

---

## Pathology 1 — plan drift on Gobi Manchurian

**The mechanism.** Weekday demand for Gobi Manchurian fell after a menu change three weeks
ago. The forecast tracked it down. The prep sheet did not — it is still cut to the volumes
that were right a month ago. Nobody is being careless: the prep sheet is a laminated card on
the wall, and nothing in the kitchen's day forces it to be reprinted.

This is the single most common form of food waste in a professional kitchen, and it is
invisible in a waste report, because a waste report tells you *what* was thrown away and
never *which decision* put it there.

**Why this dish.** Cauliflower has a 0.58 prep yield — the worst on the menu. Every portion
consumes 0.564 kg of purchased input for 250 g of food. Over-producing it is unusually
expensive in kilograms, which makes the kg-at-risk KPI move visibly.

**The numbers.**

| Quantity | Value | Where it comes from |
|---|---|---|
| Planned portions (prep sheet) | 80 | planted by Person A |
| Forecast mean, soft weekday | 55 | Person A's generator |
| Forecast standard deviation | 13 | Person A's generator |
| Contribution margin `Cu` | ₹172.72 | `costs.yaml` derived block |
| Over-production cost `Co` | ₹49.79 | food cost + labour + disposal |
| Optimal service level at λ=0.5 | 0.731 | newsvendor |
| **Recommended portions** | **63** | forecast quantile at 0.731 |
| Input avoided | 9.6 kg | 17 portions × 0.564 kg |
| Cost avoided per day | ₹787 | 17 × ₹46.28 |

**The line for the deck:** the forecast was right, the plan was stale, and no report in this
kitchen was capable of telling the difference.

---

## Pathology 2 — the under-counter chiller

**The mechanism.** `COLD_2`, the under-counter chiller on the prep line, is set to 4 °C and
actually runs at 9.2 °C, because its door is opened every ninety seconds during service.
Nobody has noticed, because the thermometer reads correctly the moment anyone looks at it —
first thing in the morning, when the door has been shut all night.

Paneer is the most expensive short-life item in the kitchen and the one that suffers most:
fresh dairy carries a Q10 of 3.0, meaning spoilage runs three times faster per 10 °C.

**The derivation.** From `shelf_life.yaml`, `dairy_fresh`: base 5.0 days, reference 4 °C,
Q10 3.0, cut life factor 0.60.

```
temp_factor = 3.0 ** ((9.2 - 4.0) / 10)   = 1.771
life        = 5.0 / 1.771                 = 2.824 days
cut (cubed) = 2.824 × 0.60                = 1.694 days
age         = 1.0 day
RSL         = 1.694 - 1.0                 = 0.69 days  ->  0.7 days
```

The same batch in `COLD_1` (the walk-in, actually at 4.6 °C):

```
temp_factor = 3.0 ** ((4.6 - 4.0) / 10)   = 1.068
life        = 5.0 / 1.068 × 0.60          = 2.809 days
RSL         = 2.809 - 1.0                 = 1.81 days
gain        = 1.81 - 0.69                 = 1.1 days
```

**Moving a tray from one fridge to another buys a day of life and costs nothing.** That is
the most quietly persuasive fact in the entire demo, and it is only visible because RSL is
modelled against temperature rather than read off a printed date.

**The numbers.**

| Quantity | Value | Where it comes from |
|---|---|---|
| Batch | B-1042, paneer, 4.4 kg | planted by Person A |
| Batch value at cost | ₹1,496 | 4.4 kg × ₹340 |
| Remaining shelf life | 0.7 days | RSL model, above |
| Life gained by re-zoning | 1.1 days | RSL model, above |
| Special selected | Paneer Butter Masala | optimiser |
| Portions covered | 36 | 4.32 kg ÷ 0.120 kg per portion |
| Contribution recovered | ₹6,680 | 36 × ₹185.56 |

---

## Pathology 3 — Sunday chicken with nowhere to go

**The mechanism.** A Sunday order was placed against a forecast that assumed a cricket
fixture. The fixture moved. There is now 9.6 kg of boneless chicken with a day and a half of
life, on a Tuesday, and the kitchen's instinct — run a chicken special — is wrong, because
Tuesday covers cannot absorb it.

**The derivation.** `poultry_raw`: base 2.0 days, reference 2 °C, Q10 2.8. `MEAT_1` runs at
2.4 °C, so the temperature penalty is negligible; the constraint here is the calendar, not
the chiller.

```
temp_factor = 2.8 ** ((2.4 - 2.0) / 10)   = 1.042
life        = 2.0 / 1.042                 = 1.92 days
age         = 0.5 days
RSL         = 1.42 days  ->  1.4 days
```

**The ranking, with the feasibility gate applied first.**

| Channel | Status | Value | Why |
|---|---|---|---|
| **Transfer to sister outlet** | eligible | **₹2,419** | 9.6 kg × ₹280 × 0.90 |
| Same-day menu special | eligible | ₹1,190 | capped by Tuesday covers |
| Staff meal | eligible | ₹1,478 but capped at 6 kg | ceiling, not a rate |
| Delivery app flash deal | **excluded** | — | batch is raw; channel takes cooked or prepped |
| NGO donation | **excluded** | — | collections run Mon/Wed/Fri; today is Tuesday |
| Animal feed | **excluded** | — | poultry cannot enter a no-meat-contact stream |
| Disposal | eligible | −₹115 | the baseline everything is measured against |

Advantage of the transfer over disposal: **₹2,534** (₹2,419 recovered plus ₹115 of disposal
cost avoided).

**The point of this pathology is the greyed-out rows.** Three channels are excluded, each
for a different and checkable reason, and all three are shown with the reason attached. An
operator who watches an option disappear without explanation stops trusting the system by
the end of the week.

---

## What λ does, per dish

Content-derived, and asserted by `test_lambda_can_actually_move_the_plan`. `q*` is the
newsvendor service level; the plan quantity is the forecast at that quantile.

| Dish | q* at λ=0 | q* at λ=1 | Δ |
|---|---|---|---|
| Gobi Manchurian | 0.776 | 0.690 | 8.6 pp |
| Vegetable Dum Biryani | 0.696 | 0.609 | 8.6 pp |
| Palak Paneer | 0.707 | 0.633 | 7.4 pp |
| Veg Hakka Noodles | 0.774 | 0.702 | 7.2 pp |
| Hyderabadi Chicken Biryani | 0.637 | 0.565 | 7.2 pp |
| Amritsari Chole | 0.804 | 0.740 | 6.4 pp |
| Paneer Butter Masala | 0.658 | 0.596 | 6.2 pp |
| Mutton Rogan Josh | 0.594 | 0.533 | 6.2 pp |
| Chilli Paneer | 0.686 | 0.624 | 6.2 pp |
| Butter Chicken | 0.669 | 0.608 | 6.1 pp |
| Butter Naan | 0.603 | 0.541 | 6.1 pp |
| Dal Makhani | 0.761 | 0.711 | 5.0 pp |
| Goan Fish Curry | 0.698 | 0.649 | 4.9 pp |
| Jeera Rice | 0.779 | 0.739 | 4.0 pp |

**Be honest about the size of this.** On one dish, dragging λ from 0 to 1 moves the plan by a
few portions. The visible effect is at the portfolio level, on the Plan screen totals, across
all fourteen dishes at once. If a judge asks whether carbon pricing really changes decisions
at the dish level, the answer is: barely, at any defensible carbon price — which is exactly
why the objective prices the full wastage externality and not carbon alone. See the comment
block at the top of `costs.yaml`.

---

## What Person A must plant in the generator

1. `gobi_manchurian` production held at 80/day on Mon–Thu for the whole history, while
   realised demand steps down to a mean near 55 three weeks before the demo date.
2. `COLD_2` temperature series averaging 9.2 °C during service hours and 4.5 °C overnight,
   so that a morning spot check looks fine.
3. A paneer batch `B-1042`, 4.4 kg, received into `COLD_2`, cubed, one day old on the demo
   date.
4. A boneless chicken batch `B-1057`, 9.6 kg, received Sunday into `MEAT_1`, half a day old
   on the demo date, with the demo date falling on a **Tuesday** — the NGO exclusion depends
   on it.
5. Held-out days for the backtest that include at least one of each pathology, so the Impact
   screen's baseline comparison is not flattering by accident.

## What to verify in every rehearsal

- [ ] Today's three KPIs are non-zero and the same as the last run.
- [ ] The Why screen's top contributor is *plan drift*, not something that moved overnight.
- [ ] B-1042 shows an RSL under a day, in red.
- [ ] The Rescue screen shows exactly three greyed-out channels, each with a visible reason.
- [ ] Dragging λ across its full range changes the Plan totals.
- [ ] The Diagnostician's sentence names the same contributor the bar chart ranks first.
