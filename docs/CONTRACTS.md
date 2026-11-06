# Interfaces between lanes (DRAFT v0, applies only if we adopt PLAN_PROPOSAL.md)

> **Not decided yet.** Confirm or change this in issue #2 before agents build against it.

These contracts let the three lanes work in parallel overnight. The front end builds against mock files with these shapes until the real outputs land. **To change a shape:** open a PR that updates this file, and post a `HANDOFF` in the chat.

## Folders and run commands

- **Generated outputs** live in `outputs/`, which is gitignored and rebuilt from the pack.
- **Each producer has one command**, which also gets listed in the README:

| Command | Writes |
|---|---|
| `python -m src.layer1_data.run` | `outputs/layer1/` |
| `python -m src.track_c.run` | `outputs/track_c/` |
| `python -m src.copilot.index` | `outputs/copilot/` |

- **Submission drafts** go to `outputs/submissions/`. A human copies the final versions into `submissions/`.

## Layer 1 (Track A) → app and copilot

**`outputs/layer1/issues.parquet`**: one row per flagged issue.

| column | type | notes |
|---|---|---|
| issue_id | str | stable id |
| table | str | pack table name |
| record_key | str | format from TASKS_AND_SCORING.md |
| year | int | |
| issue_type | str | one of the A1 ISSUE_TYPES |
| confidence | float | 0–1 |
| field | str | which field is wrong |
| observed_value | str | |
| proposed_value | str | empty if "route to expert" |
| rule_or_model | str | detector name |
| evidence | str | short human-readable reason |
| status | str | `proposed` \| `approved` \| `rejected` |

**`outputs/layer1/audit_log.parquet`**: one row per decision on an issue.
- **Columns:** `record_key, field, old_value, new_value, rule_or_model, evidence, proposed_by, approved_by, timestamp`.
- **Rule:** agents write `proposed_by`; `approved_by` stays empty until a human approves.

**`outputs/layer1/inventory_lines.parquet`**: one row per (year, line, source record).

| column | type | notes |
|---|---|---|
| year | int | |
| scope | str | `1` \| `2_location` \| `2_market` \| `3` |
| category | str | template category name |
| tco2e | float | |
| record_key | str | source record(s) |
| activity_value | float | |
| activity_unit | str | |
| factor_value | float | |
| factor_unit | str | |
| factor_id | str | |
| factor_source | str | |
| corrections_applied | str | issue_ids |

**`outputs/layer1/peat.json`**:
```json
{"share_organic_parcels": 0.06, "farm_footprint_tco2e": {"current_calculator": 0, "with_organic_soils": 0},
 "farms_likely_misreported": [{"farm_id": "F0001", "organic_share": 0.42, "evidence": "..."}]}
```

## Track C → app and copilot

**`outputs/track_c/replay.json`**: list of season replays.
```json
[{"year": 2026, "region": "SE_SKANE", "crop": "pea", "trained_on": "2018-2025",
  "predicted_t_ha": {"p10": 2.7, "p50": 3.05, "p90": 3.4}, "actual_t_ha": 3.10,
  "normal_t_ha": 3.5, "drivers": [{"name": "drought_flowering", "effect_pct": -9.5}]}]
```

**`outputs/track_c/early_warning_2026.json`**: one entry per as-of date (weekly, May–Aug).
```json
[{"asof": "2026-07-15", "region": "SE_SKANE", "crop": "pea",
  "p10": 2.6, "p50": 3.0, "p90": 3.3, "normal_t_ha": 3.5, "p_below_80pct": 0.31}]
```

**`outputs/track_c/c2_risk.json`**: one row per region × crop × scenario.
```json
[{"region": "FI_SW", "crop": "pea", "scenario": "ssp585", "period": "2041-2060",
  "mean_yield_change_pct": -8.0, "p_bad_year": 0.22, "baseline": "1991-2020"}]
```

**`outputs/track_c/risk_eur.json`**: precomputed grid for the "what could we do" sliders.
```json
{"assumptions": {"price_year": 2026, "source": "contract_prices_and_replacement_premiums.csv"},
 "rows": [{"scenario": "today|ssp126|ssp245|ssp585", "region": "SE_SKANE", "crop": "pea",
           "irrigated_share": 0.0, "fi_share": 0.5, "buffer_area_pct": 0,
           "expected_shortfall_t": 0, "expected_cost_eur": 0, "loss_1_in_10_eur": 0,
           "extra_import_tco2e": 0}]}
```

## API (served by `app/api`, FastAPI)

| Method + path | Returns |
|---|---|
| `GET /api/health` | `{"ok": true, "data_health": {"found": n, "approved": n, "pending": n}}` |
| `GET /api/inventory?year=2025` | Totals by scope and category, plus `lines` (paged) |
| `GET /api/receipt?record_key=…` | Source rows, factor and corrections for one number |
| `GET /api/issues?status=proposed` | List from `issues.parquet` |
| `POST /api/issues/{issue_id}/decision` | Body `{"decision": "approve\|reject", "by": "name"}`. Appends to the audit log |
| `GET /api/c/replay?year=&region=&crop=` | Entries from `replay.json` |
| `GET /api/c/early-warning?asof=&region=&crop=` | Entries from `early_warning_2026.json` |
| `GET /api/c/risk?scenario=&irrigated_share=&fi_share=&buffer_area_pct=` | The nearest row(s) from `risk_eur.json` |
| `POST /api/chat` | Body `{"question": "…"}`. Returns `{"answer", "citations": [{"kind": "record\|doc", "ref", "snippet"}], "numbers": [...], "needs_approval": true}` |
| `POST /api/chat/{answer_id}/approve` | Writes the approval to the audit log |

**Mock data:** the front end keeps mock files with these shapes in `app/web/public/mock/` until the real outputs exist.
