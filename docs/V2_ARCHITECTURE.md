# Navigator v2: architecture (Prediction layer + Retrieval layer + React app)

> Decided 7 Nov 2026 by the team after the Apetit Q&A. v1 (Tracks A, C, E, the CSVs, the audit trail) is **done and frozen**; v2 builds a product on top of it. `AGENTS.md` rules still apply in full. Where this file and older docs disagree about v2, this file wins. The agent workflow is in [V2_AGENT_WORKFLOW.md](V2_AGENT_WORKFLOW.md).

## What Apetit told us (the two problems)

1. **Scattered data.** Answers about the past live in ERP, many Excel files and paper diaries. Every report is rebuilt by hand. They want to ask a question and get the answer, with its source, plus the report file, without manual work.
2. **Climate risk to crops.** The 2026 Swedish pea drought hurt. Once peas are sown little can be done, so they want to see the risk years ahead, how big it is, and what to do about it (irrigation, sourcing split, sowing, new heat-tolerant varieties, which take years to breed).

They said: good-enough beats perfect, accuracy percentages don't matter to them, profit comes first but customers demand emission cuts.

**The adaptation answer** comes from [RISK_MITIGATION_AND_ADAPTATION.md](RISK_MITIGATION_AND_ADAPTATION.md): "nothing can be done once the peas are sown" is true for the farmer, not for Apetit. Apetit acts in three **decision windows** (strategic 1–15 years, pre-season, in-season/post-harvest). Every risk is tagged with one of seven **hazards** (H1 drought, H2 heat at flowering, H3 waterlogging, H4 harvest rain, H5 season length, H6 blight, H7 pollen beetle), and the hazard picks the adaptation options. v2 builds four of that doc's ideas: hazard-tagged alerts, the **sourcing hedge frontier** (§4.1), **adaptation pathways** with tipping years and decide-by years (§4.2), and the **decision board** with expert approval (§4.3), plus the options knowledge base (§7) and its side-effect labels (§6). Its §5 extras are out of scope for this weekend. Where the two docs disagree, this file wins (for example: € as bands, at most 12 alerts).

## The product: one app, two layers, one microphone

```
 React app (web/)  ── map + timeline + alerts + ask panel + voice ──────────────────────────┐
      │ HTTP JSON (contract = api/schemas.py)                                               │
 FastAPI (api/)  ── /api/intent → routes to one of two layers                               │
      │                                                                                     │
      ├── RETRIEVAL layer (src/r_*)          "what happened / show me / build the report"   │
      │     catalog_search → run_sql (read-only) → search_docs → make_report (.xlsx)        │
      │     LLM picks tools and phrases; numbers come only from tool results (post-check)   │
      │                                                                                     │
      └── PREDICTION layer (src/p_*)         "what if we … / what happens to …"             │
            text → ScenarioSpec (LLM fills a form, never a number)                          │
            ScenarioSpec → engine (c_ensemble / c_euro transforms) → scenario cube          │
            cube → alert rules (critical + notable only) → timeline events                  │
            cube → weather layer (from the pack's daily weather)                            │
            cube + options KB → hedge frontier, pathways (decide-by years), decision board  │
                                                                                            │
 Frozen v1 data: out/serve.duckdb (snapshot of navigator.duckdb, read by both layers) ─────┘
```

**The one rule still holds:** deterministic code computes every number. The LLM only routes, fills the ScenarioSpec form, picks tools and phrases answers.

## Repo decision: same repo, v1 frozen

We build v2 **in this repo**, not a clean one:
- The engine v2 needs (`c_ensemble.context/production`, `c_euro` transforms, `e_tools`, `e_llm`, `lineage`) lives here. A new repo would copy and fork it.
- The jury looks at one repo; v1's audit trail is part of the v2 story.
- The agent machinery (chat, tasks, CI, worktrees) already works here.

