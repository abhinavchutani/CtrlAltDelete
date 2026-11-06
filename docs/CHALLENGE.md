# The challenge in full

This is our summary of the Apetit challenge brief (4 Nov 2026), the data pack's own docs (`START_HERE.md`, `docs/TASKS_AND_SCORING.md`, `docs/METHODOLOGY.md`, `docs/SCENARIOS_AND_RISK.md`, `docs/NATURE_SBTN.md`) and the Since AI builder and judge guides. **Where this summary and the pack disagree, the pack wins.** File paths below are relative to the unzipped pack.

---

## 1. What Apetit asks for

**Guiding question (paraphrased):** how can AI help Apetit understand, prioritise and quantify climate and nature impacts across its value chain, and turn sustainability data into decisions that account for future climate scenarios?

The brief wants a system that:

1. builds on the group's existing GHG calculation, plus farmer and third-party data;
2. simulates SBTi target pathways and the actions they require, with cost estimates;
3. forecasts emissions under public scenarios and industry roadmaps;
4. estimates business risks and costs under climate scenarios, **focusing on farming conditions**;
5. combines emissions, raw-material and geospatial data to prioritise nature impacts and dependencies in line with SBTN (biodiversity, eutrophication, water availability), and is built so more geospatial data can be added later.

Results must be **traceable, source-based and subject to expert review and approval**. The aim is not only to calculate the past but to find the most impactful climate and nature actions and risks for the future.

- **Preferred stack:** Microsoft Azure, Fabric, Azure AI Foundry and Copilot. This is a preference, not a requirement, until accounts are arranged; if we use other tools, explain how they would fit Apetit's stack later.
- **Suggested methods:** RAG over frameworks (GHG Protocol, SBTi, SBTN, CSRD), agents for data collection and validation, ML for scenarios and risk, knowledge graphs, geospatial AI, explainable AI, NLP, and digital-twin or scenario simulation.

**The brief's evaluation:**
- automated reporting, plus intelligent use of the given frameworks and climate scenarios;
- reliable data handling;
- material insights about the future that support decisions;
- reliability and transparency (audit trail).

Teams may do one or several parts. Judging is on demonstrated usefulness, sound reasoning and traceability, **not on the number of topics or the technology stack**.

**The brief's deliverable:** a working AI solution and documentation with usage instructions.

**Contacts:** Jani Kielenniva (IT) and Minna Päällysaho (sustainability), via the challenge Discord or the emails in the brief.

---

## 2. The data pack (`APETIT_CLIMATE_NATURE_NAVIGATOR_2026`)

A **synthetic twin** of a Nordic food company, calibrated to Apetit's public figures and sample workbook. Nothing in it is real confidential data.

| Folder | Contents |
|---|---|
| `data/00_apetit_original` | Apetit's sample workbook, unchanged. **Not CC BY**: shared for the hackathon only |
| `data/01_master` | Sites, materials, suppliers, emission-factor library, farms, parcels, climate grid |
| `data/02_raw_feeds` | ERP, energy, fuels, GoOs, refrigerants, waste, water, travel, commuting, shipments, sales, capex, supplier PCFs. **Raw, with planted errors** |
| `data/03_farming` | Finnish farm survey, Swedish (Foodhills) grower file, crop history and plan, current-calculator footprints |
| `data/04_climate` | Daily weather 1991–2060 (Parquet), monthly CSV, climate-change signals |
| `data/05_scenarios` | Transition scenarios, structural events, 30 levers, prices, published inventory history |
| `data/06_nature` | Parcels and catchments (GeoJSON), monitored loads, import-origin indicators |
| `data/07_frameworks` | Framework digest (status 3 Nov 2026) and source registry |
| `tasks/` | Task templates, dev answer keys, question set |
| `tools/ccn_tools` | Loaders, reference GHG calculator, farm-footprint calculator, scorer, baselines |

**The twin at a glance:**
- **Farms:** 680 contract farms: 150 Finnish vegetable growers, 230 Finnish oilseed growers, 300 Swedish pea growers.
- **Land:** 14,213 field parcels across 42 catchments, plus 84 climate grid cells.
- **Weather:** historical up to 2026, then SSP1-2.6, SSP2-4.5 and SSP5-8.5 from 2027.
- **Errors:** 781 planted data issues. Labels for 2023–24 are public; 2025 is hidden.

**Bad harvest years in the twin:**
- **Finland:** 2014 (pea about −40 %), 2015, 2018 (potato), 2021 and 2023.
- **Sweden:** 2021, 2023 and **2026**, while Finland had a record 2026.
- **2025 is normal in the twin.** It does *not* reproduce the real 2025 harvest problem.

**Quick start:** `pip install pandas pyarrow numpy && cd tools && python -m ccn_tools` runs every baseline and scores it on the dev keys.

**Licences:**
- **Pack data:** CC BY 4.0. **Pack code:** MIT. Both © Since AI ry.
- **The Apetit workbook** is the exception: it is not CC BY.
- **Never commit the pack to git.**

