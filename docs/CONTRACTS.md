# Shared contract: DuckDB tables, keys and outputs (v1)

This implements the "number + trail" contract in [SYSTEM_DESIGN.md](SYSTEM_DESIGN.md). **To change it:** open a PR that edits this file and the code in `src/lineage.py` together, then post a `HANDOFF` to `to:all`.

## Files and commands

| Path | What |
|---|---|
| `out/navigator.duckdb` | The one database (gitignored). The path comes from `NAVIGATOR_DB`; default `out/navigator.duckdb` |
| `out/*_submission.csv` | Auto-scored CSVs, named exactly as in the pack's `tasks/templates/` (committed) |
| `out/corrections.csv` | Export of the `corrections` table (committed) |
| `out/scores/*.json` | Dev scores from the pack's scorer (committed) |
| `out/cache/` | LLM call cache keyed by input hash (gitignored) |

**`make` targets:**

| Target | Builds |
|---|---|
| `make load` | The `raw_*` tables |
| `make a` | The A pipeline |
| `make c` | The C pipeline |
| `make e` | The E pipeline |
| `make app` | Runs Streamlit |
| `make all` | Every submission file from the unzipped pack |
| `make test` | The tests |

## Table naming

- **`raw_<name>`:** a pack file loaded untouched, plus a `record_key` column in the official A1 format where one exists.
- **`clean_<name>`:** the same table with the corrections applied (approved ones, or dev mode; see below).
- **Track-owned working tables** use a prefix:
  - **Data:** `a_`
  - **Climate:** `c_`
  - **Copilot:** `e_`

## The four shared tables

**`issues`**: one row per suspected data problem.

| column | type | notes |
|---|---|---|
| issue_id | VARCHAR | stable: `{rule_id}:{record_key}` |
| table_name | VARCHAR | pack table, e.g. `erp_purchase_lines` |
| record_key | VARCHAR | official A1 format |
| year | INTEGER | |
| issue_type | VARCHAR | one of the 18 A1 ISSUE_TYPES, or `observation` (never exported to A1) |
| confidence | DOUBLE | 0–1 |
| rule_id | VARCHAR | detector name, or `llm_triage` |
| explanation | VARCHAR | one line, human-readable |
| evidence | VARCHAR | JSON: the numbers the rule used |
| proposed_fix | VARCHAR | JSON `{field, old_value, new_value}`, or empty for "route to expert" |
| status | VARCHAR | `proposed` \| `approved` \| `rejected` \| `legitimate` (allow-listed, logged) |
| created_by | VARCHAR | `agent:<name>` or a person |
| created_at | TIMESTAMP | |

**`corrections`**: one row per applied change.

| column | type | notes |
|---|---|---|
| correction_id | VARCHAR | |
| issue_id | VARCHAR | |
| record_key | VARCHAR | |
| field | VARCHAR | |
| old_value | VARCHAR | |
| new_value | VARCHAR | |
| reason | VARCHAR | |
| approved_by | VARCHAR | **only a human name**, or `DEV-ASSUMED` (see below) |
| approved_at | TIMESTAMP | |

**`results`**: one row per published number.

| column | type | notes |
|---|---|---|
| result_id | VARCHAR | stable, e.g. `A2:2025:scope3:cat1` |
| metric | VARCHAR | e.g. `tco2e`, `yield_t_ha`, `eur_at_risk` |
| scope | VARCHAR | e.g. `1`, `2_location`, `2_market`, `3` |
| category | VARCHAR | inventory category, or crop / region for C |
| year | INTEGER | |
| scenario | VARCHAR | `actual`, `ssp126`, `ssp245`, `ssp585`, `backtest`, … |
| value | DOUBLE | |
| unit | VARCHAR | |
| method | VARCHAR | short, e.g. `reference_calculator v1 + corrections` |
| status | VARCHAR | `draft` \| `approved` \| `published` |
| produced_by | VARCHAR | module + git short SHA |
| created_at | TIMESTAMP | |

**`lineage`**: the links behind a result.

| column | type | notes |
|---|---|---|
| result_id | VARCHAR | |
| source_kind | VARCHAR | `record` \| `factor` \| `correction` \| `model` \| `doc` |
| source_ref | VARCHAR | a record key, factor id, correction id, model id, or `file#section` |
| contribution | DOUBLE | share or absolute amount, if known |
| note | VARCHAR | |

## Rules

- **A number without lineage rows is a bug.** `tests/test_lineage.py` fails if any `published` result has none.
- **Only `published` results feed the submission CSVs, the dashboard and the copilot.**
- **Dev mode** (`NAVIGATOR_DEV_ASSUME=1`): while humans sleep, pipelines may apply `proposed` fixes so we can score against the dev keys.
  - Those corrections get `approved_by = 'DEV-ASSUMED'` and their results stay `draft`.
  - Final CSVs are produced only after humans approve, in the review app.
- **Always label results as synthetic** in the UI and docs.

## Hand-off tables

| Table | Owner | Read by | Notes |
|---|---|---|---|
| `clean_farm_survey`, `clean_farm_registry` | Data | Climate | Columns as in the raw tables, plus `record_key`, `corrected_fields` |
| `c_parcel_cell` | Climate | Climate, app | Columns: `parcel_id`, `cell_id`, `region`, `distance_km` |
| `results` for C | Climate | app, copilot | Includes `scenario` and per-feature effects (`metric = 'feature_effect_pct'`) |
