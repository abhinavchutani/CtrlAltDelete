# Submission text (sinceai.app)

## Tagline options (≤140 chars; voters read this first)

1. "Weather cost Apetit two pea harvests. Our AI traces every emission and prices climate risk, and an expert signs off every number." (130)
2. "From messy farm data to signed-off climate decisions: a traceable inventory, the hidden peat emissions, and harvest risk in €." (126)
3. "The climate navigator that shows its work: every number links to its invoice line, every correction needs a human yes." (119)

## Project name
Climate & Nature Navigator: CtrlAltDelete

## About the project (draft, ≤5,000 chars; the first lines carry the vote card)

**Two harvests in a row, weather hit Apetit's peas.** In 2025 part of the planted area couldn't be harvested; in August 2026 drought in Sweden forced a profit warning. Meanwhile, SBTi targets are due by December 2027, and about 98 % of Apetit's emissions sit in the value chain, mostly on farms. *(Public sources; numbers below come from the organisers' synthetic twin.)*

**What we built.** One system where every number can be traced and signed:

- **Clean data → 2025 inventory.** 18 deterministic detectors find the planted data errors, with an allow-list so legitimate oddities (credit notes, tonne-lots, harvest peaks, ammonia) are never flagged. An expert approves each correction. The organisers' reference calculator turns the clean data into the inventory, and every line clicks back to its source records and factor. Dev scores: A1 {{A1_DEV_SCORE}} vs a 52 baseline; A2 {{A2_DEV_2024}} vs ~23.
- **The hidden peat.** The current farm calculator assumes mineral soil. On the parcel soil map, drained organic soils add {{PEAT_EXTRA_TCO2E}} t CO2e ({{PEAT_SHARE_PCT}} % of contract-farm emissions). That has to be fixed before an SBTi base year is set.
- **Harvest risk in €.** A yield model learns how drought, heat at flowering, waterlogging and harvest rain drive yields. Trained only on years up to 2023, it reproduces the 2026 split: strong Finnish peas, heat- and drought-hit Swedish peas. Under SSP5-8.5, 2041–60 Finnish potato yields change by {{C2_POTATO_FI_585_PCT}} % and turnip rape by {{C2_RAPE_FI_585_PCT}} %, while peas hold up ({{C2_PEA_SE_585_PCT}} % in Skåne): the pea risk is year-to-year, as 2026 showed. We put € on it ({{C3_EUR_AT_RISK}}/yr expected) and on the hedges: two-region sourcing saves {{C3_HEDGE_EUR}}, and irrigation on drought-exposed fields saves {{C3_IRRIGATION_EUR}}.
- **A copilot with receipts.** Ask "What were Säkylä's 2025 refrigerant emissions?" and get the number, its records and the rule applied. A code check blocks any number that didn't come from the data.

**What Apetit could do next week:**
1. Verify soil type on the {{PEAT_TOP_FARMS}} farms most likely on peat before fixing the SBTi base year (owner: sustainability lead).
2. Pilot irrigation scheduling on the highest-risk Skåne pea fields (owner: Apetit Sverige contract farming).
3. Rebalance contracted pea area between Finland and Sweden by {{C3_REBALANCE_PCT}} % (owner: procurement).

**How we built it.** Python + DuckDB (a "number + trail" layer: issues, corrections, results, lineage), scikit-learn / statsmodels, Streamlit, and an OpenAI-compatible LLM for triage and the copilot. An LLM never produces a number. Everything maps one-to-one onto Apetit's Microsoft stack: Fabric Lakehouse, notebooks, Azure ML, Azure OpenAI in AI Foundry, AI Search, Power Apps / Power BI and Purview lineage. One `make all` rebuilds every submission file from the unzipped pack.

**What's next.** Real parcel and soil data from Apetit's growers. SBTi pathway and FLAG targets on the corrected baseline. SBTN catchment prioritisation for the Pyhäjärvi water-protection pilot.

## Built with (first five become chips)
Python, DuckDB, scikit-learn, Streamlit, Claude Code, statsmodels, pandas
