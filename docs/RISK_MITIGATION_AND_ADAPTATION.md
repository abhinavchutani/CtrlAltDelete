# Risk Mitigation & Adaptation — Design Doc
*Apetit × SinceAI 2026 · Tracks C (climate risk to farming) + E (copilot) · draft 7 Nov 2026*

---

## 1. The pitch in one line

> **"Nothing can be done once the peas are sown" is true for the farmer — not for Apetit.**
> We show *which* risks matter, *how much* they cost, *what* Apetit can do about each, and *when* each decision must be taken — with every number traceable and every recommendation approved by an expert.

### What the judges told us (7 Nov meeting)
- Auto-scores don't matter. Usefulness, reasoning and traceability do. "Good enough" beats perfect.
- Real pain point #2: climate business risk to crops (e.g. Swedish peas 2026). **Prediction alone isn't enough — they want "what could be done to make it better".**
- Long-term view (~2050) should tell them **how big** the risk is and **whether to start now** (new heat-tolerant varieties, slow development cycles).
- Profit first, but customers demand value-chain emission cuts → adaptation must not blow up Scope 3.

---

## 2. Reframe: the three decision windows Apetit controls

| Window | When | Levers Apetit controls | Owner |
|---|---|---|---|
| **Strategic** | 1–15 years ahead | Variety development / breeding partnerships, sourcing-region portfolio, irrigation co-investment, crop mix | R&D, Sourcing, CFO |
| **Pre-season** | Winter before sowing | Which growers/parcels get contracts, contract terms (risk-sharing, field-selection rules), contracted area buffer, sowing-window advice | Agronomy, Procurement |
| **In-season / post-harvest** | Sowing → harvest → sales year | Early yield forecast → **pre-book replacement imports early**, harvest scheduling, frozen-stock carry-over, sales allocation | Procurement, Supply chain, Sales |

---

## 3. Risk drivers (the "keys" of the system)

The package's truth yield model reacts to exactly these hazards (SCENARIOS_AND_RISK.md, Track C). Every risk and every adaptation option is tagged with one of them:

| ID | Hazard | Main crops affected | Modelled mitigation |
|---|---|---|---|
| H1 | Drought in sensitive stages | Peas, potatoes, all | Irrigation (in model) |
| H2 | Heat days at flowering | Peas, turnip rape | — (varieties = assumption) |
| H3 | Waterlogging after sowing on clay | All on clay soils | Parcel/soil selection |
| H4 | Rain at harvest | Peas, cereals, rape | Harvest scheduling, earlier varieties |
| H5 | Season length / immaturity | Late crops, northern parcels | Variety maturity class, sowing date |
| H6 | Potato late blight (warm, wet Jul–Aug) | Potatoes | Sprays (in model), resistant varieties |
| H7 | Pollen beetle (warm May) | Turnip rape | IPM, monitoring |

The C2 model attributes each region × crop × SSP risk to its **dominant driver(s)** → that driver selects the adaptation options.

---

## 4. Hero features (build these first)

### 4.1 Sourcing portfolio hedge — "efficient frontier"
- **Idea:** treat Finland vs Sweden (and regions within them) like assets in a portfolio. Bad years are not perfectly correlated (2026: record Finnish peas, drought-hit Swedish peas).
- **Method:** from the C2 Monte Carlo, get joint yield distributions per region. Vary contract-area shares; for each mix compute expected supply and **CVaR₁₀ of shortfall** (average of the worst 10 % of years). Plot the frontier.
- **Output:** *"Shifting 15 % of pea area from Skåne to SW Finland cuts the 1-in-10-year shortfall by X t / €Y, at a cost of €Z/yr in higher contract prices."*
- **Data:** C2 simulations, `contract_prices_and_replacement_premiums.csv`, `farm_registry.csv`, parcel plan.
- **Why it wins:** the package explicitly asks to quantify the two-region hedge; finance understands it instantly.

