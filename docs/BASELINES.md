# Baselines and loader checks

## Reference baselines (dev keys)

These are the scores the pack's deliberately simple baselines get on the public dev keys, as published in the pack's `docs/TASKS_AND_SCORING.md`. Our pipelines must beat them by a wide margin.

| Task | Baseline | Dev score |
|---|---|---|
| A1 issues | Rules: price ratio, duplicates, meter gaps and spikes, yield outliers | **52.17** (F1 0.5284), 2023–24 labels |
| A2 inventory | Naive pipeline + reference calculator, no cleaning | **25.54** (2023), **23.24** (2024) |
| D1 catchments | Contract area × state weight | **12.0** (6 dev catchments) |
| C1 yields | Farm historical mean yield (ignores weather) | backtest yourself |
| C2 risk | "No change" null model | — |

**Re-running them locally** (`cd $DATA_DIR/tools && python -m ccn_tools`) executes the pack's own Python code. Auto mode blocked an agent from doing that, so a human runs it once:

```bash
cd data/APETIT_CLIMATE_NATURE_NAVIGATOR_2026/tools && ../../../.venv/bin/python -m ccn_tools > ../../../out/scores/baseline.json
```

Then commit `out/scores/baseline.json`. The scorer (`ccn_tools/score.py`) runs the same way, which is how our CSVs get scored.

## Loader (`python -m src.load`)

The loader writes 55 tables and views to `out/navigator.duckdb` in under a second. Highlights:
- `raw_erp_purchase_lines`: 7,427 rows
- `raw_parcels`: 14,213 rows
- `raw_parcel_crop_history_and_plan`: 284,260 rows
- `raw_weather_daily`: 4,234,104 rows, as a view

**Record keys match the official A1 format.** Checked against `task_dev_A1_dev_issue_labels_2023_2024` (201 labels): every label that points at an existing row matches one of our keys exactly.

| Prefix | Matched / total |
|---|---|
| `erp` | 90/90 |
| `farm_survey` | 59/59 |
| `travel` | 12/12 |
| `waste` | 6/6 |
| `fuel` | 4/4 |
| `refrigerant` | 4/4 |
| `goo` | 2/2 |
| `energy` | 10/16 |
| `ship` | 0/8 |

The 6 `energy` and 8 `ship` misses are `missing_record` / `missing_leg` labels, whose rows do not exist by definition. Detectors must generate those keys themselves:
- missing meter month: `energy:{site}:{YYYY-MM}:{carrier}`
- missing leg: `ship:{ref_doc}:{expected ef_id}`
