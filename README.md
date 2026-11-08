# CtrlAltDelete · Apetit × Since AI Hackathon 2026

**Challenge:** Apetit Plc, *Climate & Nature Navigator*
**Event:** Since AI Hackathon, Turku, 6–8 Nov 2026
**Hard deadline:** **Sun 8 Nov, 10:00 EET**, in sinceai.app (we aim for 08:00)

> **The plan: [docs/SYSTEM_DESIGN.md](docs/SYSTEM_DESIGN.md).** Tracks A, C and E on one traceable system: a Streamlit app over a DuckDB "number + trail" layer.
> - **Shared tables:** [docs/CONTRACTS.md](docs/CONTRACTS.md).
> - **Task board:** issues labelled `agent-task`.

## The problem in one paragraph

Apetit makes frozen vegetables and rapeseed oil and works with hundreds of contract farmers in Finland and Sweden. Its climate numbers are assembled by hand from messy systems once a year, and they only describe the past. Apetit wants an AI system that:

1. calculates the full carbon footprint automatically from raw company and farm data;
2. plans its science-based (SBTi) climate targets and costed actions;
3. forecasts emissions under future scenarios;
4. estimates what climate change will cost the business, **especially farming**;
5. prioritises nature impacts (water, biodiversity) using map data.

Every result must be **traceable to source records** and **approved by an expert** before it is published.

## Why it matters to them right now (real, public events)

| When | What happened |
|---|---|
| Autumn 2025 | Weather problems in the frozen-pea harvest: part of the planted area could not be harvested. Food Solutions profit fell, followed by a December profit warning. |
| Dec 2025 | Committed to setting SBTi targets, which are due within 24 months (by Dec 2027). About 98 % of emissions are in the value chain, mostly farming. |
| Mar 2026 | The CEO writes that having two growing regions (Finland and Sweden) reduces harvest risk. The 2026–28 strategy bets growth on frozen peas and Sweden. |
| 12 Aug 2026 | Heat and drought hit the Swedish pea crop. 2026 operating-profit guidance was cut to between −€2.0M and +€1.0M. |
| Ongoing | No biodiversity targets yet. A farm-level water-protection pilot with the Pyhäjärvi Institute started in 2025. |

Details and sources: [docs/APETIT_CONTEXT.md](docs/APETIT_CONTEXT.md)

## The five tracks (doing more of them does not score higher)

| Track | In plain words | Auto-scored? |
|---|---|---|
| **A** Data → inventory | Find the ~800 planted errors in the raw data and compute the 2025 carbon footprint with an audit trail | Yes |
| **B** Pathways | SBTi targets (incl. farmland/FLAG and base-year recalculation) and a cost curve of reduction actions | Jury only |
| **C** Climate risk to farming | Predict yields for 2027–31 and risk for 2041–60 under each climate scenario, then translate it into € and adaptation options | C1 and C2 yes, C3 jury |
| **D** Nature (SBTN) | Phosphorus and nitrogen runoff per catchment, a priority ranking, and a materials screening | D1 yes, D2 jury |
| **E** Copilot | Answer 34 questions with evidence (record keys, documents) | Numeric part yes |

Full detail, scoring formulas and traps: [docs/CHALLENGE.md](docs/CHALLENGE.md)

## How we are judged

**Apetit prize (our main target).** Apetit's own evaluators review every submission on Sun 10:00–13:00 and pick their top three: **€2,000 / €750 / €250**, announced at 13:30. There is no scheduled pitch to them, so **the submission is the pitch**. Confirm this with Apetit at the Q&A. The rubric in the data pack:

| Criterion | Weight | Full marks means |
|---|---|---|
| Usefulness for decisions | 30 % | An Apetit expert could act on it next week: priorities, € and t figures, actions with owners |
| Sound reasoning | 25 % | Correct GHG Protocol / SBTi / SBTN / scenario logic; assumptions stated; method changes not sold as reductions |
| Traceability + expert review | 25 % | Every number links to source records and factors; corrections logged; a human approves before publishing |
| Reliability | 10 % | Auto-scored results; robust to the planted data issues |
| Technical quality | 10 % | Runs end to end from the raw pack; reproducible; maps onto Apetit's Microsoft stack |

