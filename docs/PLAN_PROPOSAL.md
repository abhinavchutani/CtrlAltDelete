# Early plan proposal (superseded)

> **Superseded by [SYSTEM_DESIGN.md](SYSTEM_DESIGN.md), the team's decided plan.** This file is kept only for pitch ideas: the demo moments and the real-incident story. Where they differ, SYSTEM_DESIGN wins; for example, the UI is Streamlit, not React.

## The pitch in one line

**"Two harvests in a row, weather cost you money. We built the system that sees it coming, prices it, and proves every number."**

## One platform, three layers: the *Climate & Nature Navigator*

| Layer | Track | Problem it answers (real) | What we show (numbers from the twin) |
|---|---|---|---|
| **Foundation**: numbers you can sign | A | Sustainability numbers are built by hand and not externally assured. Farmland (land-use) emissions are not counted yet, and SBTi targets are due Dec 2027. | Raw data in → an agent flags errors → an expert approves → the inventory recalculates. A receipt on every number. **Peat reveal:** the farm footprint is understated because the calculator assumes mineral soil. |
| **Foresight (hero)**: harvest risk in € | C | The 2025 and 2026 pea harvests were hit by weather (the Aug 2026 profit warning). The strategy bets on peas and Sweden. | Replay every bad season using only earlier data. An early-warning date slider for 2026. Risk for 2041–60 per climate scenario. € at risk and the value of each hedge. |
| **Interface**: ask it anything, get receipts | E | A small team answers CDP, customer and SBTi questions every year. | A chat that answers with a number plus source rows plus the rule, or doc passages plus a citation, and an **Approve** button that writes to the audit log. |

One audit log and one approval flow run through all three. **Track B and D** go on a "phase 2" roadmap slide: the import-replacement emissions from C feed a pathway, and the parcel map is ready for runoff.

## Layer details

### Foundation (A): show it, but keep it small
- **Data-health bar on every screen,** e.g. "2025: N issues found · M approved · K waiting".
- **One review screen:** issue → before/after, rule, evidence, confidence → Approve or Reject → totals update.
- **Receipt icon on every number:** source rows, factor, factor source, and corrections applied.
- **Validation badge:** the pipeline reproduces the public 2023/2024 inventories within X %.
- **Audit-log schema,** taken from the pack's `AZURE_FABRIC_QUICKSTART.md`: `record_key, field, old_value, new_value, rule_or_model, evidence, proposed_by, approved_by, timestamp`.
- **Outputs:** `A1_issues_submission.csv` and `A2_inventory_2025_submission.csv`.

### Foresight (C): the interactive hero
1. **Replay a season:** pick a year and a region. The model is trained only on earlier years, then shown predicted vs actual. Covers Finland 2014, 2018, 2021, 2023 and Sweden 2021, 2023, 2026. **Don't claim 2025**; it is normal in the twin.
2. **Early-warning slider (2026):** weather up to the chosen date is real; the rest of the season is filled with each of the past 35 summers. The forecast range narrows, Skåne drops and Finland rises. "This is the day you'd have known." Fill in the actual date once the model runs.
3. **What-could-we-do panel:** sliders for irrigated share, the Finland/Sweden split, buffer area and sowing date. They recalculate the shortfall (t), € cost (shortfall × contract price × import premium), the 1-in-10-year loss, and the extra emissions from replacement imports. A toggle switches between today and 2041–60 under SSP1-2.6, 2-4.5 and 5-8.5.
4. **Closing card,** "Recommended for the 2027 season": three actions, each with € and an owner.

**Rules for the C layer:**
- Show ranges and probabilities, never a single confident number. It is "early warning, not a guarantee."
- Precompute everything in Python and let the UI only read and sum, so every click is instant.
- **Outputs:** the `C1_yields_2027_2031_submission.csv` and `C2_climate_yield_risk_submission.csv` files.

**Model idea:**
- **Weather → crop-stress features** per cell, year and crop: sowing date, GDD stages, a soil-water bucket, drought by stage, heat days at flowering, waterlogging, rain at harvest, blight days, warm May.
- **Add:** soil, irrigation, farm skill and a tech trend.
- **Fit:** LightGBM, validated with leave-one-year-out.
- **Explain:** per-prediction drivers (SHAP).
- **For C2:** add delta-method weather samples to stabilise the single realisation.

### Interface (E): a chatbot with two tools
- **Doc search** (RAG) over `framework_digest.md`, `source_registry.csv`, the pack docs and the glossary, for rule questions (FLAG, EUDR, base year, …).
- **A numbers tool** that queries the Layer 1 tables and the C outputs and returns record keys. **Pure RAG will invent the 21 numeric answers.**
- **Approve button:** writes to the audit log.
- **Output:** `E_answers_submission.csv`.
- **Stack:** Azure OpenAI if access arrives (Microsoft-stack points), otherwise any LLM.

## Demo "wow" moments

1. **The 2026 replay:** "This would have warned you before the harvest."
2. **The peat reveal:** "Fix your farm baseline before you submit SBTi targets."
3. **Click a citation** in the chat and land on the exact source row.

## Build order (draft)

| When | What |
|---|---|
| Fri night | Layer 1 data spine: loaders, cleaning rules, inventory vs dev truths, audit log. This also produces the clean farm data C needs. |
| Sat day | C: features, model, replays, slider, actions panel. Show an early version at the Q&A (09–12 or 14:30–18). |
| Sat evening | E: chatbot with tools. UI integration throughout. |
| Sun 02–08 | Polish, a <2-min video (show it working in the first 20 s), tagline, description, deck, method note, reproducible README. Submit by 08:00. |

**If we fall behind:** trim E to a few polished flows. **Never cut the audit log.**

## Open decisions for the team

- [ ] Hero track: C (recommended), or A as the safer option if nobody does ML?
- [ ] Do we build all three layers, or C plus a minimal A only?
- [ ] Front end: React + MapLibre/deck.gl, or Streamlit for speed?
- [ ] LLM: Azure OpenAI (if access is given), Claude or OpenAI?
- [ ] Who owns which layer: ML, data, front end, story/video?
- [ ] What do we ask Apetit at the Q&A?

## Draft backlog (convert to `agent-task` issues after deciding)

**Foundation (A):**
1. Load the pack into a single local store (DuckDB or pandas). Typed loaders plus a data-dir config.
2. Reproduce the 2023 and 2024 dev inventories with `tools/ccn_tools/reference_calculator.py`, and report the gap.
3. Cleaning rules for each issue type, plus the audit-log table. Score A1 on the 2023/24 dev labels.
4. Organic-soil analysis: soil map vs survey, and the farm footprint with and without peat.

**Foresight (C):**

5. Weather feature pipeline (daily Parquet → per cell × year × crop stress features).
6. Yield model with leave-one-year-out validation. Write the C1 CSV.
7. Season-replay and early-warning precompute (as-of dates May–Aug).
8. C2 scenario runs plus the delta-method ensemble. Write the C2 CSV.
9. € risk, hedge and adaptation calculator (C3).

**Interface (E) and delivery:**

10. Chatbot: doc index plus a numbers tool plus approve → audit log. Write the E CSV.
11. App shell: map, season replay, actions panel, review queue, chat.
12. Submission kit: tagline, description, deck, method note, video script.