---

## 3. Tasks, deliverables and auto-scores

### Track A: Data → inventory

**A1: find and classify data-quality issues in 2025 records**
- **Submit:** `A1_issues_submission.csv` with columns `table, record_key, issue_type, confidence, explanation`.
- **Record-key formats** are given per table in `TASKS_AND_SCORING.md`, e.g. `erp:{doc_no}:{line_no}`, `fuel:{delivery_id}`, `farm_survey:{survey_id}`.
- **Issue types** (use these exact strings): `unit_error, duplicate_record, currency_error, material_mismatch, decimal_shift, missing_record, meter_spike, wrong_gas_code, certificate_mismatch, soil_misreport, outlier_implausible, area_mismatch, coordinate_swap, pcf_unit_error, pcf_stale_period, total_mismatch, missing_leg, mode_mislabel`.
- **Legitimate traps that cost precision if you flag them:** credit notes, vessel lots in tonnes (`uom = TO`), seasonal meter peaks, ammonia systems.
- **`soil_misreport`:** applies when at least 30 % of a farm's crop area that year is truly organic soil but the survey says "Mineral soil".
- **Score:** 100 × F1 × (0.75 + 0.25 × type accuracy). Rule baseline on dev: 52.17.

**A2: 2025 inventory with an audit trail**
- **Submit:** `A2_inventory_2025_submission.csv`, with tCO2e for every category row.
- **Scoring:** each line earns max(0, 1 − |error| / 5 %). Weights: Scope 1 15 %, Scope 2 location-based 3 %, Scope 2 market-based 12 %, Scope 3 total 20 %, category 1 20 %, category 4 8 %, other categories 22 %.
- **Self-check:** the 2023 and 2024 truths are public in `tasks/dev/`. The naive baseline scores about 25.
- **The jury requires:** every number traceable to source records, every correction logged with its reason, and the factor and its source recorded.

### Track B: Pathways (jury rubric only)

**B1: SBTi targets and pathway. B2: abatement cost curve and action portfolio.** The jury expects:

- **Base year and recalculation logic:** the grain-trade divestment (2022), the Foodhills acquisition (Nov 2025), Pudasjärvi, and Kantvik steam.
- **A FLAG / non-FLAG split.**
- **Target rates:** Scope 1+2 at 4.2 %/yr, Scope 3 at 2.5 %/yr, FLAG at 3.03 %/yr, plus V1.3.1 vs V2 timing.
- **A pathway under at least two transition scenarios.**
- **An abatement cost curve (MACC) with honest uncertainty.**
- **Lever L27 (better measurement) is not a reduction.**

### Track C: Climate risk to farming

**C1: predict yields for 2027–2031**
- **Weather:** the weather for those years is given, as one SSP2-4.5 realisation (`scenario = ssp245`).
- **Crop plan:** `parcel_crop_history_and_plan.csv`, rows with `status = planned`.
- **Submit:** `yield_t_ha_pred` for every parcel-year in the template (12,064 rows).
- **Score:** 60 % aggregate production MAPE by region × crop × year (full marks at 0 %, none at 15 %) and 40 % parcel-level nRMSE (none at 0.35).

**C2: climate yield risk for 2041–2060**
- **Submit:** 18 rows, one per region × crop × SSP: `mean_yield_change_pct` (vs 1991–2020) and `p_bad_year` (share of years below 80 % of the 1991–2020 mean).
- **Hidden truth:** a Monte Carlo over the truth model with the 2025 parcel mix and current management.
- **Score:** 70 % MAE of yield change (none at 5 pp) and 30 % MAE of p_bad_year (none at 0.1).

**What drives yields in the truth model (from `SCENARIOS_AND_RISK.md`):**
- drought at sensitive stages (irrigation mitigates it)
- heat days at flowering
- waterlogging after sowing on clay
- rain at harvest
- season length
- potato late blight
- pollen beetle in turnip rape

**C3: € risk and adaptation (jury)**
- Price the risk as shortfall × contract price × replacement premium.
- Add the emissions impact of replacement imports.
- Value the adaptation options: irrigation, sowing date, varieties, a wider sourcing area.
- **Quantify the two-region hedge.** The docs call out the 2026 contrast: a record Finnish crop while Swedish peas failed.

### Track D: Nature (SBTN)

**D1: catchment priority (2025)**
- **Estimate:** for each catchment, the P and N that Apetit-contract parcels deliver to water, plus a `priority_rank`.
- **Formula:** `priority = (P / median(P) + 0.5 × N / median(N)) × state_weight × p_sensitivity`, where state_weight is good 1.0, moderate 1.2, poor 1.5, bad 1.8.
- **Calibration data:** 15 monitored outlets for 2019–2025. 6 dev catchments are public.
- **Score:** 10 % Spearman rank, 10 % top-5 overlap, 40 % MAE log10(P) and 40 % MAE log10(N), none at 0.15. Baseline: 12.0.

