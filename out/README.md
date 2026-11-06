# out/: generated outputs (rebuilt by `make all`)

| File | What |
|---|---|
| `A1_issues_submission.csv` | A1 data-quality issues (2025) |
| `A2_inventory_2025_submission.csv` | A2 2025 inventory |
| `C1_yields_2027_2031_submission.csv` | C1 yields 2027–2031 |
| `C2_climate_yield_risk_submission.csv` | C2 yield risk 2041–2060 |
| `E_answers_submission.csv` | E copilot answers |
| `corrections.csv` | Export of the `corrections` table (the expert-review log) |
| `scores/` | Dev scores from the pack's scorer, one JSON per run |
| `navigator.duckdb` | The shared database (gitignored) |
| `cache/` | LLM call cache (gitignored) |

**Rules:**
- These files are committed so judges can see them, but each must be reproducible from the raw pack with `make all`.
- **The final versions are produced only from `published` results,** after human approval in the review app.
