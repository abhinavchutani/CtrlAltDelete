# Navigator v2: workflow for the three agents

> What each agent builds, in what order, how it uses subagents, and the prompt to paste. The design is [V2_ARCHITECTURE.md](V2_ARCHITECTURE.md); the adaptation ideas it builds on are in [RISK_MITIGATION_AND_ADAPTATION.md](RISK_MITIGATION_AND_ADAPTATION.md). `AGENTS.md` and `docs/AGENT_LOOP.md` still apply word for word; this file only adds the v2 tasks and rules.

## Who builds what

| Agent | `AGENT_LANE` | v2 role | Task label | Owns |
|---|---|---|---|---|
| `noa-claude` | `platform` | **Contract, API, React skeleton** | `track:app` | `api/`, `web/`, `src/serve_db.py`, new Makefile targets, `tests/test_api_*`, `tests/test_v2_guard.py` |
| `climate-agent` | `C` | **Prediction layer**: scenarios, alerts, weather, hedge frontier, pathways | `track:C` | `src/p_*.py`, `tests/test_p_*` |
| `abhinav-claude` | `A` | **Retrieval layer**: ask, reports, adaptation KB, decision board | `track:A` | `src/r_*.py`, `kb/`, `tests/test_r_*` |

No `.env` changes are needed: the lanes keep their names and the v2 tasks carry the matching track label.

**Reviews:** the Prediction and Retrieval agents review each other's PRs. Both review the Platform agent's PRs. Platform reviews both.

## v2 rules (on top of AGENTS.md)

1. **v1 is frozen.** Never edit `src/a_*`, `src/c_*`, `src/e_*`, `src/lineage.py`, `src/load.py`, `app/` or any `out/*_submission.csv`. Import from them. If you find a v1 bug, create a separate task and label it `needs-human`.
2. **Read only `out/serve.duckdb`** through `src.serve_db.connect(read_only=True)`. The prediction engine may make a private in-memory copy for its temp tables. Never write to `issues`, `corrections`, `results` or `lineage`.
3. **The contract is `api/schemas.py`.** Return exactly those shapes. If you need a change, post a `QUESTION` in the chat addressed `to:all`; after CP1 a shape changes only when all three agents agree.
4. **Numbers come from code.** The LLM only routes, fills a `ScenarioSpec`, picks tools and phrases. € values leave the API only as `EurBand`s. Accuracy percentages are not shown in the UI.
5. **Alerts are critical or notable only,** capped at 12 per scenario (thresholds in `src/p_alerts.py`).
6. **Every LLM call goes through `src/e_llm.chat`** (cached, temperature 0) and has an offline fallback. The demo must run with no API key.
7. **The UI is a skeleton.** Working, typed and unstyled: logic in hooks, the store and layer functions; styling only through `web/src/theme/tokens.css`. The human designs it later, so don't spend time on looks.
8. **Synthetic data:** every API response has `synthetic: true` where the schema has it, and the app always shows the banner.
9. **Every module has a CLI smoke check** (`python -m src.p_engine --preset current_plan_ssp245`, `python -m src.r_agent "question"`) and its command goes in the PR body.
10. **Tests:** schema and fixture tests run in CI with no data. Anything needing the pack or `serve.duckdb` uses `pytest.skip` when it's missing. CI doesn't build `web/` (`.github/` is protected), so the reviewer runs `cd web && npm ci && npm run build`.
11. **New Python packages** (`openpyxl`, maybe `pydantic` pinned): adding to `requirements.txt` is fine; say so in the PR.

## Checkpoints (EET, Sat 7 → Sun 8 Nov)

| CP | By | Everyone can see |
|---|---|---|
| CP1 · walking skeleton | Sat 16:30 | `API_MOCK=1 make api` + `make web`: map, timeline dots, meters, alerts and the ask panel render from fixtures. P and R have module stubs that return contract shapes |
| CP2 · real layers | Sat 22:00 | `make v2` builds the 6 presets and weather frames; the app runs on them with `API_MOCK=0`; `/api/ask` answers the 5 demo questions offline with evidence; one .xlsx report downloads. **The human starts on the UI here** |
| CP3 · live ideas | Sun 02:30 | Voice or text → intent → spec chips → live `/api/simulate` < 15 s; alerts have suggested levers; "better option", hedge frontier, pathways and the decision board (with a logged approval) work; the LLM ask loop passes its eval |
| Freeze | Sun 06:00 | README v2 section, `make v2-check` green, v1 CSVs unchanged (guard test) |

**No polishing before CP2.** Weak but complete first.

## The task list

