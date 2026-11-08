# Apetit Radar · Climate & Nature Navigator

**See the season before it happens.** Apetit Radar turns Apetit's scattered sustainability, operations and farm data into one
checked, traceable dataset; prices climate risk to contract crops in euros, season by season; and puts a copilot on top that
answers with its sources, simulates decisions and learns from the team. Every number is computed by code, every
correction is logged, and nothing is published until an expert approves it.

*Team CtrlAltDelete · Since AI Hackathon 2026 · Apetit challenge "Climate & Nature Navigator" · Tracks A, C and E (plus B and D groundwork)*

> **Data notice.** All figures come from the challenge's synthetic data twin of Apetit, not Apetit's real data. The one real
> event referenced is Apetit's public profit warning of 12 Aug 2026 (heat and drought cut Swedish pea yields).

---

## The problem Apetit described

| Apetit's problem | What it costs today | What Apetit Radar does |
|---|---|---|
| **Data is scattered and messy.** 43 source feeds (ERP lines, energy meters, fuel, refrigerants, GoO registry, travel, shipments, farm surveys, grower files…) with planted errors | Wrong inputs flow into every report; nobody can say which number is right | **Layer 1 · clean data.** Rule + ML detectors find the errors, propose fixes with evidence, leave legitimate look-alikes alone, and log every correction for expert sign-off |
| **Reports are built by hand.** The GHG inventory is assembled once a year in spreadsheets | Weeks of work; the hand-built draft's own lines don't add up to its total | **The footprint rebuilds itself** from the cleaned records, every tonne traced to source records and emission factors, ready for SBTi target-setting |
| **Never another Sweden.** In 2026 drought at pea flowering cut the Swedish harvest; Apetit learned it in August, through a profit warning | Losses discovered after the season, too late to act | **Layer 2 · climate risk in euros.** A yield model per parcel, run under three SSP climate paths for 15 seasons, flags bad seasons before harvest, prices them in €, and simulates adaptation plans to find the one that pays |
| Knowledge lives in people's heads and meetings | Decisions are lost; answers can't be audited | **Layer 3 · copilot + adaptive database.** Ask anything and get the records behind the answer; simulate an idea; teach it what a meeting decided, linked into a knowledge graph that every future answer and report uses |

## Results you can verify

All scores are reproduced by `make all` and the pack's own scorer (`python -m ccn_tools`) against the public dev keys.
Details and the attempt log: [docs/SCOREBOARD.md](docs/SCOREBOARD.md).

| Track | What | Result | Baseline / bar |
|---|---|---|---|
| **A1** | Data-quality issue detection, all 200 dev labels | **96.69 / 100** (precision 0.98, recall 0.95); 729 issues flagged in 28,933 records; 204 legitimate look-alikes (credit notes, tonnes, seasonal peaks, ammonia) left alone | rule baseline 52.17 |
| **A2** | 2025 GHG inventory with audit trail; self-check on the known 2023 / 2024 truths | **84.96 / 87.17**; 5,339 source records and 114 emission factors traced; peat soils add 11,754 t (10,951 → 22,705 t) the current calculator misses | naive baseline ≈ 25 |
| **C1** | Parcel yields; backtest trained ≤ 2023, tested on unseen 2024–26 | **5.12 % production MAPE, nRMSE 0.115** (SE pea 2026: 4.4 %) | farm-mean baseline 9.89 % / 0.152 |
| **C2** | 2041–60 yield change and bad-year probability per region × crop × SSP | delta-method ensemble: 30 perturbed 1991–2020 years × 3 SSPs on the 2025 parcel mix, cross-checked against the pack realisation | documented method |
| **C3** | € risk and adaptation | shortfall × contract price × replacement premium; 12 adaptation plans simulated (irrigation, sowing date, heat-tolerant pea, FI/SE split); best plan saves **€50–100k a year**; the 2026 FI/SE two-region hedge quantified (FI +24 %, SE −8.5 %) | jury rubric |
| **E** | 34 copilot questions with evidence | **24 / 34 answered offline** with record keys and sources (dev E90–E92: 3/3 within tolerance); the rest answered "not in the data" with a reason, never a guessed number | evidence required |
| **D1** | Catchment P and N priority (SBTN) | leave-one-out MAE log10: P 0.025, N 0.040 on the 6 dev catchments | baseline 12.0 |

**Reproducible:** a clean checkout of `main` rebuilds every submission CSV with `make all` in about 46 s, byte-identical
(only the git SHA in `out/scores/A2_dev.json` differs). No LLM key is needed.

## How it works

```
 43 raw feeds ──► load (DuckDB, raw_* tables, untouched)
                   │
                   ▼
 Layer 1  detectors (rules + ML) ──► corrections log (record_key, field, old → new, rule_or_model, evidence,
          │                                           proposed_by, approved_by, timestamp)
          ▼
          clean tables ──► lineage graph (every result → source records + emission factors)
          │                     │
          ▼                     ▼
          GHG inventory 2023–25 (Scope 1, 2 location/market, Scope 3 by category, FLAG / non-FLAG, peat)
          │
 Layer 2  weather features per parcel and growth stage (drought at flowering, heat days, waterlogging, harvest rain)
          ▼
          yield model (ridge on log-yield + farm effects + gradient-boosted residual, backtested) ──► 15-season outlook × 3 SSPs ──► € at risk per crop and season
          ▼
          plan finder: every adaptation lever alone and combined, re-checked under hotter and cooler paths
          │
 Layer 3  copilot: question → router → deterministic tool (SQL / model / retrieval) → answer + records + sources
          │          the LLM only classifies, retrieves and phrases; a post-check blocks any number not from a tool
          ▼
          adaptive database: knowledge graph of data, models, documents, farms, sites and people's notes;
          custom tags, relations re-linked as notes arrive, four-eyes confirmation before a note counts
          │
          ▼
          expert review & publish  (nothing leaves draft until a named human approves)
```