**Overall prize (bonus).** All builders vote between pairs of vote cards (tagline, start of the description, video, deck) on Sun 10:00–12:00. The top project from five different challenges becomes a finalist: a 4-minute live pitch plus 6 minutes of jury questions at 14:00. The winner gets **€5,000**.

## Key times (EET)

| When | What |
|---|---|
| Sat 09:00–12:00, 14:30–18:00 | Company Q&A at Joki. **Show Apetit an early version.** |
| Sun 10:00 | **Hard submission deadline**; voting opens |
| Sun 12:00 | Voting closes, five finalists confirmed |
| Sun 13:30 | Company top three announced |
| Sun 14:00 | Finals |

## Repo layout

```
AGENTS.md              rules for every AI agent working in this repo (read first)
CLAUDE.md              imports AGENTS.md for Claude Code
docs/                  SYSTEM_DESIGN (the plan), CONTRACTS, challenge, company context, agent guides
scripts/agent-chat.sh  helper for agents: chat, tasks, claims, worktrees, reviews
data/                  the data pack goes here locally (gitignored, never committed)
src/                   db, lineage, load, a_*, c_*, e_* modules (see SYSTEM_DESIGN)
app/                   Streamlit app
out/                   submission CSVs, corrections.csv, scores (rebuilt by `make all`)
tests/
```

## Getting started

Needs **Python 3.11+** (macOS ships 3.9; e.g. `uv venv --python 3.11 .venv` or `python3.11 -m venv .venv`).

```bash
git clone https://github.com/abhinavchutani/CtrlAltDelete.git
cd CtrlAltDelete
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # set AGENT_NAME etc.
```

Then unzip the data pack into `data/`. See [data/README.md](data/README.md).

## Reproduce every result

One command rebuilds every submission file from the unzipped pack (about **1 minute** on a laptop; no LLM key needed):

```bash
make all        # = make load a c e pitch
```

| Command | Builds | Output |
|---|---|---|
| `make load` | the pack's files, untouched, as `raw_*` / `task_*` tables | `out/navigator.duckdb` (gitignored) |
| `make a` | Track A: detectors, LLM triage (offline stub without a key), corrections, 2023–25 inventory, peat reveal | `out/A1_issues_submission.csv`, `out/A2_inventory_2025_submission.csv`, `out/corrections.csv`, `out/scores/A2_dev.json`, `out/scores/peat_reveal_2025.json` |
| `make c` | Track C: weather link, stage features, yield model + backtest, C1, C2 ensemble, C3 € risk, delivery changes | `out/C1_yields_2027_2031_submission.csv`, `out/C2_climate_yield_risk_submission.csv`, `out/scores/C1_backtest.json`, `C2_ensemble.json`, `C3_euro_risk.json` |
| `make d` | Track D1: 2025 Apetit-parcel P and N delivered to water per catchment (parcel index, delivery decay, retention; 2 scales calibrated on the 6 dev catchments) + SBTN-style priority rank | `out/D1_catchment_priority_submission.csv`, `out/scores/D1_dev.json` |
| `make e` | Track E: every question in `tasks/E_questions.csv` through the copilot | `out/E_answers_submission.csv` (+ E90–E92 dev check printed) |
| `make pitch` | every `{{placeholder}}` in METHOD_NOTE + `docs/pitch/` filled from `results` | `out/pitch/*.md`, `out/pitch/values.json` (value + source per number) |
| `make app` | the Streamlit app: data quality, inventory click-through, farm & peat, climate risk, review & publish, copilot | http://localhost:8501 |
| `make test` | the test suite (pack-dependent tests skip without data) | |