The `scripts/v2-seed-tasks.sh` script creates these 14 issues with the right labels and dependencies. Each is about 60–120 minutes of agent work.

### Platform (`track:app`)

**V2-1 [P0] Contract, API skeleton, fixtures, snapshot.** Depends on: none.
- `api/schemas.py` exactly as in V2_ARCHITECTURE; `api/main.py` with every endpoint; `API_MOCK=1` serves `api/fixtures/*.json`.
- Fixtures with realistic values (a mix of preset results, 6 alerts across 2027–2045 with hazards, 3 weather frames, 2 ask answers with a table and evidence, a hedge frontier, 4 pathway items, 4 board rows, 5 adaptation options).
- `src/serve_db.py` (`connect(read_only=True)`, path from env `SERVE_DB`, default `out/serve.duckdb`); Makefile targets `snapshot`, `v2` (calls `src.p_presets` and `src.r_catalog` when they exist, otherwise prints a note), `api`, `web`, `v2-check`.
- `out/v1_manifest.json` (sha256 of each `out/*_submission.csv`) and `tests/test_v2_guard.py`.
- `web/src/api/openapi.json` exported by `python -m api.export_openapi`.
- **Done when:** `pytest -q` validates every fixture against its schema; `API_MOCK=1 make api` and `curl /api/health` work; a `HANDOFF` in the chat lists the endpoints and the import path `from api.schemas import ...`.
- **Ship this in your first run.** The other two lanes are waiting for it.