**Design principle:** deterministic code computes every number. Models are tested on data they never saw. The language
model classifies, retrieves and phrases, and is optional: every demo path runs offline.

### The app (React + FastAPI)

- **Overview: contract crop outlook to 2040.** Pick a climate future (SSP1-2.6 / 2-4.5 / 5-8.5) and every widget
  recalculates: *Crops at risk* (seasons that could cost €100k+ to buy in), *Issues ahead* (each bad season with rain and
  temperature at flowering, fields and farms affected, € at risk, cited measures), *Fields at risk soon*,
  *Hit again and again* (farms with repeated bad years), *Yield optimizer* (the ranked plan search) and *Upcoming season*.
- **Assistant: Ask, Simulate, Teach.** *Ask* answers from the data with the exact records lit up in the knowledge graph,
  and gives cited measures from crop research and farm guides. *Simulate* runs a plan through the yield model and compares
  it with today's plan, season by season. *Teach* files a note or a meeting decision, tags it, links it to the right
  farms and tables, and holds it unverified until a second person confirms it.
- **Design:** light and dark themes, liquid-glass materials, WCAG AA contrast, 60 fps motion.

## Fits Apetit's Microsoft stack

| Layer | Built here | On Apetit's stack |
|---|---|---|
| Storage | DuckDB + Parquet | Microsoft Fabric Lakehouse (Delta tables) |
| Pipelines | Python modules, one `make all` | Fabric notebooks / Data Factory pipelines |
| Yield model | scikit-learn / LightGBM | Azure Machine Learning |
| Copilot | any LLM via API with structured tool calls | Azure OpenAI in Azure AI Foundry, same tools |
| Retrieval | local index | Azure AI Search |
| Review + dashboards | React app | Power Apps (review) + Power BI (dashboards) |

## Run it

Needs **Python 3.11+**, **Node 18+**, and the unzipped data pack in `data/` (see [data/README.md](data/README.md)).

```bash
git clone https://github.com/abhinavchutani/CtrlAltDelete.git && cd CtrlAltDelete
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

make all          # every submission CSV + scores (~1 min, no LLM key needed)
make snapshot v2  # the frozen database and scenario presets the app reads
make api          # terminal 1: FastAPI on http://127.0.0.1:8000
make web          # terminal 2: the app on http://localhost:5173
make test         # tests (pack-dependent tests skip without data)
```

| Command | Output |
|---|---|
| `make a` | `out/A1_issues_submission.csv`, `out/A2_inventory_2025_submission.csv`, `out/corrections.csv`, `out/scores/A2_dev.json` |
| `make c` | `out/C1_yields_2027_2031_submission.csv`, `out/C2_climate_yield_risk_submission.csv`, `out/scores/C1_backtest.json`, `C2_ensemble.json`, `C3_euro_risk.json` |
| `make d` | `out/D1_catchment_priority_submission.csv`, `out/scores/D1_dev.json` |
| `make e` | `out/E_answers_submission.csv` |
| `make demo-check` | walks the demo through the real API, one ok / FAIL line per step |
| `API_MOCK=1 make api` | serves committed fixtures, no data pack needed |

## Traceability and expert review

- Every correction is a row in the audit log with its rule or model, evidence and proposer. Code never fills
  `approved_by`; a person does.
- Every inventory line links to its source record keys and the emission factor with its source.
- Copilot answers carry their record keys and documents; a number not produced by a tool is blocked.
- Climate figures are shown as € bands with the climate path and the assumption behind them.
- Guardrails from the pack are encoded and tested: credit notes net against receipts, ammonia (R717) has GWP 0, biogenic
  CO2 is a memo item, GoOs count only for their vintage year and site, Foodhills counts from Dec 2025, grain trade is out
  of the base year, measurement improvements (L27) and structural changes are never counted as reductions.

## Repository map

```
AGENTS.md               orientation for AI agents and reviewers: what to run, where the evidence is
src/                    pipelines: load, a_* (data quality, inventory), c_* (climate, yield, €), p_* (prediction),
                        r_* (retrieval, reports, knowledge), e_* (copilot), b_sbti (targets and pathways)
api/                    FastAPI: outlook, plan finder, ask / simulate / teach, knowledge graph, reports
web/                    React + Vite + TypeScript app
out/                    submission CSVs, corrections.csv, scores/ (rebuilt by make all)
tests/                  pytest suite
docs/                   SYSTEM_DESIGN, V2_ARCHITECTURE, CONTRACTS, CHALLENGE, APETIT_CONTEXT, SCOREBOARD, METHOD notes
METHOD_NOTE.md          one-page method note: sources, assumptions, limitations, expert review
REASONING_LOG.md        every modelling decision and why
```

Further reading: [docs/SYSTEM_DESIGN.md](docs/SYSTEM_DESIGN.md) · [docs/V2_ARCHITECTURE.md](docs/V2_ARCHITECTURE.md) ·
[docs/CHALLENGE.md](docs/CHALLENGE.md) · [docs/APETIT_CONTEXT.md](docs/APETIT_CONTEXT.md) ·
[docs/RISK_MITIGATION_AND_ADAPTATION.md](docs/RISK_MITIGATION_AND_ADAPTATION.md)