**How Track A stays fixed:**
1. A human tags the current main: `git tag v1-submission && git push origin v1-submission`.
2. `make snapshot` copies `out/navigator.duckdb` → `out/serve.duckdb`. **v2 code reads only `serve.duckdb`** (env `SERVE_DB`). It never runs `make a/c/e` and never writes to `issues`, `corrections`, `results` or `lineage`. (This also avoids the DuckDB lock the Streamlit app hits.)
3. v2 PRs must not change any `out/*_submission.csv` or `src/a_*`, `src/c_*`, `src/e_*` files. A small test (`tests/test_v2_guard.py`) checks the CSVs against `out/v1_manifest.json` (sha256).
4. Track A/C bugs found during v2: a separate task, a human approves it.

## Folder map (new areas)

| Area | Owner lane | Files |
|---|---|---|
| Prediction layer | `C` (climate-agent) | `src/p_spec.py`, `src/p_parse.py`, `src/p_engine.py`, `src/p_cube.py`, `src/p_alerts.py`, `src/p_weather.py`, `src/p_compare.py`, `src/p_hedge.py`, `src/p_pathways.py`, `src/p_presets.py`, `tests/test_p_*.py` |
| Retrieval layer | `A` (abhinav-claude) | `src/r_catalog.py`, `src/r_sql.py`, `src/r_docs.py`, `src/r_report.py`, `src/r_agent.py`, `src/r_options.py`, `src/r_board.py`, `tests/test_r_*.py` |
| Adaptation knowledge base | `A`, reviewed by `C` | `kb/adaptation_options.csv` (committed; `data/` is git-ignored) |
| API + contract | `platform` (noa-claude) | `api/main.py`, `api/schemas.py`, `api/routes/*.py`, `api/fixtures/*.json`, `tests/test_api_*.py` |
| React app | `platform` | `web/` (Vite + React + TypeScript) |
| Shared | `platform`, announce first | `Makefile` (new targets only), `src/serve_db.py`, `.gitignore` |

v2 never edits v1 files (`src/a_*`, `src/c_*`, `src/e_*`, `src/lineage.py`, `app/`). It **imports** them.

## The contract (`api/schemas.py`, Pydantic v2)

This is the only hard dependency between the three lanes. Platform writes it first (task V2-P0-1) with fixtures; the other two lanes return exactly these shapes. Changing a shape after CP1 needs all three agents to agree in the chat.

