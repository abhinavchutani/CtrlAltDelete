# Deck outline, demo script, video script, Microsoft mapping

`{{placeholders}}` are filled from `results` at freeze. The list is at the bottom. **Every number on screen is synthetic (twin) unless it is cited as a public fact.**

## Slides: problem → approach → evidence → what Apetit should do (8 slides)

1. **Title:** "Climate & Nature Navigator: numbers you can sign, risks you can see coming." Team, and a "synthetic twin" disclaimer.
2. **Problem (real, public):**
   - Weather hit the pea harvest in 2025 (unharvested area) and in Aug 2026 (Swedish drought, guidance cut to −€2.0M…+€1.0M).
   - SBTi targets are due by Dec 2027.
   - About 98 % of emissions are in the value chain.
   - The farm calculator assumes mineral soil.

   Sources: Apetit Annual Report 2025, Financial Review 2025, profit warning 12 Aug 2026.
3. **Approach:** one system, three layers: clean data → inventory, weather → yield → €, and a copilot with receipts. One rule: code computes every number; the LLM only classifies and explains. The architecture diagram goes here.
4. **Evidence, data quality:** issues found by type; dev scores A1 96.0 vs 52.17, A2 85.9 vs 23.2; the allow-list protecting precision; one approved correction.
5. **Evidence, the peat reveal:** the farm footprint with vs without organic soils: 14,356 t CO2e (57 %), and the FLAG share moves from 67.6 % to 69.6 %. Fix it before the SBTi base year.
6. **Evidence, harvest risk:** the 2026 backtest (FI strong, SE drought); the 2041–60 risk by SSP; € at risk {{C3_EUR_AT_RISK}}/yr; the hedges {{C3_HEDGE_EUR}} and {{C3_IRRIGATION_EUR}}.
7. **Traceability + expert review:** the click-through from a number to its invoice line, the corrections log, and the publish flow. The Microsoft mapping table (below).
8. **What Apetit should do next week:** 3 actions with €, t and an owner (see SUBMISSION_TEXT.md). The phase-2 roadmap: SBTi pathway (B) and the SBTN catchment layer (D).

## Demo script (4 minutes, live final)

| Time | Screen | Say |
|---|---|---|
| 0:00–0:30 | Title → farm & peat page | "Apetit's farm calculator assumes every field is mineral soil. Drained peat emits 29 t CO2 per hectare per year." |
| 0:30–1:30 | Data quality page | "Raw files in. Our detectors found 790 problems; the allow-list ignored 204 legitimate oddities." Approve one soil misreport live; the total updates. |
| 1:30–2:15 | Inventory page | Click Scope 3 cat 1 → supplier lines → the invoice record → factor + source. "Every number has a trail." |
| 2:15–3:15 | Climate page | "Trained only on years up to 2023, the model sees 2026 coming: strong Finnish peas, drought-hit Swedish peas." Drag the SSP slider: € at risk, the two-region hedge. |
| 3:15–3:45 | Copilot panel | Ask: "What share of 2025 contract-farm emissions comes from drained organic soils?" The answer opens its evidence. |
| 3:45–4:00 | Final slide | Three actions, each with an owner. |

## Video script (<2 min, for the vote card; product working by 0:20)

| Time | Shot |
|---|---|
| 0:00–0:05 | Text: "Weather cost Apetit two pea harvests." |
| 0:05–0:20 | The climate page: the SSP slider moves, € at risk changes. |
| 0:20–0:45 | The data quality page: approve a correction, the inventory total updates. |
| 0:45–1:05 | Click a number → its invoice line. |
| 1:05–1:25 | The peat reveal: the calculator says 10,951 t CO2e, with peat 25,308 t CO2e. |
| 1:25–1:45 | Copilot: a question with evidence chips. |
| 1:45–1:55 | "Every number traceable. Every correction signed by a human." Logo. |

## Microsoft mapping (slide 7; from the pack's AZURE_FABRIC_QUICKSTART)

| Layer | Our build | Apetit production path |
|---|---|---|
| Storage | DuckDB + Parquet (`raw_*` → `clean_*` → `results`) | Fabric Lakehouse: Files (bronze) → Delta tables (silver/gold) |
| Pipelines | Python modules, `make all` | Fabric notebooks / Data Factory pipelines |
| Data quality | Deterministic detectors + allow-list; `issues` table | Fabric notebooks with expectation checks; issue log as a Delta table |
| Calculation | The pack's reference calculator + versioned factor library | A versioned calculation notebook; the factor library as a governed table |
| Yield model | scikit-learn / statsmodels | Azure Machine Learning |
| LLM + tools | OpenAI-compatible API, structured JSON, cached | Azure OpenAI in AI Foundry, Agent Service with the same tools |
| Retrieval | Local index over the framework digest + docs | Azure AI Search |
| Review + UI | Streamlit review queue and pages | Power Apps (approval flow) + Power BI |
| Audit trail | `corrections` + `lineage` tables | The same tables in the Lakehouse + Purview lineage |

## Placeholders to fill from `results`

| Placeholder | Source |
|---|---|
| `96.0` | `out/scores/` (A1 dev F1 score) |
| `91.3`, `85.9` | `out/scores/` (A2 dev) |
| `8.2 %` | C backtest result |
| `790`, `204` | `issues` counts by status |
| `10,951 t CO2e`, `25,308 t CO2e`, `14,356`, `57`, `8` | A peat results (#12) |
| `67.6 %`, `69.6 %` | A inventory FLAG split |
| `{{C2_PEA_SE_585_PCT}}`, `{{C2_PEA_SE_585_PBAD}}` | C2 results (#18) |
| `{{C3_EUR_AT_RISK}}`, `{{C3_HEDGE_EUR}}`, `{{C3_IRRIGATION_EUR}}`, `{{C3_REBALANCE_PCT}}` | C3 results (#19) |
