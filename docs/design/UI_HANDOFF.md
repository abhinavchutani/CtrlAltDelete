# UI handoff: "Field Radar" (branch `ui/design`)

**Goal image:** [field_radar_goal_v2.webp](field_radar_goal_v2.webp): calm dark satellite map with soft glows, View panel
(left), a plan panel (right), Explore years (bottom). History: v1 ([field_radar_goal.webp](field_radar_goal.webp)) was
too busy; v2 simplified it; **v3 (this) makes it useful** (human feedback, 2026-11-07): show the problems on the timeline
and stop at them, put the problem next to its pin with prominent solutions, run many simulations and say which plan is
best, show what the model is built on, show the weather on the map, and make the assistant an overlay that really
simulates.

## Run it
```
make snapshot && python -m src.p_presets && python -m src.p_weather      # once: out/serve.duckdb + out/v2
API_MOCK=0 ~/.navigator-venv/bin/python -m uvicorn api.main:app --port 8000
cd web && npm ci && npm run dev                                           # http://localhost:5173 (proxies /api)
```
On start the API warms the model (~10 s), then **prewarms** the default plan, the comparison grid and the default plan
search (~50 s in the background), so the first simulate (~0.5 s) and the plan finder (instant) answer at once.
In the Claude desktop app the servers are `navigator-api` / `navigator-web` (`.claude/launch.json`, git-excluded at the
root). The tour opens on a first visit (`fieldradar.tour.seen.v2` in localStorage); `?tour` or the **?** button replays it.

## What a visitor sees
1. **Overview (landing).** Hero: "On this weather path, €X–Y a year of contract-crop supply is at risk", the costly
   years, the alert causes counted, then **the best of N simulated plans** (saves, costly years before → after, holds in
   the other futures) with *Watch the years on the map*. **Built on the Apetit data pack**: counts from the data
   (`/api/provenance`) and the C1 backtest (trained ≤2023, tested 2024–26: 5.1 % vs 9.9 % for a farm-average guess).
   Then the chosen year at a glance, every problem ahead (*Show on map*), and More detail (meters, hedge, pathways, board).
2. **Map.** View panel (future, colour by, weather on/off, go to region). **Find the best plan** panel: best plan in
   words (saves, € at risk, years over €250k, worst year, other futures, cost level from the KB, CO2e, assumption
   note), *Show it on the map*, *All N plans*, and **Build your own plan** (irrigate pea/potato driest/all, sow earlier
   any crop, % pea from Finland, heat-tolerant pea from a year with an assumed cut, crop area ± % per region).
3. **Explore years.** A dot per problem year (hover: what, € band). **Playback stops at each problem**: it opens that
   year's worst alert and flies to the pin. The **problem card sits beside the pin**: month + region + crop, what
   happens, € at risk, the month's weather vs normal with Apr–Sep rain bars, **the model's pick** and every KB solution
   (cost, timing, lead time, robustness) with **Test it**: the effect on this problem (that year, region, crop) and over
   15 years, then *Apply on the map*. *Keep playing* resumes.
4. **Weather on the map** (`features/map/WeatherFx.tsx`): rain streaks, dry dust and a heat haze whose strength follows
   the API's weather for the region in view (the alert's month when one is open, else the season); a chip says it in
   numbers. Respects reduced motion.
5. **Assistant** (top-bar button): an overlay over the dimmed map. Ask the data; say a what-if → a **full simulation
   card** (€ at risk vs today's plan, the crop's harvest per year vs normal for both regions, today's plan dashed, the
   80 % bad-harvest line, CO2e, critical alerts, confidence); or *Find the best plan for me* → the plan finder live.

## How it is built
- **Plan finder** `src/p_search.py` (deterministic, no LLM): 11 singles (irrigate pea driest/all, irrigate potato,
  sow early all/pea, pea from Finland 50/60/70/80 %, heat-tolerant pea 2028/2030), then every combination (2+) of the
  best setting of each change that helped, ranked by mean € at risk a year; top 3 re-run under the other two climates.
  Exact € stay inside; bands, counts ("costly years" = €250k+) and words leave. Tests: `tests/test_p_search.py`.
- **API** (`api/insight.py`, routes in `api/main.py`, models in `api/schemas.py`): `POST /api/search` streams SSE
  (text/event-stream is not gzipped); one shared run per (climate, horizon), live for whoever joins, replayed after.
  `GET /api/provenance`, `GET /api/weather/months` (`src/p_season.py`, from `raw_weather_monthly`).
  `api/prediction.py`: `ENGINE_LOCK` (one engine run at a time; the context's DuckDB is shared), `ready()`, `context()`.
- **Web**: `state/search.ts` (stream reader; a replayed burst is paced 70 ms per plan so each arrives visibly),
  `features/plans/*`, `features/alerts/PinCard.tsx`, `features/chat/SimCard.tsx`, `features/map/WeatherFx.tsx`,
  `features/map/isolate.ts` (cards on the map block map gestures but let clicks through to React; the map ignores a
  click that began on a card). Playback stop lives in `features/timeline/useTimeline.ts` (mount it once: YearBar).
- Map rendering as in v2: deck.gl interleaved in MapLibre (fields never lag), farm glows + soft fields, GPU colour
  tweening, every year prefetched.

**Checked in the browser** (1360×1020): landing hero + provenance + tour (9 steps across both tabs), play → stops at
2028 Skåne drought, card beside the pin, Test it (model's pick: 2028 Skåne pea €250k–1M → €100–250k), plan finder panel,
assistant overlay (plan finder answer, what-if simulation card), rain in SW Finland 2040. `npm run build` passes;
`pytest -q` 317 passed, 4 skipped.

## Honest limits (say them in a demo)
- "Saves" is € at risk avoided **before the cost of the change**; the engine has no € costs, only the KB's cost level.
- Heat-tolerant pea is an **assumption** (penalty cut not measured); plans with it are labelled.
- One weather path per climate; the 2025 field mix and current management held for every year.

## Touched files owned by other agents (tell them in the PR)
- noa-claude: `api/main.py` (3 routes + prewarm call), `api/schemas.py` (new models, additive), `api/prediction.py`
  (`ENGINE_LOCK` around simulate, `ready()`, `context()`), `features/timeline/useTimeline.ts` (stop at problems,
  PLAY_MS 450), `api/hooks.ts` (prefetch, new hooks), `features/alerts/AlertPopup.tsx` (region names; now unused by the
  map, which uses PinCard). New dependency: `@deck.gl/mapbox@9.0.38`.

## Next
1. Phones / narrow windows: panels cover the map; make them bottom sheets.
2. Chat answer tables with long id columns are wide (`line_result_id`).
3. The plan search could add € costs per change once the KB has them, to rank by net benefit.
4. Rules that must stay: synthetic-data note always visible; € only as bands; no "decide by" years; numbers only from
   the API.

## Known open bugs (other lanes)
- `PathwaysGantt` (noa-claude): duplicate React keys (`A01-FI_SW-ssp245`, …). Fix: add the row index to the key.
- Decision board approval with a whitespace-only name → 500; row_id is positional (PR #114 comments).
- A knowledge item can be approved by its own contributor (PR #114 comments).