```python
Door = Literal["ask", "simulate"]
Climate = Literal["ssp126", "ssp245", "ssp585"]
Region = Literal["FI_SW", "SE_SKANE"]
Crop = Literal["pea", "potato", "carrot", "spinach", "wheat", "barley", "oats", "turnip_rape", "grass_ley", "fallow"]
Severity = Literal["critical", "notable"]
Confidence = Literal["high", "medium", "low"]
EurBand = Literal["< €50k", "€50–100k", "€100–250k", "€250k–1M", "> €1M"]
Hazard = Literal["H1", "H2", "H3", "H4", "H5", "H6", "H7"]   # drought, heat at flowering, waterlogging, harvest rain, season length, blight, pollen beetle
Window = Literal["strategic", "pre_season", "in_season"]
Simulated = Literal["simulated", "simulated_with_caveat", "assumption"]   # RISK_MITIGATION §9: say which, out loud

# ── levers (the only things a spoken idea can change) ──────────────
class Irrigate(BaseModel):        type: Literal["irrigate"]; crop: Literal["pea", "potato"]; target: Literal["drought_exposed", "all"] = "drought_exposed"
class EarlierSowing(BaseModel):   type: Literal["earlier_sowing"]; crop: Crop | Literal["all"] = "all"
class RegionSplit(BaseModel):     type: Literal["region_split"]; crop: Literal["pea"] = "pea"; fi_share: float  # 0.2–0.9
class HeatTolerant(BaseModel):    type: Literal["heat_tolerant_variety"]; crop: Literal["pea"] = "pea"; from_year: int = 2030; penalty_cut: float = 0.3  # 0–0.6, an ASSUMPTION
class CropArea(BaseModel):        type: Literal["crop_area"]; crop: Crop; region: Region; change_pct: float  # −50…+50
Lever = Annotated[Irrigate | EarlierSowing | RegionSplit | HeatTolerant | CropArea, Field(discriminator="type")]

class ScenarioSpec(BaseModel):
    climate: Climate = "ssp245"
    horizon_end: Literal[2031, 2040, 2050, 2060] = 2040
    levers: list[Lever] = []          # [] = their current plan
    label: str | None = None          # short human name, e.g. "Irrigate dry pea fields"

# ── /api/intent ────────────────────────────────────────────────────
class IntentIn(BaseModel):  text: str
class IntentOut(BaseModel):
    door: Door
    text: str
    spec: ScenarioSpec | None = None  # when door == "simulate"
    heard: list[str] = []             # chips shown back: "climate: middle path", "irrigate dry pea fields"
    problems: list[str] = []          # out-of-range values, unknown levers → shown, never silently fixed

# ── prediction ─────────────────────────────────────────────────────
class EvidenceRef(BaseModel): kind: Literal["result", "lineage", "weather", "table_row", "doc", "assumption"]; ref: str; label: str

class Alert(BaseModel):
    id: str
    year: int
    month: int | None = None          # stage month, e.g. 6 = pea flowering
    region: Region
    crop: Crop | None = None
    severity: Severity
    kind: Literal["drought_flowering", "heat_flowering", "waterlogging", "wet_harvest", "blight_weather",
                  "beetle_weather", "supply_shortfall", "risk_threshold", "assumption"]
    hazard: Hazard | None = None      # the dominant driver; picks the options from the KB
    title: str                        # template text, e.g. "Pea flowering drought, SE_SKANE"
    why: str                          # template text built from numbers in code
    eur_at_risk: EurBand | None = None
    suggested_lever: Lever | None = None
    evidence: list[EvidenceRef] = []

class RegionYear(BaseModel):
    region: Region; crop: Crop; year: int
    change_vs_baseline_pct: float     # rounded to whole %
    eur_at_risk: EurBand
    bad_year: bool                    # < 80 % of the 1991–2020 mean

class Meters(BaseModel):
    eur_at_risk_per_year: EurBand     # mean over the horizon
    vs_current_plan: Literal["better", "same", "worse"]
    co2e_direction: Literal["lower", "same", "higher"]   # replacement-import emissions
    confidence: Confidence
    confidence_why: list[str]         # e.g. "near-term years", "assumption: heat-tolerant variety"

class BetterOption(BaseModel): spec: ScenarioSpec; saves: EurBand; why: str

class SimResult(BaseModel):
    scenario_id: str                  # hash of the spec; presets have readable ids
    spec: ScenarioSpec
    years: list[int]                  # 2026 … horizon_end
    regions: list[RegionYear]
    farms_url: str                    # /api/cube/{scenario_id}/farms → FarmYear rows
    alerts: list[Alert]               # critical + notable only, at most 12
    meters: Meters
    better: BetterOption | None = None
    synthetic: bool = True            # UI must show the "synthetic data" banner

class FarmYear(BaseModel): farm_id: str; year: int; change_vs_baseline_pct: float; risk: Literal["ok", "watch", "bad"]

# ── adaptation (RISK_MITIGATION_AND_ADAPTATION.md) ─────────────────
class AdaptationOption(BaseModel):          # one row of kb/adaptation_options.csv
    option_id: str; hazards: list[Hazard]; crops: list[str]; option: str; window: Window
    lead_time_yrs: tuple[int, int]; cost_level: Literal["low", "low_med", "med", "high"]
    ghg: Literal["better", "same", "worse"]; nutrients: Literal["better", "same", "worse", "depends"]
    water: Literal["better", "same", "worse"]
    robustness: Literal["no_regret", "scenario_dependent", "maladaptive", "reactive"]
    simulated: Simulated; lever: Lever | None = None   # set when the engine can re-run it
    source_name: str; source_url: str | None = None; reviewed_by: str | None = None   # only a human fills reviewed_by

class HedgePoint(BaseModel):                # one Finland share on the frontier
    fi_share: float                         # 0.00–1.00 of contracted pea volume
    expected_loss: EurBand                  # mean € at risk per year
    tail_loss: EurBand                      # mean of the worst 10 % of years (CVaR10)
    is_now: bool; is_best: bool
class Hedge(BaseModel): climate: Climate; points: list[HedgePoint]; why: str   # e.g. "Moving 15 pp to FI_SW cuts the 1-in-10-year loss from €250k–1M to €100–250k"

class PathwayItem(BaseModel):               # one bar in the pathways Gantt
    crop: Crop; region: Region; climate: Climate
    threshold: str                          # e.g. "bad-year odds > 1 in 4"
    tipping_year: int | None                # None = not crossed before horizon_end
    option_id: str; option: str
    decide_by: int | None                   # tipping_year − lead time (max); None when no tipping
    signpost: str                           # e.g. "3 seasons in a row with > 5 hot days at pea flowering in SE_SKANE"
    simulated: Simulated

class BoardRow(BaseModel):                  # one line of the decision board (§4.3)
    row_id: str; scenario_id: str
    risk: str; crop: Crop; region: Region; hazard: Hazard
    eur_at_risk: EurBand; eur_tail: EurBand | None = None
    action: str; option_ids: list[str]; owner: str; decide_by: int | None
    trigger: str; evidence: list[EvidenceRef]; robustness: str; simulated: Simulated
    status: Literal["pending", "approved", "edited", "rejected"] = "pending"
    decided_by: str | None = None; decided_at: str | None = None; reason: str | None = None
class Decision(BaseModel): status: Literal["approved", "edited", "rejected"]; decided_by: str; reason: str; action: str | None = None

class WeatherCell(BaseModel):
    cell_id: str; region: Region; lat: float; lon: float      # 0.25° square around (lat, lon)
    tmax_anom_c: float                # growing season vs 1991–2020
    precip_anom_pct: float
    drought_index: float              # 0–1, from the stage soil-water bucket
    hot_days_flowering: int
class WeatherFrame(BaseModel): climate: Climate | Literal["historical"]; year: int; cells: list[WeatherCell]

# ── retrieval ──────────────────────────────────────────────────────
class AskIn(BaseModel): question: str; history: list[dict] = []
class AskOut(BaseModel):
    status: Literal["answered", "not_in_data"]
    answer_md: str
    table: dict | None = None         # {"columns": [...], "rows": [[...]]}, at most 50 rows
    evidence: list[EvidenceRef]       # table + record keys, file + row, or doc + section
    report: dict | None = None        # {"report_id", "filename", "url"} when a file was made
    pending_approval: bool = False    # any draft result used
```

