# Scoreboard (update in every PR that moves a number)

Goal bars and the plateau rule are in [END_GOAL.md](END_GOAL.md). Add a row to the attempt log for every scoring attempt. Never edit old rows.

## Current status

| G-box | Metric | Bar | Current | Status |
|---|---|---|---|---|
| G1 | A1 CSV | exists + valid | — | open (#12) |
| G1 | A2 CSV | exists + valid | — | open (#12) |
| G1 | C1 CSV | exists + valid | — | open (#15 → #17) |
| G1 | C2 CSV | exists + valid | — | open (#18) |
| G1 | E CSV | exists + valid | — | open (#23) |
| G2 | A1 dev score, overall | ≥ 80 | **95.78** (all 200 dev labels; P 0.95, R 0.965) | ✅ met (#9) |
| G2 | A2 dev score, 2023 / 2024 | ≥ 70 / ≥ 70 | — | open |
| G2 | C1 backtest MAPE / nRMSE | ≤ 8 % / ≤ 0.25 | — | open |
| G2 | E dev E90–E92 | 3/3 within tolerance | — | open |
| G3 | App on real results; peat; C3 actions; click-through | done | — | open |
| G4 | Placeholders filled; `make all` from clean clone; CI green | done | — | open |

## Attempt log

| Date (EET) | PR | Metric | Before → after | Note |
|---|---|---|---|---|
| 2026-11-07 00:40 | #33 | A1 dev, farm tables only | — → 87.8 | 5 farm detectors; 5 soil misses are soil-map errors |
| 2026-11-07 00:55 | #37 | A1 dev, ops tables | — → 99.12 | ERP/energy/fuel/GoO/refrigerant + allow-list |
| 2026-11-07 01:05 | #9 PR | A1 dev, all labels | 95.16 (farm+ops) → 95.78 | + travel/shipments/waste/PCF/report/commuting (ops2 tables 100) |
