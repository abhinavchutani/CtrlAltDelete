#!/usr/bin/env bash
# Create the 14 Navigator v2 task issues (docs/V2_AGENT_WORKFLOW.md) with labels and real dependency numbers.
# Run ONCE, by a human, from the main checkout:  scripts/v2-seed-tasks.sh
# Add --dry-run to print the titles without creating anything.
set -euo pipefail
cd "$(dirname "$0")/.."

DRY=0
[ "${1:-}" = "--dry-run" ] && DRY=1
DOC="Spec: docs/V2_ARCHITECTURE.md · tasks and done-when: docs/V2_AGENT_WORKFLOW.md · adaptation ideas: docs/RISK_MITIGATION_AND_ADAPTATION.md"
COUNT=0
# bash 3.2 (macOS) has no associative arrays: store issue numbers in variables N_V2_1, N_V2_5, ...
varname() { echo "N_${1//-/_}"; }

# task KEY TRACK "title" "depends (space-separated keys)" "G-box" "body"
task() {
  local key="$1" track="$2" title="$3" deps="$4" gbox="$5" body="$6" dep_txt="none" d v kv
  kv="$(varname "$key")"
  if [ -n "$deps" ]; then
    dep_txt=""
    for d in $deps; do v="$(varname "$d")"; dep_txt+="#${!v:-?} ($d) "; done
  fi
  local full="$body

**Depends on:** ${dep_txt}
**Closes:** ${gbox}
${DOC} (section ${key})"
  if [ "$DRY" = 1 ]; then
    printf -v "$kv" '%s' "$key"; COUNT=$((COUNT+1)); echo "[dry-run] track:$track  $title  (depends: $dep_txt)"; return
  fi
  local url
  url="$(scripts/agent-chat.sh new-task "$title" "$full" "$track")"
  printf -v "$kv" '%s' "${url##*/}"; COUNT=$((COUNT+1))
  echo "#${!kv}  $title"
}

task V2-1 app "[P0] v2 contract: api/schemas.py, API skeleton + mock fixtures, serve.duckdb snapshot, guard test" "" "G6" \
"Write api/schemas.py exactly as in V2_ARCHITECTURE, every endpoint in api/main.py, API_MOCK=1 fixtures, src/serve_db.py, Makefile targets (snapshot, v2, api, web, v2-check), out/v1_manifest.json + tests/test_v2_guard.py, exported openapi.json. Fixtures include hazards on alerts, a hedge frontier, pathway items, board rows and adaptation options.
**Done when:** pytest validates every fixture against its schema; API_MOCK=1 make api serves /api/health; HANDOFF in chat lists the endpoints. Ship in the first run: both other lanes wait on it."

task V2-5 C "[P0] v2 prediction: ScenarioSpec, engine, cube, 6 presets" "" "G7" \
"p_spec (lever bounds), p_engine (load_context, simulate(spec) -> SimResult, lever -> c_ensemble/c_euro hooks), p_cube (region and farm x year, € bands), p_presets (6 presets -> out/v2/). No formal dependency so you can start now: return dicts shaped like V2_ARCHITECTURE, then import api.schemas once V2-1 merges.
**Done when:** python -m src.p_presets writes all 6; GET /api/scenario/current_plan_ssp245 is a valid SimResult; 2026 SE pea is a bad year; per-preset runtime in the PR."

task V2-6 C "[P0] v2 prediction: weather frames for the map" "" "G7" \
"p_weather: a WeatherFrame per climate x year for the 84 cells (historical 1991-2026, each SSP to 2060): Tmax and rain anomalies vs 1991-2020, drought index from the c_features bucket, hot days at pea flowering. Precomputed in make v2. Starts now; uses api.schemas once V2-1 merges.
**Done when:** /api/weather?climate=ssp245&year=2035 is valid and < 200 ms; 2026 shows the Swedish drought."

task V2-9 A "[P0] v2 retrieval: catalog, read-only SQL, docs search, offline ask" "" "G7" \
"r_catalog (cards from DATA_DICTIONARY + DuckDB schema -> out/v2/catalog.json), r_sql (SELECT only, read-only, allow-list, 500 rows, 5 s), r_docs (extends e_tools.search_frameworks), r_agent.ask -> AskOut with offline routes for the 5 demo questions. No formal dependency so you can start now: return dicts shaped like V2_ARCHITECTURE, then import api.schemas once V2-1 merges.
**Done when:** each demo question returns answered + evidence from python -m src.r_agent; a write statement is refused (test)."

task V2-12 A "[P0] v2 adaptation options KB (kb/adaptation_options.csv) + options tool" "" "G7" \
"The 20 options in RISK_MITIGATION section 7 with the section 6 side-effect columns and the lever for the 5 the engine can re-run; reviewed_by empty (humans only). r_options.options(hazard, crop) as an API endpoint and a copilot tool.
**Done when:** every row validates against AdaptationOption; /api/options?hazard=H2&crop=pea lists A04 and A06 first; 'what can we do about heat at flowering?' answers from the KB with its source."