**Endpoints:**

| Method | Path | Returns | Owner of the logic |
|---|---|---|---|
| POST | `/api/intent` | `IntentOut` | P (`p_parse.parse`) + platform router |
| POST | `/api/ask` | `AskOut` | R (`r_agent.ask`) |
| GET | `/api/report/{report_id}` | the .xlsx file | R (`r_report`) |
| GET | `/api/scenarios` | preset list `[{scenario_id, label, spec}]` | P (`p_presets`) |
| GET | `/api/scenario/{scenario_id}` | `SimResult` | P |
| POST | `/api/simulate` | `SimResult` (body: `ScenarioSpec`) | P (`p_engine.simulate`) |
| GET | `/api/cube/{scenario_id}/farms?year=` | `list[FarmYear]` | P |
| GET | `/api/weather?climate=&year=` | `WeatherFrame` | P (`p_weather`) |
| GET | `/api/hedge?climate=` | `Hedge` | P (`p_hedge`) |
| GET | `/api/pathways/{scenario_id}` | `list[PathwayItem]` | P (`p_pathways`) |
| GET | `/api/options?hazard=&crop=` | `list[AdaptationOption]` | R (`r_options`) |
| GET | `/api/board/{scenario_id}` | `list[BoardRow]` | R (`r_board`) |
| POST | `/api/board/{row_id}/decision` | `BoardRow` (body: `Decision`) | R (`r_board`) |
| GET | `/api/geo/farms` | GeoJSON points (farm_registry) | platform |
| GET | `/api/geo/parcels` | simplified GeoJSON polygons, gzip | platform |
| GET | `/api/health` | `{ok, mock, serve_db, llm}` | platform |

