# Method note: Climate & Nature Navigator (one page, draft)

**What it is.** One traceable decision system on the organisers' synthetic twin of Apetit:
- **A:** clean raw data → 2025 GHG inventory.
- **C:** weather → contract-crop yield risk → €.
- **E:** a copilot that answers with evidence.

**All results are synthetic** and are not Apetit's real figures. `{{placeholders}}` are filled from the `results` table at freeze.

## Data sources
- **The data pack:** `APETIT_CLIMATE_NATURE_NAVIGATOR_2026` v1.0.0. Data is CC BY 4.0 and code MIT (© Since AI ry). Apetit's sample workbook is used for context only, never as an answer.
- **Standards:** GHG Protocol (Corporate, Scope 2, Scope 3), IPCC AR6 GWP100, the IPCC 2019 Refinement for agricultural N2O, the SBTi Corporate Net-Zero Standard and FLAG guidance, and SBTN steps 1–2. All are taken from the pack's `framework_digest.md` and `source_registry.csv`.
- **Factors:** the pack's `emission_factor_library.csv`, plus supplier PCFs where valid (rule R09).

## Method
- **A, inventory:**
  1. Load the raw files untouched; every record keeps its official key.
  2. Run 18 deterministic detectors, one per issue type, with an allow-list for legitimate oddities.
  3. An LLM triages grey-zone cases only (it never edits data).
  4. A human approves the corrections.
  5. The organisers' reference calculator turns the corrected data into the inventory.
  6. Every inventory line is stored with lineage down to record keys and factor ids.
- **A, peat:** the farm footprint is recomputed with drained organic soils (29 t CO2/ha/yr), against the current mineral-soil calculator.
- **C:**
  - **Model:** one yield model per crop, trained on cleaned 2012–2026 farm history. It uses features that mirror crop physiology: sowing date, degree-day stages, a soil-water bucket, drought and heat at sensitive stages, waterlogging, harvest rain, and blight and beetle weather.
  - **Backtest:** train up to 2023, predict 2024–26.
  - **Futures:** an ensemble built from the pack's change signals for SSP1-2.6, 2-4.5 and 5-8.5.
  - **€:** shortfall × contract price × replacement premium, plus the emissions of replacement imports.
- **E:** two tools, SQL over approved `results` and retrieval over the frameworks. A code check makes sure every number in an answer came from a tool.

## v2: from results to decisions
v2 turns the frozen v1 results into a planning tool, without changing a v1 number:
- **Prediction:** it re-runs the Track C yield model on 6 preset scenarios, or on a scenario typed or spoken in plain words, from 2026 to 2060.
- **Alerts:** only critical and notable risks, at most 12, each with a € band and a suggested lever.
- **Hedge frontier:** expected and 1-in-10-year loss for every Finland–Sweden pea split.
- **Adaptation pathways:** tipping year when bad-year odds pass 1 in 4, minus each option's lead time.
- **Retrieval:** answers questions with read-only SQL over the same tables, with evidence, and builds Excel reports with a Sources sheet.
- **Decision board:** joins the critical risks with options from a 20-row adaptation knowledge base (not yet reviewed by an agronomist). A named human approves each row, in an append-only log.

The LLM only maps words to a scenario spec or a tool. Deterministic code computes every number, and an answer containing a number no tool returned is blocked. On this weather path the 1-in-4 threshold isn't crossed before 2060, so the pathways show signposts to watch rather than a decide-by year.

## Key assumptions
- Organic-soil emissions are included (the pack's methodology). The soil map is about 88 % accurate, so soil misreports are routed to an expert, not auto-corrected.
- Foodhills is in scope from Dec 2025 only, and its Swedish farms are excluded from 2025.
- Categories 11 and 12 follow the pack's documented method choices (rule R15).
- C2 holds the 2025 parcel mix and current irrigation fixed. There is no CO2 fertilisation and no adaptation in the baseline.
- Track C crop parameters (sowing thresholds, degree-day stages, soil-water buckets) are our agronomic assumptions; the pack describes the simulator's structure but not its parameters (R27). Model choices were made by cross-validation inside the training years, never on the 2024–26 test years (R28).

## Limitations
- The twin's weather is inspired by real seasons but is not real weather. Absolute numbers don't transfer to Apetit; the method does.
- There is one weather realisation per SSP. Our ensemble approximates the truth Monte Carlo.
- Scenario prices and lever costs are the pack's illustrative values.
- **Climate € risk is gross and probably a lower bound.** Adaptation values are avoided losses before the actions' own costs (irrigation capex, opex and water use). The model's year-to-year yield spread is about 0.7–1.1× the observed one, so the 1-in-10-year loss is likely understated. Replacement-import emissions use a proxy frozen-vegetable factor (R31, R32).
- **Total climate € risk is roughly flat to 2041–60; the mix shifts.** Peas hold up (+2–3 %), while potato and carrot losses grow 2–3×. The pea risk is year-to-year (2026: Finland +24 %, Sweden −8.5 %, pooled +0.8 %), which is why two-region sourcing is the hedge. Today's ~28/72 FI/SE split is close to the robust optimum (R33).

## How expert review works
1. Every detector finding becomes a `proposed` issue, with the evidence and a proposed fix.
2. A human accepts, rejects or edits it in the review page. That writes `approved_by`, `approved_at` and the reason to `corrections`. High-confidence rules can be bulk-accepted (still logged one by one); soil misreports and anything moving a category by more than 1 % need individual review.
3. Approved corrections trigger a recalculation. Affected results return to `draft` until a reviewer publishes them.
4. Only `published` results reach the CSVs, the dashboard and the copilot. The full log ships as `out/corrections.csv`.

**Scores on the public dev keys:**

| Task | Baseline | Ours |
|---|---|---|
| A1 | 52.17 | 96.7 |
| A2 (2023 / 2024) | 25.5 / 23.2 | 85.0 / 87.2 |
| C1 backtest | — | MAPE 5.1 % |

**Reproduce:** `make all` from the unzipped pack (see README).
