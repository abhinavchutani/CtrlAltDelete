# Scoreboard (update in every PR that moves a number)

Goal bars and the plateau rule are in [END_GOAL.md](END_GOAL.md). Add a row to the attempt log for every scoring attempt. Never edit old rows.

## Current status

| G-box | Metric | Bar | Current | Status |
|---|---|---|---|---|
| G1 | A1 CSV | exists + valid | 133 issues, 18 types | ✅ (#12) |
| G1 | A2 CSV | exists + valid | all 19 template rows | ✅ (#12) |
| G1 | C1 CSV | exists + valid | — | open (#15 → #17) |
| G1 | C2 CSV | exists + valid | — | open (#18) |
| G1 | E CSV | exists + valid | — | open (#23) |
| G2 | A1 dev score, overall | ≥ 80 | **96.04** (all 200 dev labels; P 0.95, R 0.97) | ✅ met |
| G2 | A2 dev score, 2023 / 2024 | ≥ 70 / ≥ 70 | **91.32 / 85.88** | ✅ met; cat01 +1.1–1.7 % (soil-map peat share) is the next lever |
| G2 | C1 backtest MAPE / nRMSE | ≤ 8 % / ≤ 0.25 | — | open |
| G2 | E dev E90–E92 | 3/3 within tolerance | **2/3** (E90 0.0 %, E92 1.7 %; E91 23 % off) | open: E91 is the A2 2024 Scope 2 market gap (+23 %), not the copilot (#47) |
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
| 2026-11-07 01:50 | #12 PR | A2 dev 2023 / 2024 | 91.47 / 74.83 → 91.32 / 85.88 | GoO from registry, interpolated meter months, estimation-uncertainty coverage rule, Bjuv Dec-only |