`API_MOCK=1` serves `api/fixtures/*.json` for every endpoint, so the web app works before the layers exist.

## Prediction layer (lane C)

**Engine.** `p_engine` builds one `c_ensemble.Context` at API start-up (fitted models + weather, warm in memory) and maps each lever to the transforms we already use:

| Lever | Engine hook |
|---|---|
| `irrigate` | `pre_finish=c_euro.with_irrigation(parcels)` (`drought_exposed` = `c_euro.exposed_parcels`) |
| `earlier_sowing` | `st=c_ensemble.stage_delta(con, c_euro.earlier_sowing_crops())` |
| `region_split` | re-weights the contracted pea volume between regions (as `c_euro.rebalance`) |
| `heat_tolerant_variety` | scales the pea hot-days-at-flowering features by `1 − penalty_cut` from `from_year`; flagged `assumption` |
| `crop_area` | scales that crop's area in the parcel mix |

**Years and weather.**
- 2026 is the last observed year (the Swedish drought); it is the timeline's start.
- 2027–2031 use the planned parcel mix; later years hold the 2031 mix.
- The weather for each year is the pack's daily weather for the chosen SSP: **one plausible weather path**, labelled as such. Alerts say "on this weather path", never "will happen".
- Confidence comes from rules, not percentages: `high` for 2027–31 with no assumption levers, `medium` to 2040, `low` beyond 2040 or with any assumption lever or a lever outside the training range (for example irrigating farms that never irrigated). The delta-method ensemble (`c_ensemble`) gives the "1 bad year in N" odds that the meter's `confidence_why` can quote.

**€ at risk** = shortfall t × contract price × (1 + replacement premium), as in `c_euro`. The exact € is computed but **the API only sends a band** (`EurBand`).

**Alerts (critical and noteworthy only).** `p_alerts` runs rules over the cube; nothing below `notable` is sent.
- `critical`: one region × crop × year with € at risk ≥ €250k, **or** production < 70 % of contracted, **or** the pathway tipping year (bad-year odds pass 1 in 4, the "start now" marker; the same rule as `p_pathways`).
- `notable`: € at risk ≥ €100k, **or** a bad year (< 80 % of the 1991–2020 mean) on a contract crop.
- The `kind` is the stress feature that drove the drop most (drought at flowering, heat at flowering, waterlogging, wet harvest, blight, beetles), from the model's feature contributions.
- At most 2 per year and 12 per scenario, highest € first. Each carries a `suggested_lever` (the action from `p_compare` that cuts it most) and evidence refs.
- Thresholds are constants at the top of `p_alerts.py`, so we can tune them for the demo.

**"Is there something better?"** `p_compare` runs a small fixed grid (about 10 lever combinations) for the chosen climate and returns the best one on € at risk, with its CO2e direction. Presets precompute it; custom runs reuse the preset grid for that climate.

**Hazard tags.** The alert's `kind` maps to a hazard: drought → H1, heat at flowering → H2, waterlogging → H3, wet harvest → H4, short season → H5, blight → H6, beetles → H7. `supply_shortfall` and `risk_threshold` alerts take the hazard of the stress feature that cost the most that year.

**Sourcing hedge frontier** (`p_hedge`, RISK_MITIGATION §4.1). We reuse the per-year pea loss table that `c_euro.rebalance` builds (re-implemented in `p_hedge`, not edited in `c_euro`). For each Finland share from 0 to 100 % in 5 pp steps it computes the expected € loss and the **tail loss** (CVaR10, the mean of the worst 10 % of years) over the delta-method ensemble years. It marks today's share and the best one (lowest tail loss among the shares within 5 % of the lowest expected loss). Both are sent as bands, and the `why` sentence is built from them.