### 4.2 Adaptation pathways — tipping points + lead times
- **Idea:** answer "do we need to start now?" directly.
- **Method:**
  1. Define an acceptability threshold per crop × region (e.g. `p_bad_year > 0.25`, or € at risk > budget).
  2. From C2 trajectories per SSP, find the **tipping year** when the threshold is crossed.
  3. For each option, subtract its **lead time** → **latest decision year**.
  4. Add **signposts**: monitored indicators that trigger the next step (e.g. "3 consecutive seasons with > N heat days at flowering in Skåne → activate plan B").
- **Output:** a Gantt-style timeline per crop: *"Heat-tolerant pea variety: decision needed by 2029 under SSP2-4.5, by 2027 under SSP5-8.5. Irrigation: can wait until 2034."*
- **Why it wins:** method from Dutch Delta / adaptation-pathways planning; almost no hackathon team does it; it's exactly what Speaker 1 asked for.

### 4.3 Adaptation decision board (the final screen)
One page an Apetit expert can act on next week:

| Risk | Crop / region | € at risk (2041–60, SSP2-4.5) | Driver | Recommended action | Owner | Decide by | Trigger | Evidence | Status |
|---|---|---|---|---|---|---|---|---|---|
| e.g. Heat at flowering | Peas / Skåne | €… /yr expected, €… 1-in-10 | H2 | Variety trials with breeder + shift 15 % area to FI | R&D, Sourcing | 2029 | Signpost S2 | C2 run #, source rows | ☐ Pending expert approval |

- Every row links to source records, model run and the adaptation-options source.
- **Status column = human-in-the-loop**: nothing is "published" until an expert approves.

---

## 5. Supporting features (if time allows)

### 5.1 Adaptation cost curve (MACC for resilience)
Same visual language Apetit already knows from carbon MACCs: x = € of loss avoided per year, y = cost per € avoided. Irrigation and sowing date can be **re-simulated** through the yield model; others use stated assumptions.

### 5.2 Stress-test replays
- "Swedish 2026 drought replayed on a 2045 climate."
- "Compound year: Finland *and* Sweden fail together."
- Show € impact **without** vs **with** the adaptation portfolio.

### 5.3 In-season early warning → procurement
Mid-season yield forecast (C1 model + weather to date) → probability of shortfall → recommendation to pre-book imports N weeks earlier. Value = (spot premium − forward premium) × expected shortfall.

### 5.4 Frozen stock as insurance
Optimal carry-over of frozen stock where marginal holding cost = expected replacement premium avoided.

### 5.5 Parcel / grower risk ranking
Flag high-risk contracted parcels (clay + waterlogging, no irrigation, organic soil) → targeted agronomy advice, contract incentives, or field-selection rules.

### 5.6 Weather-index risk-sharing clauses
Parametric clauses in grower contracts triggered by computed indices (e.g. heat days at flowering). Shares risk fairly, pays out automatically, fully auditable.

### 5.7 Opportunity side
Longer northern seasons → new crops / northward shift of sourcing. Present risk **and** opportunity (TCFD-style).

---

## 6. Side-effect check: no-regret vs maladaptation

Every option is scored on co-effects so we don't solve climate risk by creating emissions or nature problems:

| Option | GHG (Scope 3 / FLAG) | Nutrient runoff (SBTN, Track D) | Water | Robustness |
|---|---|---|---|---|
| Replacement imports | ▲ worse (transport + origin footprint) | depends on origin | — | Reactive only |
| Irrigation | ▲ slight (energy) | ▲ possible leaching | ▲ water use | Scenario-dependent |
| Regional diversification | ≈ | ≈ | ≈ | **No-regret** |
| Heat-tolerant / earlier varieties | ≈ | ≈ | ▼ less stress | **No-regret** (long lead) |
| Catch crops / soil cover | ▼ better | ▼ better | ▼ better retention | **No-regret** |

Labels: **No-regret** (pays off under all SSPs) · **Scenario-dependent** · **Maladaptive** (fixes one risk, worsens another).

---

## 7. Adaptation options knowledge base (seed)

