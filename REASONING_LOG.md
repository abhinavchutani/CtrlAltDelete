# Reasoning log: traps the pack plants and the rule we apply

Each line names the trap, our rule and its source in the pack. Code that implements a rule cites its row id (e.g. `R07`) in a comment.

## Data quality (Track A)

| id | Trap | Our rule | Source |
|---|---|---|---|
| R01 | Credit notes look like negative or duplicate purchases | Movement type 122 is legitimate: net it against receipts, never flag | METHODOLOGY §2; TASKS_AND_SCORING A1 |
| R02 | Vessel lots booked in tonnes (`uom = TO`) look like a 1000× unit error | `TO` × 1000 = kg; allow-listed | TASKS_AND_SCORING A1 |
| R03 | Seasonal meter peaks (harvest season) look like spikes | Build a seasonal profile per site × carrier before z-scoring | TASKS_AND_SCORING A1 |
| R04 | Ammonia (R717) leaks look like large refrigerant emissions | R717 has GWP 0: a safety issue, not CO2e; allow-listed | METHODOLOGY §3 |
| R05 | The internal GoO log disagrees with the registry | The registry statement is authoritative; a GoO counts only if vintage year = consumption year, capped at the site's consumption; the leased HQ has none | METHODOLOGY §2 |
| R06 | Missing meter months / missing sea legs have no row to flag | Detectors generate the expected key (`energy:{site}:{YYYY-MM}:{carrier}`, `ship:{ref_doc}:{ef_id}`) | TASKS_AND_SCORING record keys |
| R07 | Farmers report "Mineral soil" for peat fields | `soil_misreport` when ≥ 30 % of the farm's crop area is organic on the soil map (map ~88 % accurate) | TASKS_AND_SCORING A1; NATURE_SBTN |
| R08 | Oddities that match no issue type | Logged as observations for expert review, never in the A1 CSV (precision) | SYSTEM_DESIGN Expert review |
| R09 | Supplier PCFs with a stale period or per-tonne values | Valid for year Y only if the reference period covers Y and the value is per kg; else fall back to the library factor | METHODOLOGY §4 |

## Accounting (Track A inventory, Track B slide)

| id | Trap | Our rule | Source |
|---|---|---|---|
| R10 | Biogenic CO2 from wood chips and side streams | A memo item, not Scope 1 | METHODOLOGY §3 |
| R11 | Foodhills acquired 27 Nov 2025 | Operations from Dec 2025 only; Swedish farm emissions **not** in the 2025 inventory | METHODOLOGY §1 |
| R12 | Grain trade divested 2022, still in the published history | Outside the canonical 2021–25 inventory; needs base-year recalculation | METHODOLOGY §1; SCENARIOS_AND_RISK B |
| R13 | Copying Apetit's sample workbook | Never an answer; categories differ by more than 20 % on purpose | APETIT_DATA_RECONCILIATION |
| R14 | Organic soils excluded by the current calculator | Included: 29 t CO2/ha/yr (annual crops) + 13 kg N2O-N/ha/yr | METHODOLOGY §5 |
| R15 | Categories 11 and 12 differ from the sample | Method choices (market-grid use phase; Finnish packaging mix): state the choice, don't "fix" it | METHODOLOGY §4 |
| R16 | Better data (lever L27) shows as a "reduction" | Measurement changes and structural changes are never reductions | SCENARIOS_AND_RISK B |
| R17 | FLAG vs non-FLAG farm emissions | FLAG = N2O, organic soils, liming; fertiliser manufacture, diesel, electricity and pesticides are non-FLAG | METHODOLOGY §5 |
| R26 | Soil map read as the soil (≈ 88 % accurate) | The map is evidence for a soil_misreport review, not a quantity: flag only when crop and farm area agree, or the farm reported peat for that crop in another year; peat counts on areas the reviewed survey calls organic | METHODOLOGY §5; dev labels 2023–24 |

## Climate risk (Track C)

| id | Trap | Our rule | Source |
|---|---|---|---|
| R18 | One weather realisation per SSP looks like "the future" | Build our own ensemble: change-signal deltas on resampled 1991–2020 years | SYSTEM_DESIGN Track C |
| R19 | Training on dirty survey yields | Train on `clean_farm_survey` (A's corrections) only | SYSTEM_DESIGN Risks |
| R20 | Claiming the model "predicted 2025" | 2025 is a normal year in the twin; the backtest story is 2026 (strong FI peas, heat- and drought-hit SE peas; drivers in `out/scores/C1_backtest.json`) | AGENTS.md §8 |
| R21 | C2 future yields drift with management changes | Hold the 2025 parcel mix and current irrigation fixed | TASKS_AND_SCORING C2 |
| R22 | Replacement imports treated as zero-emission | Add the import emissions (cat 1 and cat 4) to the € risk story | SCENARIOS_AND_RISK C3 |
| R27 | The simulator's crop parameters are not in the pack | Stage features (sowing threshold, GDD stages, soil-water bucket per soil class) use documented agronomic assumptions (`src/c_features.py` `CROPS`, `BUCKET_MM`), labelled as ours; sowing can't start before 5 April (DOY 95) | SIMULATION_DESIGN §2–3 (structure only) |
| R28 | Choosing the model on the test years | Feature set, ridge alpha and the ridge/GB average are chosen by rolling-origin CV inside the training years (predict 2020–23); 2024–26 is only reported | TASKS_AND_SCORING C1 |
| R29 | Survey yields differ from parcel-level truth (labels per farm) | Parcel features are area-weighted to farm × crop × year for training; predictions are per parcel. Raw survey only as a fallback with a ×3-median filter | SYSTEM_DESIGN Track C step 4 |
| R30 | One SSP realisation, but a Monte Carlo truth (C2) | Delta method: each 1991–2020 year perturbed with `climate_change_signals` (T + Δ, precip × factor, PET via the Hargreaves temperature term; wet-day factor not applied), same feature code as training; no CO2 fertilisation, technology trend or adaptation | TASKS_AND_SCORING C2; SCENARIOS_AND_RISK |
| R31 | € at risk read as a net business case | € = shortfall vs contracted volume × 2025 contract price × replacement premium. Action values are **gross** avoided losses (irrigation capex/opex and water are not netted) | SCENARIOS_AND_RISK C3 |
| R32 | No import factor for frozen peas / potato in the pack | Replacement imports use a stated proxy (EF-FROZ-CAUL-NL for vegetables, EF-RAP-PL for rapeseed) + 1,500 km reefer truck, net of the domestic farm factor; factor ids in lineage | emission_factor_library |
| R33 | A noisy optimum sold as a recommendation | Pea sourcing split: report the share whose worst-case gain across all scenarios is largest (robust), not the per-scenario optimum (which moves 2–18 pp on a flat curve) | C3 analysis (#70) |
| R34 | Farm survey sample changes year to year | Delivery changes (copilot E18) use same-farm matching; the raw sample total is shown next to it. FI uses surveyed production (ERP stops at 2025) | farm_survey_fi; #65 |

## Copilot (Track E) and presentation

| id | Trap | Our rule | Source |
|---|---|---|---|
| R23 | An LLM states a number | Every number must equal a tool-returned value; a post-check blocks the reply otherwise | SYSTEM_DESIGN Track E |
| R24 | Framework answers from model memory (rules dated 2026) | Answer only from `framework_digest.md`, `source_registry.csv` and the pack docs, with file + section | framework_digest |
| R25 | Presenting twin numbers as Apetit's real emissions | Every screen and slide says "synthetic data"; real events are context only | START_HERE; AGENTS.md §8 |