**Adaptation pathways** (`p_pathways`, RISK_MITIGATION §4.2), per contract crop (pea, potato) × region × climate:
1. **Threshold:** bad-year odds > 1 in 4 (a constant).
2. **Tipping year:** the first year the 10-year rolling share of bad years on the weather path passes it. We check it against the ensemble odds for 2041–60, and when the two disagree the item says "indicative".
3. **Decide-by** = tipping year − the option's maximum lead time, for each matching option in the KB (hazard + crop). A decide-by year already past shows as "now".
4. **Signpost:** a template sentence from the driving hazard's feature (hot days at flowering, flowering drought index, and so on).

On the timeline these show as a second row of markers ("decide by 2029: heat-tolerant pea"), separate from the alert dots.

**Presets** (`make v2` writes them to `out/v2/`, not committed):
`current_plan_{ssp126,ssp245,ssp585}`, `irrigate_dry_pea_ssp245`, `split_70_30_ssp245`, `heat_tolerant_pea_ssp585`.

**Weather layer.** `p_weather` turns the pack's daily weather into one `WeatherFrame` per climate × year (84 cells): growing-season Tmax and rain anomalies vs 1991–2020, the drought index from the soil-water bucket in `c_features`, and hot days at pea flowering. That's what the map shows for "the weather" (no live feed, no clouds).

**Speed targets.** Preset load < 300 ms. A custom `/api/simulate` < 15 s warm. If it's slower, run custom specs at region × year level and reuse the preset's farm layer.

## Retrieval layer (lane A)

Answers "what happened" questions over everything v1 loaded (≈30 pack files in many formats, now in one DuckDB) and builds the report file.

| Tool | Does | Notes |
|---|---|---|
| `catalog_search(query)` | Finds tables and columns | Built from `DATA_DICTIONARY.md` + the DuckDB schema: table, columns, description, years covered, source file, row count |
| `run_sql(sql)` | Runs the query | `SELECT` only, on a `read_only` connection to `serve.duckdb`, allow-listed tables (`raw_*`, `clean_*`, `results`, `lineage`, `corrections`), 500-row cap, 5 s timeout. Returns rows plus the source file and record keys where a table has them |
| `search_docs(query)` | Finds passages | Reuses `e_tools.search_frameworks`, extended to `METHOD_NOTE.md`, `REASONING_LOG.md` and `corrections.csv` reasons |
| `query_results(...)` | Approved inventory and risk numbers | Reuses `e_tools.query_results` |
| `make_report(template, params)` | Writes an .xlsx | openpyxl; a data sheet plus a "Sources" sheet (query, tables, record keys, generated-at, "synthetic data"). Templates: `deliveries_by_farm_year`, `energy_by_site_month`, `farm_yield_history`, `inventory_summary`, and `export_query` for any table the agent just built |

**Answer rules** (reuse `e_agent.finish` and its number post-check): every number in `answer_md` must match a tool result, every answer carries evidence, and when no tool result fits the answer is "not in the data" plus what's needed. Offline mode (no LLM key) answers a fixed set of demo questions through deterministic routes, so the demo never depends on a key.

**Adaptation options KB** (`kb/adaptation_options.csv`, `r_options`). Seeded from the 20 rows in RISK_MITIGATION §7, with the §6 side-effect columns. Lead times and costs are **indicative assumptions**, so `reviewed_by` stays empty until an Apetit agronomist fills it, and the UI shows "not yet reviewed". Each row that the engine can re-run carries its `lever` (A01 → `irrigate`, A06 → `earlier_sowing`, A07 → `region_split`, A04 → `heat_tolerant_variety`, A08 → `crop_area` on clay). `options(hazard, crop)` is both an API endpoint and a copilot tool, so "what can we do about heat at flowering?" is answered from the KB with its source.