File: `data/adaptation_options.csv` — the copilot looks up options by hazard ID. Seeded from LIFE AgriAdapt (Northern region, arable measures), Climate-ADAPT and the package's own C3 hints. **Lead times and cost levels are indicative assumptions — to be reviewed by Apetit agronomists.**

| option_id | hazard | crops | option | window | lead_time (indicative) | cost | in yield model? | source |
|---|---|---|---|---|---|---|---|---|
| A01 | H1 | all | Efficient irrigation systems | Strategic | 2–3 yrs | High | Yes | AgriAdapt; package C3 |
| A02 | H1 | all | On-farm water storage | Strategic | 2–4 yrs | High | Partly (via irrigation) | AgriAdapt |
| A03 | H1, H3 | all | Increase soil water-holding capacity (organic matter, compost, year-round soil cover) | Pre-season | 3–5 yrs | Low–Med | No (assumption) | AgriAdapt |
| A04 | H1, H2 | peas, rape | Heat/drought-tolerant varieties (breeding partnership / trials) | Strategic | ~8–12 yrs | Med | No (assumption: +X °C tolerance) | AgriAdapt; package C3 |
| A05 | H1, H2, H4 | all | Wide range of varieties (spread maturity classes) | Pre-season | 1 yr | Low | No (assumption) | AgriAdapt |
| A06 | H2, H5 | peas, rape | Change sowing time (earlier sowing to escape heat at flowering) | Pre-season | 1 yr | Low | Partly (temperature trigger) | AgriAdapt; package C3 |
| A07 | H1–H5 | all | Diversify sourcing regions (FI/SE portfolio) | Strategic / Pre-season | 1 yr | Med (contract premium) | Yes (computable) | package C3 hint |
| A08 | H3 | all | Parcel selection: avoid poorly drained clay for sensitive crops | Pre-season | 1 yr | Low | Yes | package (soil data) |
| A09 | H3 | all | Controlled traffic / careful soil cultivation | Pre-season | 1–2 yrs | Low–Med | No | AgriAdapt |
| A10 | H4 | peas, cereals | Harvest capacity & scheduling buffer | In-season | 1 yr | Med | No | assumption |
| A11 | H5 | late crops | Earlier-maturing varieties | Pre-season | 1–3 yrs (existing varieties) | Low | No (assumption) | AgriAdapt |
| A12 | H6 | potatoes | Blight-resistant varieties + forecast-based spraying | Pre-season / In-season | 1–5 yrs | Low–Med | Sprays yes | assumption |
| A13 | H7 | turnip rape | Integrated pest management, pest monitoring | In-season | 1 yr | Low | No | assumption |
| A14 | all | all | Extend crop rotation / cultivate legumes & diverse catch crops | Pre-season | 2–4 yrs | Low | No | AgriAdapt |
| A15 | all | all | Crop insurance / weather-index risk-sharing clauses | Pre-season | 1 yr | Med | n/a (financial) | AgriAdapt |
| A16 | all | all | Grower advisory & agricultural information services | Pre-season | 1 yr | Low | No | AgriAdapt |
| A17 | all | all | Farming cooperation (shared machinery, irrigation) | Strategic | 2–3 yrs | Low | No | AgriAdapt |
| A18 | all | processed products | Frozen-stock carry-over buffer | Post-harvest | immediate | Med (holding cost) | n/a (computable) | assumption |
| A19 | all | processed products | Early forward booking of replacement imports | In-season | immediate | Low | n/a (computable) | assumption |
| A20 | H5 | new crops | Cultivate new crops enabled by longer seasons (opportunity) | Strategic | 3–5 yrs | Med | No | AgriAdapt |

**CSV columns:** `option_id, hazard_ids, crops, option, decision_window, lead_time_yrs_min, lead_time_yrs_max, cost_level, ghg_effect, nutrient_effect, water_effect, robustness, in_yield_model, assumption_note, source_name, source_url, reviewed_by, reviewed_on`

---

## 8. How the AI ties it together (Track E)