task V2-2 app "[P0] v2 React skeleton on fixtures (map, timeline, alerts, meters, ask, spec chips)" "V2-1" "G6" \
"Vite + React + TS in web/ per the V2_ARCHITECTURE layout: generated types, react-query hooks, zustand store, deck.gl map (parcels, farms, weather cells), timeline with play/scrub and alert dots, AlertPopup, Meters, SpecChips/LeverEditor/ScenarioPicker, AskPanel, HedgeChart, PathwaysGantt, DecisionBoard + DecisionDialog, synthetic banner. Unstyled: styling only via theme/tokens.css; logic out of components.
**Done when:** make web shows everything on fixtures; npm run build and tsc --noEmit pass; screenshots in the PR."

task V2-7 C "[P1] v2 prediction: critical/notable alerts, better option, meters" "V2-5" "G7 G8" \
"p_alerts (critical/notable rules, cap 12, kind from the dominant stress feature, suggested_lever, evidence), p_compare (~10-combination grid -> BetterOption), rule-based confidence with reasons.
**Done when:** current_plan_ssp585 has 4-12 alerts incl. one critical and the 'bad-year odds pass 1 in 4' marker; texts built only from computed values; a test pins the thresholds."

task V2-8 C "[P1] v2 prediction: text -> ScenarioSpec and live /api/simulate" "V2-5" "G8" \
"p_parse.parse(text) -> IntentOut: LLM path with the ScenarioSpec JSON schema via e_llm, plus an offline keyword/number path for the 6 demo phrasings; unknown asks go to problems, never invented. Live /api/simulate on the warm context, < 15 s, region-level fallback.
**Done when:** a test checks 12 phrasings; the measured simulate time is in the PR."

task V2-13 C "[P1] v2 prediction: sourcing hedge frontier + adaptation pathways (tipping and decide-by years)" "V2-5 V2-12" "G8" \
"p_hedge: FI share 0-100 % in 5 pp steps -> expected and CVaR10 tail loss bands over the ensemble years, today and best marked (re-implement the c_euro.rebalance loss table, don't edit it). p_pathways: tipping year = first year the 10-year rolling bad-year share passes 1 in 4 on the weather path (checked vs the 2041-60 ensemble), decide-by = tipping - max lead time per KB option, signpost text.
**Done when:** /api/hedge?climate=ssp245 and /api/pathways/current_plan_ssp585 are valid; SE_SKANE pea under ssp585 has a tipping year and the heat-tolerant variety a decide-by year; a test pins threshold and window."

task V2-10 A "[P1] v2 retrieval: Excel reports with a Sources sheet" "V2-9" "G7" \
"r_report: templates deliveries_by_farm_year, energy_by_site_month, farm_yield_history, inventory_summary, export_query; data sheet + Sources sheet; out/v2/reports/{id}.xlsx; /api/report/{id}. Add openpyxl to requirements.txt (say so in the PR).
**Done when:** 'Build me the 2024 energy report by site and month' returns a report in AskOut and a test reads both sheets back."

task V2-11 A "[P1] v2 retrieval: LLM tool loop with number post-check + 15-question eval" "V2-9" "G8" \
"Tool loop over catalog_search, run_sql, search_docs, query_results, make_report, reusing e_agent.finish's post-check and not_in_data. Eval set of 15 questions with deterministic SQL answers -> out/v2/ask_eval.json.
**Done when:** with an LLM key >= 12/15 pass; without a key the 5 offline routes still pass."

task V2-14 A "[P1] v2 decision board with expert approval log" "V2-7 V2-12" "G8" \
"r_board: rows per scenario (critical alerts first, max 8) joining alert, best options (simulated first, then no-regret), decide-by (from V2-13 when it lands), owner by decision window, evidence. Decisions append to out/v2/decisions.jsonl; decided_by only from the request, never from code.
**Done when:** /api/board/current_plan_ssp245 returns rows; a POST decision round-trips and survives an API restart; a decision without decided_by is refused (test)."

task V2-3 app "[P1] v2 wiring: real layers, intent router, voice, geo endpoints" "V2-2 V2-5 V2-9" "G8" \
"/api/intent via src.p_parse; /api/geo/parcels (simplified, gzip) and /api/geo/farms; useSpeech.ts (Web Speech API, text fallback); prediction context loaded once in the API lifespan with a warming flag.
**Done when:** with API_MOCK=0 the 6-step demo in V2_AGENT_WORKFLOW runs end to end on presets."

task V2-4 docs "[P2] v2 docs: README section, METHOD_NOTE paragraph, demo script, Microsoft mapping" "V2-3" "G8" \
"README v2 run commands, one v2 paragraph in METHOD_NOTE.md, the demo script in docs/pitch/, the mapping slide text.
**Done when:** a clean checkout runs make snapshot v2 api web from the README alone."

[ "$DRY" = 1 ] || scripts/agent-chat.sh say "STATUS: v2 tasks seeded ($COUNT). Plan: docs/V2_ARCHITECTURE.md + docs/V2_AGENT_WORKFLOW.md. to:all restart your loop with the v2 prompt; platform ships the V2-1 contract first."
