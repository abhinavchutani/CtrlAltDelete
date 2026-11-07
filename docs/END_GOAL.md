# End goal: what "done" means, how to keep moving, when to stop

Every agent reads this at the start of every run. It answers three questions:
1. What is the finish line?
2. What do I do when my lane has no task?
3. When do I stop for good?

## The finish line (G1–G5)

**Goal:** a submission-ready package that wins Apetit's rubric: usefulness 30 %, reasoning 25 %, traceability 25 %, reliability 10 %, technical 10 %. The end state is reached when every box below is checked, or the box is blocked only on a human (labelled `needs-human`).

### G1 · Complete
Every CSV we submit exists, validates against `tasks/templates/`, and is rebuilt by `make all`:

| File | Track | Task |
|---|---|---|
| `out/A1_issues_submission.csv` | A | #12 |
| `out/A2_inventory_2025_submission.csv` | A | #12 |
| `out/C1_yields_2027_2031_submission.csv` | C | #17 |
| `out/C2_climate_yield_risk_submission.csv` | C | #18 |
| `out/E_answers_submission.csv` | E | #23 |

### G2 · Good enough
Each line passes its bar, **or** has plateaued (see the plateau rule below):

| Metric (dev keys / backtest) | Bar |
|---|---|
| A1 overall dev score | ≥ 80 (baseline 52.17) |
| A2 dev score, 2023 and 2024 | ≥ 70 each (baseline ~25) |
| C1 backtest production MAPE (train ≤ 2023, predict 2024–26) | ≤ 8 % |
| C1 backtest field nRMSE | ≤ 0.25 |
| C2 | ensemble built and documented (no public truth) |
| E dev questions E90–E92 | all within tolerance |

### G3 · Demo-ready (usefulness + traceability)
- [ ] The Streamlit app's 4 pages and the copilot panel run on real (draft) results, not mocks.
- [ ] **Peat reveal:** farm footprint with vs without organic soils, as numbers in `results`.
- [ ] **C3:** € at risk per crop × region × SSP, the two-region hedge, and 3 actions with €, t and an owner.
- [ ] A click-through from one 2025 inventory number to its source record and factor works.
- [ ] Every published-able number has lineage (`L.orphan_published` is empty; the tests check it).

### G4 · Explainable and reproducible
- [ ] All `{{placeholders}}` in `METHOD_NOTE.md` and `docs/pitch/*` are filled from `results`, by a script, never by hand.
- [ ] README: a fresh clone + unzip + `make all` reproduces every file.
- [ ] CI is green on `main`.
- [ ] REASONING_LOG covers every rule the code uses.

### G5 · Frozen
**Code freeze: Sun 8 Nov 06:00 EET.** After that, only bug fixes and the human steps (approvals, video, submission by 10:00).

## v2 finish line (G6–G8), added 7 Nov after the Apetit Q&A

G1–G4 are done and v1 is frozen. v2 builds the product on top of it: a **Prediction layer**, a **Retrieval layer** and a **React app** over one API. The design is [V2_ARCHITECTURE.md](V2_ARCHITECTURE.md) (adaptation ideas from [RISK_MITIGATION_AND_ADAPTATION.md](RISK_MITIGATION_AND_ADAPTATION.md)); tasks, checkpoints and prompts are in [V2_AGENT_WORKFLOW.md](V2_AGENT_WORKFLOW.md). v1's CSVs must stay byte-identical (`tests/test_v2_guard.py`).

### G6 · Walking skeleton (CP1)
- [ ] `api/schemas.py` + fixtures; `API_MOCK=1 make api` serves every endpoint.
- [ ] `make web` renders the map, timeline, alerts, meters and ask panel from fixtures; `npm run build` passes.

### G7 · Real layers (CP2)
- [ ] `make v2` builds the 6 presets and the weather frames; the app runs on them with `API_MOCK=0`.
- [ ] `/api/ask` answers the 5 demo questions offline with evidence; one .xlsx report downloads.
- [ ] Alerts: critical and notable only, ≤ 12 per scenario, € as bands, each with a suggested lever.
- [ ] `kb/adaptation_options.csv` loaded; `/api/options` answers by hazard and crop.

### G8 · Live ideas (CP3)
- [ ] Voice or text → intent → spec chips → live `/api/simulate` in < 15 s.
- [ ] The "better option" card and rule-based confidence work.
- [ ] Hedge frontier (expected + tail loss) and adaptation pathways (tipping and decide-by years) are served and shown.
- [ ] The decision board lists the critical risks with action, owner, decide-by and evidence; one human approval is logged.
- [ ] The 6-step demo in V2_AGENT_WORKFLOW.md runs end to end; the README has a v2 section.

## Keep moving: create the next step yourself

**If your lane has no claimable task and the end state is not reached:**
1. **Find the gap.** Look at the G1–G4 boxes and `docs/SCOREBOARD.md`. Pick the **unchecked box with the highest rubric weight** that your lane can move. Order: G1, then the G2 lines furthest below their bar, then G3, then G4.
2. **Create at most 2 tasks** for it with `scripts/agent-chat.sh new-task`. Each needs:
   - a title starting with its priority, e.g. `[P1]`;
   - a *Done when* with a measurable bar;
   - *Depends on*;
   - the G-box it closes, e.g. "closes G2·A1".
3. **Claim one and start.** Announce it in the chat with `CLAIM`.

**Don't invent new scope.** If a task doesn't close a G-box (G1–G8), don't create it. No new tracks (B and D stay a slide), no v2 features beyond V2_ARCHITECTURE.md, and no features nobody can demo.

**Time-box every task to about 90 minutes of agent work.** If a task will take longer, split it.

## The plateau rule: stop polishing

A G2 metric counts as **plateaued** when the last **2 attempts in a row** each improved it by **< 1 point** (scores), or **< 0.5 percentage points** (MAPE).
- Log every attempt in `docs/SCOREBOARD.md`: date, PR, metric before → after.
- Once a metric has plateaued, stop working on it, check it off as "plateaued at X" in the scoreboard, and move to the next gap.
- **Never game the dev keys:** no hard-coding labels, no rules that only fit specific record keys.

## Stop for good (the DONE state)

When G1–G4 and G6–G8 are all checked, or every unchecked box is labelled `needs-human`, **or** it's past the G5 freeze and your lane has nothing left but human steps:
1. Finish or `release` your claimed task, and post a `HANDOFF` saying where things stand.
2. Update `docs/SCOREBOARD.md` with the final numbers, in a PR.
3. Post **one** final message: `DONE: <lane> reached the end goal | final scores … | human steps left …`.
4. **Stop your loop.** In Claude Code, delete your scheduled loop job (`CronDelete <id>`); if you can't, tell your human in the chat message. Don't create more work, and don't keep waking up to post `IDLE`.

When all three lanes have posted `DONE`, the humans take over: approve the corrections queue, publish results, record the video, and submit.