**D2: value-chain materiality screening incl. imports (jury).** See `NATURE_SBTN.md`.

### Track E: Copilot with evidence

- **Questions:** 34 in `tasks/E_questions.csv`: 21 numeric test, 3 numeric dev, 10 rubric.
- **Numeric answers:** auto-checked against relative tolerances. They need computed numbers (from Track A), not document search.
- **Rubric answers:** judged on correctness and on citing a source. **No evidence means no credit.**

---

## 4. Jury rubric (all tracks)

| Criterion | Weight | Full marks means |
|---|---|---|
| Usefulness for decisions | 30 % | An Apetit expert could act on it next week: priorities, € and t figures, recommended actions with owners |
| Sound reasoning | 25 % | Correct use of GHG Protocol, SBTi, SBTN and scenario logic. Assumptions stated. Method changes not presented as reductions |
| Traceability and expert review | 25 % | Every number links to source records and factors. Corrections logged. A human approves before results are published |
| Reliability | 10 % | Auto-scored results where applicable; robustness to the planted data issues |
| Technical quality | 10 % | Runs end to end from the raw pack; reproducible; fits or maps onto Apetit's Microsoft stack |

Auto-scores are **evidence for the jury, not the verdict**. Per the Since AI judge guide, the company evaluators use criteria agreed with Apetit. This rubric is very likely those criteria, but that is not confirmed.

---

## 5. Traps and guardrails (lose points if you get these wrong)

**Data and calculation:**
- **Don't copy the Apetit sample workbook as an answer.** Categories differ from it by more than 20 % on purpose.
- **Credit notes (movement 122) are legitimate:** they net against receipts. Vessel lots in tonnes, seasonal meter peaks and ammonia are also not errors.
- **Ammonia (R717) has a GWP of 0.** A leak is a safety issue, not CO2e.
- **Guarantees of origin (GoO):** the registry statement is authoritative over the internal log. A GoO counts only if its vintage year equals the consumption year, capped at the site's consumption. The leased head office has none.
- **Biogenic CO2** is a memo item, not Scope 1.
- **Supplier PCFs** are valid only if the reference period covers the year and the values are per kg.
- **Organic (peat) soils are included** at 29 t CO2/ha/yr for annual crops. The current calculator assumes mineral soil, so it understates.

**Boundary and structural changes:**
- **Foodhills:** its operations count only from Dec 2025. Swedish farm emissions are **not** in the 2025 inventory; they are in full from 2026.
- **Grain trade:** divested in 2022 and outside the canonical inventory. It requires a base-year recalculation.
- **Pudasjärvi closure and the Kantvik steam sale** are future changes. They belong in the pathway (Track B), not the 2025 inventory.

**Targets and reporting:**
- **Lever L27 (better measurement) and structural changes are not reductions.**
- **Categories 11 and 12 are method choices.** Discuss them; don't just copy one.
- **The data is synthetic.** Never present results as Apetit's real emissions or as facts about real farms.

---

## 6. What to submit

**From the pack (`TASKS_AND_SCORING.md`):**
1. A repository link with a README that reproduces our results from the unzipped pack.
2. CSVs for the auto-scored tasks we attempted, named as in `tasks/templates/`.
3. A short demo and slides following **problem → approach → evidence → what Apetit should do**.
4. A one-page method note: data sources, assumptions, limitations, and how expert review works.

**In sinceai.app (Since AI builder guide):**

| Field | Limits and notes |
|---|---|
| Project name | Up to 80 characters |
| Tagline | One sentence, up to 140 characters. Read first on every vote card |
| About the project | Up to 5,000 characters. Judges read all of it; voters see the first lines |
| Built with | The first five become chips on the vote card |
| Repository | A private repo is fine; judges then use the zip |
| Demo video | YouTube only, **ideally under 2 minutes**. Show it working in the first 20 seconds |
| Source code | One .zip, up to 100 MB, without node_modules or data |
| Demo URL (optional) | Judges see it; voters don't |
| Pitch deck (optional) | Voters can open it from the card |
| Supporting documents (optional) | Up to two, for judges. Put the method note here |
| AI tools | Disclose the main ones used; the form asks |

---

## 7. Timeline (EET)

| When | What |
|---|---|
| Sat 09:00–12:00, 14:30–18:00 | Company Q&A at Joki. The guide recommends showing an early version and refining it around real business value |
| Sun 10:00 | Hard submission deadline; peer voting opens (20 pairwise comparisons per builder) |
| Sun 10:00–13:00 | Apetit evaluators review submissions |
| Sun 12:00 | Five finalists confirmed (top-voted project from five different challenges) |
| Sun 13:30 | Company top three: €2,000 / €750 / €250 |
| Sun 14:00 | Finals: 4-minute live pitch plus 6 minutes of jury Q&A. Overall winner: €5,000 |
