# Rehearsals and contingency

**Owner:** Person D. **Rehearsals:** 6. **Backup video:** recorded after rehearsal 3.

A rehearsal that everybody knows is a rehearsal is worth about a third of one that is run
cold, standing up, with a timer visible. Run them properly.

---

## Schedule

| # | Hour | Conditions | Purpose |
|---|---|---|---|
| 1 | H28 | Seated, script in hand, no timer | Find the beats that do not make sense out loud |
| 2 | H29 | Standing, timer visible, script face down | Find where you run over |
| 3 | H30 | Full dress: real laptop, real projector, cold start | Find what breaks in the room |
| — | H30 | **Record the backup video here** | — |
| 4 | H33 | **Wifi off** | Find hidden network calls |
| 5 | H34 | Person B or C deliberately breaks one thing, unannounced | Find out whether you can recover |
| 6 | H35 | Cold, silent room, no interruptions | Confidence |

---

## Before every rehearsal

- [ ] `python -m foodos.ingest.seed` — fresh database, no exceptions
- [ ] `pytest backend/tests` — green
- [ ] Backend on `:8000`, frontend on `:5173`, both restarted, not left running overnight
- [ ] Browser: one tab, no extensions visible, no bookmarks bar, 125% zoom
- [ ] λ slider back at 0.5
- [ ] Timer where you can see it and the audience cannot

## After every rehearsal, write down

1. Where you went over time, and by how much.
2. Every sentence you stumbled on — those are badly written, not badly delivered.
3. Every question the room asked that is not in `demo-script.md`. Add it.

---

## Rehearsal 4 — wifi off

The one that finds the failure nobody planned for. Turn wifi **off at the machine**, not at
the router — a captive portal is a different failure.

```bash
export FOODOS_LLM_OFFLINE=1     # Windows: $env:FOODOS_LLM_OFFLINE='1'
python -m foodos.ingest.seed
python -m foodos.agents.runner all --demo
```

Then walk the entire demo path in the browser.

**Expected:** everything works. The agents fall back to deterministic templates, the numbers
are identical because they were never the model's, and the Verifier's six checks are all
local.

**What to actively hunt for:**

- [ ] A Google Font, an icon CDN, an analytics beacon in the frontend — anything that makes
      the app render slowly or blank without a network
- [ ] An avatar, image or map tile loaded from a URL
- [ ] A `fetch` to anything that is not `localhost:8000`
- [ ] A slow failure rather than a fast one: a 30-second timeout mid-demo is worse than an
      immediate fallback
- [ ] The deck: if it is in Google Slides and only in Google Slides, it does not exist.
      Export to PDF and open the PDF once.

If anything here fails, it is a demo-path bug and it gets fixed regardless of the freeze.

---

## Contingency ladder

Work down it. Do not skip a rung, and do not explain to the audience which rung you are on.

| If | Then | Cost |
|---|---|---|
| One screen throws an error | Navigate past it, keep talking, come back only if time allows | 0s |
| The frontend will not load | Present from the API responses in the browser at `/docs` — they contain every number | 15s |
| The backend will not start | `python -m foodos.agents.runner all --demo` in a terminal, then the deck | 20s |
| Nothing runs on the laptop | **Backup video.** Full screen, talk over it, do not mention it is a recording | 0s |
| The projector will not take the laptop | Present from the PDF on the organiser's machine | 30s |
| You lose your place entirely | Go to the λ slider and drag it. It is the strongest thirty seconds in the demo and it re-anchors you | — |

**Nobody says "it worked a minute ago".** Nobody says "let me just try one more thing". One
attempt at a recovery, then down the ladder.

---

## Backup video

Record after rehearsal 3, when the demo is stable but before the freeze makes it stale.

- [ ] 1080p, screen only, no webcam
- [ ] Voice-over recorded live with the run — not dubbed
- [ ] The full 4:40 path, including the λ drag and the Verifier block
- [ ] No mouse hunting, no visible notifications, no other applications
- [ ] Saved **locally** on the presenting laptop, and on one other machine
- [ ] Played back once, in full, on the presenting laptop, with sound
- [ ] Embedded on hidden slide 10 of the deck

---

## Freeze rules — H33 onward

Merges to `main` only for a bug **on the demo path**. Everything else waits.

A change qualifies if, and only if:

1. It is reachable in the 4:40 script, and
2. It is currently wrong or broken, and
3. Person B or C has reproduced it, and
4. `python -m foodos.ingest.seed` and `pytest backend/tests` are green after the fix.

Refactors, renames, "quick tidies", new features, and improvements to screens the demo never
visits are all out. Every hackathon loses a demo to a fix that looked safe at hour 34.

---

## The last hour

- [ ] Reseed one final time
- [ ] Full test suite green, screenshot of the passing run
- [ ] Both servers restarted, demo path walked once, silently, by Person C
- [ ] Laptop charged, charger in the bag, screen brightness at maximum
- [ ] Notifications off — system-wide, not per-app
- [ ] Deck PDF open, backup video open, terminal ready with the agent demo already run
- [ ] Phone silent and out of reach
- [ ] Person D has read the close aloud one more time and stops rehearsing