**Decision board** (`r_board`, RISK_MITIGATION §4.3). For a scenario, one row per critical alert (plus the top notable ones, at most 8 rows). Each row joins the alert, its hazard's best options (simulated ones first, then no-regret), the pathway decide-by year, the owner from the option's window (strategic → "R&D, Sourcing, CFO"; pre-season → "Agronomy, Procurement"; in-season → "Procurement, Supply chain"), and the evidence. Decisions are appended to `out/v2/decisions.jsonl` (never to v1's tables). `decided_by` is typed by a human in the UI; agents never fill it.

**Demo questions it must answer:** pea deliveries from Swedish farms in 2021 vs 2026; which farms reported peat but were calculated as mineral soil; energy use per site per month in 2024 as a report; what the guarantee-of-origin rule is (with the framework passage); farm F0123's yield history.

## React app (platform lane): a skeleton the human restyles

**Stack:** Vite, React 18, TypeScript, `deck.gl` 9 (`@deck.gl/react`, `@deck.gl/layers`), `react-map-gl` + `maplibre-gl` (basemap style URL in `web/.env`, works with no basemap), `@tanstack/react-query`, `zustand`, `openapi-typescript` for the types. **No component library and minimal CSS**, so the human can design it later.

```
web/src/
  api/          client.ts (fetch wrapper), types.gen.ts (generated, never hand-edited), hooks.ts (react-query hooks)
  state/        store.ts: scenarioId, year, playing, layer, selection, door, pendingSpec
  features/
    map/        MapView.tsx; layers/*.ts are pure functions (data, state) → deck.gl layer
                parcels: extruded polygons, colour = change vs baseline; farms: columns; weather: cell squares
    timeline/   Timeline.tsx (2026 → horizon, play/scrub), EventDot.tsx (one per alert)
    alerts/     AlertList.tsx, AlertPopup.tsx (title, why, € band, suggested lever → "try it")
    meters/     Meters.tsx (€ band, vs plan, CO2e direction, confidence + why)
    simulate/   SpecChips.tsx (what we heard, editable), LeverEditor.tsx, ScenarioPicker.tsx
    ask/        AskPanel.tsx, EvidenceChips.tsx, ResultTable.tsx, ReportButton.tsx
    hedge/      HedgeChart.tsx (frontier: FI share vs expected and tail loss bands; today and best marked)
    pathways/   PathwaysGantt.tsx (per crop × region: tipping year, decide-by bars, signposts)
    board/      DecisionBoard.tsx, DecisionDialog.tsx (approve / edit / reject + name + reason)
    voice/      useSpeech.ts (browser Web Speech API; fallback: text box), MicButton.tsx
  theme/        tokens.css (colours, spacing, fonts as CSS variables, light + dark)
  App.tsx       layout only
```

**Rules that keep the UI swappable:**
- Logic lives in hooks, the store and the layer functions; components only render props. Restyling never touches data code.
- Colours, sizes and fonts come only from `theme/tokens.css`.
- Every component works on fixtures (`API_MOCK=1`) and has an empty, loading and error state.
- The "synthetic data, not Apetit's real figures" banner is always visible.

**Flow:** the mic or text box → `/api/intent` → `ask`: AskPanel shows answer, table, evidence, report button. `simulate`: SpecChips show what was heard → the user confirms → `/api/simulate` → map, timeline dots, meters and alerts update. Clicking an alert's suggested lever adds it to the spec and re-runs.

## Run it

```bash
make snapshot                       # out/navigator.duckdb → out/serve.duckdb
make v2                             # presets, weather frames, catalog → out/v2/
make api                            # uvicorn api.main:app --port 8000   (API_MOCK=1 make api for fixtures)
make web                            # cd web && npm install && npm run dev  (proxy /api → :8000)
make v2-check                       # pytest for p_/r_/api + `npm run build` + typecheck
```

## Microsoft mapping (for the slide)

| v2 piece | Apetit stack |
|---|---|
| serve.duckdb + catalog | Fabric Lakehouse + its semantic model |
| Retrieval tools | Copilot Studio agent / Azure AI Foundry agent calling the same tools; AI Search for docs |
| Prediction engine | Azure ML endpoint |
| FastAPI | Azure Functions / Container Apps |
| React app | Static Web App, or embedded in Teams / Power BI |
| Speech | Azure AI Speech |
| Paper diaries (future) | Azure Document Intelligence → the v1 review queue |
