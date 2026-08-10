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
- [ ] `pytest backend/tests/test_external` — green **with the wifi already off**. These
      tests poison `urllib.request.urlopen`, so a pass is proof that no connector opens a
      socket, not merely that one happened not to be needed.
- [ ] Backend on `:8000`, frontend on `:5173`, both restarted, not left running overnight
- [ ] Browser: one tab, no extensions visible, no bookmarks bar, 125% zoom
- [ ] Command Center loaded, batch **T1024** present and reading 8.4% / 31 h / HIGH
- [ ] What-If sliders back at zero, destination back to Delhi APMC
- [ ] λ slider back at 0.5 (kitchen node)
- [ ] Timer where you can see it and the audience cannot

### The agri demo path, walked in order

The four batch screens are the pitch; the seven kitchen screens are twenty seconds of
platform proof at 4:10. Walk it in this order or the timings in
[`demo-script.md`](demo-script.md) do not hold.

- [ ] Screen 2 — register 10 t Kolar → Delhi, eleven answers, under 30 seconds on the clock
- [ ] Screen 2 step 4 — three photos, and once per rehearsal **skip them instead**, because
      that is the recovery path and it must be as smooth as the happy one
- [ ] Screen 3 — 8.4% as a band, 31 h remaining life, drivers ranked, HIGH
- [ ] Screen 3 — plan matrix, with at least one excluded row and its reason legible from
      the back of the room
- [ ] Screen 4 — drag departure, change vehicle, move the split; the current plan stays on
      screen throughout and the number never blanks
- [ ] Kitchen node group — open, eight seconds, close

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

Then walk the agri path as well — the batch screens are the ones with external connectors
behind them:

```powershell
# FOODOS_ALLOW_NETWORK must be UNSET. Network is opt-in, so absent means no socket.
Get-ChildItem Env:FOODOS_ALLOW_NETWORK   # must error: the variable does not exist
python -m pytest tests/test_external -q
```

**Expected:** every connector answers from `backend/data/external/*.json`, every response
carries `source: "snapshot"`, and Screens 3 and 4 render the staleness note rather than an
error. If any panel shows `source: "model"` during the demo path, a snapshot is missing —
run `python -m foodos.external.capture` and **commit the result**.

**What to actively hunt for:**

- [ ] A Google Font, an icon CDN, an analytics beacon in the frontend — anything that makes
      the app render slowly or blank without a network
- [ ] An avatar, image or map tile loaded from a URL
- [ ] A `fetch` to anything that is not `localhost:8000`
- [ ] A slow failure rather than a fast one: a 30-second timeout mid-demo is worse than an
      immediate fallback
- [ ] A `source: "model"` badge anywhere on the four batch screens — it means a captured
      snapshot is missing and a judge is being shown seasonal normals
- [ ] The What-If slider dragged to both extremes: at −12 h and +12 h the source must
      still read `snapshot`. Provenance changing mid-drag is a captured window that is
      too narrow, and it is fixed in `capture.py`, not on the night.
- [ ] The deck: if it is in Google Slides and only in Google Slides, it does not exist.
      Export to PDF and open the PDF once.

If anything here fails, it is a demo-path bug and it gets fixed regardless of the freeze.

---

## Contingency ladder

Work down it. Do not skip a rung, and do not explain to the audience which rung you are on.

| If | Then | Cost |
|---|---|---|
| A figure on screen differs from the script | **Read what is on screen.** Never announce a discrepancy nobody spotted | 0s |
| The recommended plan is not the split | Present the plan the engine picked and say what it is. The claim is the delta, not the split | 0s |
| Photo upload hangs | Tap Skip — a zero-photo batch is a supported path. *"And I'll skip the photos, because it works either way."* | 5s |
| `POST /simulate` is slow | It holds the previous figure by design. Say so — a blank number in an operations tool is how people stop trusting it | 0s |
| One screen throws an error | Navigate past it, keep talking, come back only if time allows | 0s |
| The frontend will not load | Present from the API responses in the browser at `/docs` — they contain every number | 15s |
| The backend will not start | `python -m foodos.agents.runner all --demo` in a terminal, then the deck | 20s |
| Nothing runs on the laptop | **Backup video.** Full screen, talk over it, do not mention it is a recording | 0s |
| The projector will not take the laptop | Present from the PDF on the organiser's machine | 30s |
| You lose your place entirely | Go to the What-If departure slider and drag it. It is the strongest thirty seconds in the demo and it re-anchors you. (Kitchen node: the λ slider does the same job) | — |

**Nobody says "it worked a minute ago".** Nobody says "let me just try one more thing". One
attempt at a recovery, then down the ladder.

---

## Backup video

Record after rehearsal 3, when the demo is stable but before the freeze makes it stale.

- [ ] 1080p, screen only, no webcam
- [ ] Voice-over recorded live with the run — not dubbed
- [ ] The full 4:40 path, including the What-If drag and the Verifier block
- [ ] No mouse hunting, no visible notifications, no other applications
- [ ] Saved **locally** on the presenting laptop, and on one other machine
- [ ] Played back once, in full, on the presenting laptop, with sound
- [ ] Embedded on hidden slide 10 of the deck

---

## Freeze rules — H33 onward

At **H30** the calibration of T1024 is locked at **8.4% loss / 31 h remaining life / 3.9%
on the best plan**, and the content constants under `backend/foodos/content/` are locked
with it. After that, a figure that drifts is fixed in the model or in a constant — never
hardcoded into a response, and never edited on the night. Deck screenshots are captured at
H33, *after* the lock, and re-captured if any figure moves.

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