**Determinism.** A rerun on a fresh database reproduces the committed CSVs byte for byte. The only expected diff is the
git SHA recorded in `out/scores/A2_dev.json` (`method`). LLM calls, when a key is set, are cached by input hash in
`out/cache/` so reruns repeat them exactly.

**Results are drafts until a human publishes them.** With `NAVIGATOR_DEV_ASSUME=1` (the default in `.env.example`) the
pipelines apply proposed fixes as `DEV-ASSUMED` corrections so scores can be checked; a human expert approves and
publishes in the app's *Review & publish* page. **All figures come from the organisers' synthetic twin and are not
Apetit's real data.**

**Stop the app before `make all`**: while it runs it holds the DuckDB file lock.

## v2: the product (React app over one API)

v2 adds a **prediction layer** (scenarios, alerts, hedge, adaptation pathways), a **retrieval layer** (ask the data in
plain words, Excel reports, the decision board) and a **React app** on top of v1. It reads a frozen copy of v1's
database and never changes v1's CSVs. Design: [docs/V2_ARCHITECTURE.md](docs/V2_ARCHITECTURE.md). Demo script:
[docs/pitch/V2_DEMO.md](docs/pitch/V2_DEMO.md).

Needs the Python setup above, the unzipped pack, and **Node 18+** for the app. From a clean checkout:

```bash
make all            # v1: builds out/navigator.duckdb (~1 min; skip if you have it)
make snapshot       # out/navigator.duckdb → out/serve.duckdb (the frozen copy v2 reads)
make v2             # 6 scenario presets, weather frames, data catalog → out/v2/ (~20 s)
make api            # terminal 1: FastAPI on http://127.0.0.1:8000 (model warm-up ~10 s; /api/health shows `warming`)
make web            # terminal 2: React app on http://localhost:5173 (proxies /api to :8000)
```

| Command | What it checks or does |
|---|---|
| `make demo-check` | walks the demo through the real API, one `ok`/`FAIL` line per beat (needs `snapshot` + `v2`) |
| `make v2-check` | v2 tests, the v1-unchanged guard, `npm run build` and the TypeScript check |
| `API_MOCK=1 make api` | serves the committed fixtures instead of the real layers (no pack needed) |

- **No LLM key needed.** Text → scenario and the demo questions have offline rules. Every number in an answer must
  come from a tool result, or the answer is blocked (v1's post-check). The LLM tool loop for open questions is #93.
- **Human decisions are files.** Decision-board approvals append to `out/v2/decisions.jsonl` (git-ignored). Code never
  fills `decided_by`; a person types their name.
- **Same data rule as v1:** the twin is synthetic, so the app shows a banner saying so. € values are shown as bands.

## Deploy (Render, one Docker image)

The API serves the built web app on the same port, so one container is the whole product. The data pack and
`out/serve.duckdb` / `out/v2` are gitignored, so the image is built locally and pushed to a **private** registry;
Render runs that image. Apetit's own workbook (`data/00_apetit_original`, not CC BY) is left out of the image.

```bash
make snapshot && make v2                                     # if out/serve.duckdb or out/v2 is missing
docker login
scripts/build_image.sh <dockerhub-user>/field-radar:latest --push
```

On Render: **New → Web Service → Existing image** → `docker.io/<dockerhub-user>/field-radar:latest` (add the
registry credentials), instance type Free, health check path `/api/health`, and these env vars:
`LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` (see `.env.example`) and `APP_PASSWORD` (one shared password for
the whole app, so a public URL can't spend the LLM quota). Free instances sleep when idle: the first request
after a nap takes about a minute. The disk is ephemeral (Teach notes and the LLM cache reset on redeploy).

## Working with AI agents

Each of us can run an AI agent overnight. The agents coordinate through GitHub: one pinned **Agent chat** issue, task issues with claim labels, and PRs reviewed by another agent. Rules: [AGENTS.md](AGENTS.md). Human setup guide: [docs/AGENT_COLLAB.md](docs/AGENT_COLLAB.md).

**Data rule:** the pack is synthetic. Never present results as Apetit's real emissions or as facts about real farms.