**V2-2 [P0] React skeleton on fixtures.** Depends on: V2-1.
- Vite + React + TS in `web/`, the folder layout from V2_ARCHITECTURE, generated types, react-query hooks, zustand store.
- Map: deck.gl over maplibre, with parcels (extruded, colour = change vs baseline), farm columns and weather cells; a layer toggle.
- Timeline 2026 → horizon: play and scrub; one dot per alert; clicking a dot opens its AlertPopup and moves the map.
- Meters, SpecChips + LeverEditor + ScenarioPicker, AskPanel (answer, table, evidence chips, report button), the synthetic banner.
- HedgeChart, PathwaysGantt (decide-by markers also on the timeline's second row), DecisionBoard + DecisionDialog (approve / edit / reject with a typed name and reason).
- **Done when:** `make web` shows all of it on fixtures; `npm run build` and `npx tsc --noEmit` pass; a short screen recording or screenshots in the PR.

**V2-3 [P1] Wire the real layers, the intent router and voice.** Depends on: V2-2, V2-5, V2-9.
- `/api/intent`: calls `src.p_parse.parse(text)`; routes to `ask` when there's no lever or what-if wording.
- `/api/geo/parcels`: simplified polygons (round to 5 decimals, keep `parcel_id, farm_id, area_ha`, gzip); `/api/geo/farms`.
- `useSpeech.ts` with the browser Web Speech API (fi-FI / sv-SE / en-US), text box fallback.
- The prediction context loads once at API start-up (`lifespan`), with a `warming` flag in `/api/health`.
- **Done when:** with `API_MOCK=0` the 6-step demo below runs end to end on presets.

**V2-4 [P2] Docs and demo.** Depends on: V2-3.
- README "v2" section (run commands), a one-paragraph v2 addition to `METHOD_NOTE.md`, the demo script below in `docs/pitch/`, the Microsoft mapping slide text.
- **Done when:** a clean checkout runs `make snapshot v2 api web` from the README alone.

### Prediction (`track:C`)

**V2-5 [P0] Spec, engine, cube, presets.** Depends on: none (claim it now; switch to `api.schemas` once V2-1 merges).
- `p_spec.py`: lever bounds and validation messages (used by `/api/intent` `problems`).
- `p_engine.py`: `load_context()`, `simulate(spec) -> SimResult` with the lever → hook table from V2_ARCHITECTURE; 2026–horizon years; the planned mix for 2027–31, then held.
- `p_cube.py`: region × crop × year and farm × year tables with change vs baseline, exact € (internal) and € band; `out/v2/cube/{scenario_id}.parquet`.
- `p_presets.py`: the 6 presets → `out/v2/`.
- **Done when:** `python -m src.p_presets` writes all 6; `GET /api/scenario/current_plan_ssp245` returns a valid `SimResult`; the 2026 SE pea drop shows up as a bad year; runtime per preset in the PR.

**V2-6 [P0] Weather frames.** Depends on: none (switch to `api.schemas` once V2-1 merges).
- `p_weather.py`: a `WeatherFrame` per climate × year for 84 cells (historical 1991–2026, then each SSP to 2060), from the pack's daily weather and the `c_features` soil-water bucket.
- **Done when:** `/api/weather?climate=ssp245&year=2035` is valid and < 200 ms (precomputed); 2026 shows the Swedish drought in the drought index.

**V2-7 [P1] Alerts, better option, meters.** Depends on: V2-5.
- `p_alerts.py` with the critical/notable rules, a cap of 12, a `kind` from the dominant stress feature, `suggested_lever`, and evidence refs.
- `p_compare.py`: the ~10-combination grid per climate → `BetterOption`.
- Meters with rule-based confidence and its reasons.
- **Done when:** `current_plan_ssp585` has 4–12 alerts, at least one `critical`, and the "bad-year odds pass 1 in 4" marker; each alert's text is built only from computed values; a unit test pins the thresholds.

**V2-8 [P1] Text → spec, and live simulate.** Depends on: V2-5.
- `p_parse.py`: `parse(text) -> IntentOut`. LLM path with the `ScenarioSpec` JSON schema; an offline path of keyword and number rules covering the 6 demo phrasings below. It never invents a lever: unknown asks go to `problems`.
- `/api/simulate` on the warm context, < 15 s; fall back to region-level when slower.
- **Done when:** a test feeds 12 phrasings (English, plus 2 in Finnish or Swedish if the LLM is on) and checks the specs; the measured simulate time is in the PR.

**V2-13 [P1] Hedge frontier and adaptation pathways.** Depends on: V2-5, V2-12.
- `p_hedge.py`: Finland share 0–100 % in 5 pp steps → expected and tail (CVaR10) € loss over the ensemble years; today's and the best share; `why` sentence. Re-implement the loss table from `c_euro.rebalance`, don't edit it.
- `p_pathways.py`: tipping year (10-year rolling bad-year share > 1 in 4 on the weather path, checked against the 2041–60 ensemble odds), decide-by per KB option (tipping − max lead time), signpost text.
- **Done when:** `/api/hedge?climate=ssp245` and `/api/pathways/current_plan_ssp585` are valid; under ssp585 pea in SE_SKANE has a tipping year and the heat-tolerant variety a decide-by year; a test pins the threshold and the rolling window.

### Retrieval (`track:A`)

**V2-9 [P0] Catalog, safe SQL, docs search, offline ask.** Depends on: none (claim it now; switch to `api.schemas` once V2-1 merges).
- `r_catalog.py`: table and column cards from `DATA_DICTIONARY.md` + the DuckDB schema (description, years covered, source file, row count, key columns) → `out/v2/catalog.json`; `catalog_search(query)`.
- `r_sql.py`: `run_sql(sql)` with SELECT only, read-only, allow-listed tables, 500-row cap, 5 s timeout, returning the source file and record keys.
- `r_docs.py`: `e_tools.search_frameworks` extended to METHOD_NOTE, REASONING_LOG and correction reasons.
- `r_agent.py`: `ask(question) -> AskOut`; offline routes for the 5 demo questions in V2_ARCHITECTURE.
- **Done when:** `python -m src.r_agent "<each demo question>"` returns `answered` with evidence; a write statement through `run_sql` is refused (test).

**V2-10 [P1] Reports to Excel.** Depends on: V2-9.
- `r_report.py`: the 5 templates; a data sheet plus a "Sources" sheet; `out/v2/reports/{report_id}.xlsx`; `/api/report/{report_id}`.
- **Done when:** "Build me the 2024 energy report by site and month" returns `report` in `AskOut`, and the file opens with both sheets (a test reads it back with openpyxl).

**V2-11 [P1] LLM tool loop and eval.** Depends on: V2-9.
- The tool loop over `catalog_search`, `run_sql`, `search_docs`, `query_results` and `make_report`, with `e_agent.finish`'s number post-check and `not_in_data`.
- An eval set of 15 questions with expected answers computed by deterministic SQL → `out/v2/ask_eval.json`.
- **Done when:** with an LLM key, at least 12 of 15 pass; without a key, the offline routes still pass their 5.

**V2-12 [P0] Adaptation options KB.** Depends on: none.
- `kb/adaptation_options.csv`: the 20 options in RISK_MITIGATION §7 with the §6 side-effect columns and the `lever` for the 5 the engine can re-run; `reviewed_by` empty.
- `r_options.py`: `options(hazard, crop) -> list[AdaptationOption]`; also registered as a copilot tool.
- **Done when:** a test loads every row into the schema; `/api/options?hazard=H2&crop=pea` lists A04 and A06 first; "what can we do about heat at flowering?" answers from the KB with its source.

**V2-14 [P1] Decision board with expert approval.** Depends on: V2-7, V2-12.
- `r_board.py`: rows per scenario as in V2_ARCHITECTURE (critical alerts first, at most 8), joined with options, decide-by years (from V2-13 when it lands; empty until then), owner and evidence. Decisions append to `out/v2/decisions.jsonl`; `decided_by` only from the request body, never filled by code.
- **Done when:** `/api/board/current_plan_ssp245` returns rows; a POST decision round-trips and survives an API restart; a test checks that a decision without `decided_by` is refused.

## Cut order (if a lane is behind at CP2)

1. V2-11's eval shrinks to 8 questions; the offline routes carry the demo.
2. Live `/api/simulate` falls back to the nearest preset plus the lever's precomputed delta.
3. Pathways show only pea × 2 regions × ssp245/ssp585.
4. Finnish/Swedish voice phrasing.

Never cut: the contract, the presets, the alerts, the decision board's approval log, the synthetic banner.

## Subagents (AGENTS.md section 9 still applies)

- **At most 3 at once.** A subagent never claims, pushes, merges or posts in the chat. You check its output (run the tests, read the diff) before you commit it.
- **Give each one a written brief:** the goal, the files it may touch (only inside your area), the exact output, and the done-when. It never gets your whole task.
- **Prefer read-only subagents** for surveys and audits; write-subagents only for pieces that don't share files with what you're editing.

| Lane | Good subagent jobs | Not for a subagent |
|---|---|---|
| Platform | (1) Scaffold `web/` with Vite, deps and the empty folder layout while you write `api/schemas.py`. (2) Write the fixtures from the schemas, with realistic values read from `serve.duckdb`. (3) Write the parcels simplification and check the size | The schemas themselves; wiring the real layers |
| Prediction | (1) Read-only audit of `c_ensemble.py` / `c_euro.py` / `c_features.py`: for each lever, the exact function and line it hooks into, and what `production()` needs. (2) Build `p_weather.py` on its own (it shares no files with the engine). (3) A timing experiment: `production()` on the full mix vs region level, report the seconds. Later: (4) cross-check the hedge frontier's tail loss against a brute-force recount on the raw loss table | `p_engine.simulate` and the alert rules |
| Retrieval | (1) Survey every table in `serve.duckdb` and draft the catalog cards (broad search; you only need the result). (2) Write the 5 report templates against the catalog. (3) Build the 15-question eval set with the deterministic SQL answers. (4) Turn RISK_MITIGATION §6–§7 into `kb/adaptation_options.csv` rows (you check every row against the doc) | The SQL safety layer; the agent's post-check |

## Building instructions (every lane)

1. Start each task the usual way: `scripts/agent-chat.sh claim <n>` → `scripts/agent-chat.sh start <n> <slug>` → `cd .worktrees/<n>`. Run `make snapshot` once in the worktree if `out/serve.duckdb` is missing.
2. **Contract first.** Import from `api.schemas`; until V2-1 lands, write plain functions returning dicts shaped like the doc, then switch.
3. Keep PRs under ~400 lines. Open a draft PR early.
4. Before review: `git fetch origin && git merge --no-edit origin/main`, then `make v2-check` (or `pytest -q` and, for `web/`, `npm run build`). Put the smoke command, its output summary and the timing in the PR body.
5. Leave a progress note on the issue every run, and post one `STATUS`.
6. When your lane is empty: review, then help on another lane's unblocked v2 task, then create at most 2 tasks for the biggest open v2 box (G6–G8 in END_GOAL.md).

## The demo the build must support (≈3 minutes; the 2-minute video uses beats 1, 3, 4, 6 and 8)

1. The map opens on 2026: Swedish pea fields red, the drought visible in the weather layer.
2. Voice: *"How did pea deliveries from Swedish farms in 2026 compare with 2021?"* → answer, table, evidence chips, then *"Make that a report"* → the .xlsx downloads.
3. Press play on the current plan, ssp245, to 2040: fields shift colour, dots appear; click the critical one → the popup with its € band and suggested lever.
4. Voice: *"What if we irrigate the driest pea fields and move to a 70/30 Finland–Sweden split?"* → spec chips → confirm → the map, dots and meters update.
5. The "better option" card: what it saves, and why.
6. Switch to ssp585, 2060: the pathways row shows *"decide by 2029: heat-tolerant pea"*; add *"a heat-tolerant pea from 2030"* and the tipping marker moves; confidence drops to low because it's an assumption.
7. The hedge frontier: *"moving 15 pp of pea to Finland cuts the 1-in-10-year loss by one band"*.
8. The decision board: one row per critical risk with action, owner, decide-by and evidence; the human approves one live with their name and a reason.

## Prompts (paste once per agent; `/loop` re-runs it every 15 minutes)

Settings as before: Opus 5.5, effort High, Auto mode. Stop the old loop first (`CronDelete <id>`).

### Platform (`noa-claude`)

```
/loop 15m You are the CtrlAltDelete Platform agent (AGENT_LANE=platform) building Navigator v2. On your first run in this session, read AGENTS.md, docs/AGENT_LOOP.md, docs/END_GOAL.md, docs/V2_ARCHITECTURE.md, docs/V2_AGENT_WORKFLOW.md and docs/RISK_MITIGATION_AND_ADAPTATION.md in full. Every run, follow docs/AGENT_LOOP.md exactly: sync main, read the chat and answer anything for you, review other agents' PRs first, then continue your claimed v2 task or claim the next track:app task by priority and dependencies, work only in its worktree, and push small PRs. Start with the V2-1 contract task and ship it in your first run: both other lanes depend on api/schemas.py and the fixtures, so post a HANDOFF with the endpoints when it lands. Then the React skeleton on fixtures. The UI is a skeleton the human will restyle: typed, working, unstyled, logic out of components, styling only via theme tokens. Never edit v1 files. Use subagents per V2_AGENT_WORKFLOW.md, at most 3. Stop at a natural checkpoint, leave a progress note on the issue, post one STATUS, and end the run. Never stop to ask me: for a human decision use scripts/agent-chat.sh block and move on.
```

### Prediction (`climate-agent`)

```
/loop 15m You are the CtrlAltDelete Prediction agent (AGENT_LANE=C) building Navigator v2's prediction layer. On your first run in this session, read AGENTS.md, docs/AGENT_LOOP.md, docs/END_GOAL.md, docs/V2_ARCHITECTURE.md, docs/V2_AGENT_WORKFLOW.md and docs/RISK_MITIGATION_AND_ADAPTATION.md in full, then reread src/c_ensemble.py and src/c_euro.py. Every run, follow docs/AGENT_LOOP.md exactly: sync main, read the chat and answer anything for you, review other agents' PRs first, then continue your claimed v2 task or claim the next track:C task by priority and dependencies, work only in its worktree, and push small PRs. Start with the engine, cube and presets task (begin before api/schemas.py lands, then adopt it), then weather frames, then alerts and live simulate, then the hedge frontier and pathways. Deterministic code computes every number; € leaves the API only as bands; alerts are critical or notable only; one plausible weather path, never "will happen". Never edit v1 files: import them. Use subagents per V2_AGENT_WORKFLOW.md, at most 3. Stop at a natural checkpoint, leave a progress note on the issue, post one STATUS, and end the run. Never stop to ask me: for a human decision use scripts/agent-chat.sh block and move on.
```

### Retrieval (`abhinav-claude`)

```
/loop 15m You are the CtrlAltDelete Retrieval agent (AGENT_LANE=A) building Navigator v2's retrieval layer. On your first run in this session, read AGENTS.md, docs/AGENT_LOOP.md, docs/END_GOAL.md, docs/V2_ARCHITECTURE.md, docs/V2_AGENT_WORKFLOW.md and docs/RISK_MITIGATION_AND_ADAPTATION.md in full, then reread src/e_tools.py, src/e_agent.py and src/e_llm.py. Every run, follow docs/AGENT_LOOP.md exactly: sync main, read the chat and answer anything for you, review other agents' PRs first, then continue your claimed v2 task or claim the next track:A task by priority and dependencies, work only in its worktree, and push small PRs. Start with the catalog, safe SQL and offline ask task (begin before api/schemas.py lands, then adopt it), then the adaptation options KB, then Excel reports, the decision board and the LLM tool loop with its eval. Numbers only from tool results, evidence on every answer, read-only SQL on out/serve.duckdb. Never edit v1 files: import them. Use subagents per V2_AGENT_WORKFLOW.md, at most 3. Stop at a natural checkpoint, leave a progress note on the issue, post one STATUS, and end the run. Never stop to ask me: for a human decision use scripts/agent-chat.sh block and move on.
```

## Human steps

1. Merge this docs PR (it changes END_GOAL.md).
2. Tag v1: `git tag v1-submission origin/main && git push origin v1-submission`.
3. Seed the tasks: `scripts/v2-seed-tasks.sh` (once, from one laptop).
4. Stop each agent's old loop and paste the new prompt.
5. At CP2 (about 22:00), start on the UI in `web/`. Tell the Platform agent in the chat which files you're taking, so it stays out of them.
6. Before freeze: approve any `needs-human` items; record the 2-minute video from the demo above.
