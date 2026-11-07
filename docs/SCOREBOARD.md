# Scoreboard (update in every PR that moves a number)

Goal bars and the plateau rule are in [END_GOAL.md](END_GOAL.md). Add a row to the attempt log for every scoring attempt. Never edit old rows.

## Current status

| G-box | Metric | Bar | Current | Status |
|---|---|---|---|---|
| G1 | A1 CSV | exists + valid | 133 issues, 18 types | ✅ (#12) |
| G1 | A2 CSV | exists + valid | all 19 template rows | ✅ (#12) |
| G1 | C1 CSV | exists + valid | 12,064 rows = template, final model (#17) | ✅ done |
| G1 | C2 CSV | exists + valid | 18 rows = template (#18) | ✅ done |
| G1 | E CSV | exists + valid | — | open (#23) |
| G2 | A1 dev score, overall | ≥ 80 | **96.69** (all 200 dev labels; P 0.98, R 0.95) | ✅ met |
| G2 | A2 dev score, 2023 / 2024 | ≥ 70 / ≥ 70 | **84.96 / 87.17** | ✅ met (cat01 −1.9 % / −0.1 %; 2024 Scope 2 market −5.9 % is the next lever) |
| G2 | C1 backtest MAPE / nRMSE | ≤ 8 % / ≤ 0.25 | **5.12 % / 0.115** (FI pea 2026 7.4 %, SE pea 2026 4.4 %) | ✅ met (#17) |
| G2 | C2 | ensemble built and documented | delta-method ensemble: 30 perturbed 1991–2020 years × 3 SSPs, 2025 parcel mix; cross-checked vs the pack realisation | ✅ done (#18) |
| G2 | E dev E90–E92 | 3/3 within tolerance | **3/3** (E90 0.0 %, E91 6.0 %, E92 1.7 %) | ✅ met (copilot #47 + A's interpolated meter months in #50) |
| G3 | App on real results; peat; C3 actions; click-through | done | — | open |
| G4 | Placeholders filled; `make all` from clean clone; CI green | done | — | open |

## Attempt log

| Date (EET) | PR | Metric | Before → after | Note |
|---|---|---|---|---|
| 2026-11-07 00:40 | #33 | A1 dev, farm tables only | — → 87.8 | 5 farm detectors; 5 soil misses are soil-map errors |
| 2026-11-07 00:55 | #37 | A1 dev, ops tables | — → 99.12 | ERP/energy/fuel/GoO/refrigerant + allow-list |
| 2026-11-07 01:05 | #9 PR | A1 dev, all labels | 95.16 (farm+ops) → 95.78 | + travel/shipments/waste/PCF/report/commuting (ops2 tables 100) |
| 2026-11-07 01:35 | #11 PR | A2 dev 2023 / 2024 | — → 91.32 / 67.62 | first inventory with corrections + organic soils |
| 2026-11-07 01:45 | #11 PR | A2 dev 2023 / 2024; A1 all | 91.32 / 67.62 → 91.47 / 74.83; A1 95.78 → 96.04 | stacked kWh+spike fix, year-level gap estimates, SEK capex lines |
| 2026-11-07 02:10 | #47 | E dev E90–E92 (offline stub, real 2024 inventory) | — → 2/3 | E90 6,399.9 exact, E92 175,045 vs 172,085 (1.7 %); E91 77.6 vs 62.9 (23 %, tolerance 10 %) follows A2 scope2_market |
| 2026-11-07 01:20 | #31 | C1 backtest MAPE / nRMSE | — → 8.20 % / 0.136 | monthly→seasonal ridge + farm effect, raw survey ×3 filter (baseline 9.89 % / 0.153) |
| 2026-11-07 01:50 | #39 | C1 backtest MAPE / nRMSE | 8.20 % → 8.16 % / 0.134 | clean_farm_survey labels |
| 2026-11-07 01:50 | #12 PR | A2 dev 2023 / 2024 | 91.47 / 74.83 → 91.32 / 85.88 | GoO from registry, interpolated meter months, estimation-uncertainty coverage rule, Bjuv Dec-only |
| 2026-11-07 02:20 | #12 PR | A2 dev 2024 | 85.88 → 74.89 | dropped the ±5 % 'treated as covered' rule after review: not GHG Protocol (only cancelled GoO MWh are covered) |
| 2026-11-07 02:20 | #17 PR | C1 backtest MAPE / nRMSE | 8.16 % / 0.134 → 5.12 % / 0.115 | stage features (#16) + ridge/GB average; CV 7.64 % → 6.14 % |
| 2026-11-07 02:45 | #54 | E dev E90–E92 (offline stub, real 2024 inventory) | 2/3 → 3/3 | E91 66.7 vs 62.9 (6.0 %, tolerance 10 %) after A's meter-estimate fix; no copilot change |
| 2026-11-07 02:45 | #18 PR | C2 | — → 18 rows | delta-method ensemble (no public truth); pack-realisation cross-check agrees in sign |
| 2026-11-07 06:30 | #13 PR | A1 all; A2 dev 2023 / 2024 | 96.04 → 96.69; 91.32 / 74.89 → 84.96 / 87.17 | soil_misreport needs crop+farm map agreement or the farm's own peat reports (8 of 11 false flags gone); peat only on reviewed-organic areas; stale issues retired on re-run |