```
User question
   │   "What's the climate risk to our pea supply by 2050 and what should we start now?"
   ▼
Copilot (tool-calling agent)
   ├─ risk_tool(crop, region, ssp)      → C2 results: Δyield %, p_bad_year, € at risk, dominant hazard
   ├─ options_tool(hazard_ids, crop)    → rows from adaptation_options.csv
   ├─ simulate_tool(option, params)     → re-run yield model (irrigation, sowing, area mix)
   ├─ pathway_tool(crop, region)        → tipping year, decide-by year per option
   └─ cite every number: file + row / record key / model run id / source URL
   ▼
Draft recommendation → Decision board row (status: Pending expert approval)
   ▼
Expert approves / edits / rejects → logged with name + reason
```

**Microsoft-stack fit:** CSV/Excel in, results as Excel/Power BI-ready tables; copilot pattern maps to Copilot Studio / Azure OpenAI (see the package's Azure/Fabric notes).

---

## 9. What the data can and cannot simulate (say this out loud)

| Option | Simulated? | Presentation |
|---|---|---|
| Irrigation, sourcing mix, parcel selection, stock buffer, early booking | Yes / directly computable | "Simulated result" |
| Sowing date | Partly (temperature trigger) | "Simulated, with caveat" |
| New varieties, soil-health measures, IPM | No | "Modelled under stated assumption: …" |

Package limitations to cite: one realisation per SSP (C2 truth uses an ensemble), no CO₂ fertilisation, no adaptation in the truth model beyond irrigation/sowing trigger, synthetic weather. **Conclusions about method transfer to the real company; absolute numbers do not.**

---

## 10. Demo storyline (3–4 minutes)

1. **Problem:** "2026 — Finnish peas record harvest, Swedish peas hit by drought. What does 2045 look like?"
2. **Risk:** C2 map — Δyield and p_bad_year by crop × region × SSP; dominant hazard per cell.
3. **Money:** € at risk = shortfall × contract price × replacement premium (+ extra Scope 3 from imports).
4. **Reframe:** three decision windows — Apetit can act before, during and after the season.
5. **Hedge:** portfolio frontier — "move 15 % of area, cut tail loss by X".
6. **Timeline:** pathways — "variety decision needed by 2029; irrigation can wait."
7. **Copilot live:** ask the question → cited answer → decision board row → expert clicks Approve.
8. **Close:** "Every number traceable, every action owned, nothing published without expert sign-off."

---

## 11. Build priority

| Priority | Item | Depends on |
|---|---|---|
| **P0** | C2 risk results with dominant-hazard attribution | yield model |
| **P0** | € at risk (C3 formula) | C2, prices |
| **P0** | `adaptation_options.csv` (§7) | — |
| **P0** | Portfolio hedge (§4.1) | C2 simulations |
| **P0** | Pathways timeline (§4.2) | C2 per year, options lead times |
| **P0** | Decision board + approval status (§4.3) | all above |
| P1 | Copilot tools wired to the above (§8) | P0 |
| P1 | Co-effects scoring (§6) | options CSV |
| P2 | Adaptation cost curve, stress-test replays, early warning, stock buffer | P0 |

---

## Sources
- Package: `docs/SCENARIOS_AND_RISK.md` (Track C hazards, C3 hint, FI/SE hedge), `docs/TASKS_AND_SCORING.md` (jury rubric), `docs/ASSUMPTIONS_AND_LIMITATIONS.md`, `docs/SIMULATION_DESIGN.md`
- LIFE AgriAdapt — Northern region measures: https://agriadapt.eu/northern-region/
- LIFE AgriAdapt — arable crop measures: https://agriadapt.eu/?p=206973
- AWA webtool: https://awa.agriadapt.eu/en
- Climate-ADAPT adaptation options (EEA): https://climate-adapt.eea.europa.eu/knowledge/adaptation-information/adaptation-measures/index_html
- Climate Resilience Platform (Alliance Bioversity–CIAT / PepsiCo) — reference design for supply-chain resilience: https://alliancebioversityciat.org/tools-innovations/climate-resilience-platform
