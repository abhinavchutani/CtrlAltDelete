"""Climate lane: stage features from daily weather, mirroring the simulator (task #16).

Run:  python -m src.c_features      (needs `python -m src.load`; writes table `c_stage_features`)

One row per (cell_id, scenario, year, crop, soil) for 1991–2060 and all four scenarios
(historical ≤ 2026; ssp126 / ssp245 / ssp585 ≥ 2027). The pack (SIMULATION_DESIGN §2–3) gives the
structure but not the parameters, so the values below are documented agronomic assumptions:

* Sowing: the first day from 1 April on which the 5-day mean temperature is ≥ the crop threshold
  (the window starts on 1 April, so warm springs sow on 5 April at the earliest; DOY 95).
* Stages by degree-days above 5 °C after sowing: early → sensitive (flowering / tuber initiation)
  → fill → maturity. A crop that hasn't reached maturity by 31 October is "immature".
* Soil-water bucket per soil class, full on 1 April. Daily: AET = PET × min(1, S / (0.5 × cap));
  S ← clip(S + P − AET, 0, cap). Drought stress = 1 − ΣAET / ΣPET over a stage.
* Stress features: drought by stage, hot days (Tmax ≥ 27 °C) in the sensitive stage and in fill,
  heavy-rain days (≥ 20 mm) in the 14 days after sowing (the model interacts this with clay),
  rain in the 14 days before maturity, season length, blight days (Jul–Aug, Tmean ≥ 15 °C and
  rain ≥ 1 mm) and beetle days (May, Tmax ≥ 15 °C).

Deterministic; no randomness. Every number comes from this code.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

import duckdb
import numpy as np
import pandas as pd

from src.db import connect


@dataclass(frozen=True)
class Crop:
    sow_t: float     # 5-day mean °C to sow
    sens: float      # GDD at start of the sensitive stage
    fill: float      # GDD at start of fill
    mature: float    # GDD at maturity / harvest


CROPS = {
    "pea": Crop(6.0, 450, 650, 900),
    "turnip_rape": Crop(6.0, 500, 700, 1100),
    "potato": Crop(8.0, 400, 700, 1400),
    "carrot": Crop(7.0, 600, 1000, 1500),
    "spinach": Crop(5.0, 250, 400, 550),
}
BUCKET_MM = {"sand": 60.0, "fine_sand": 90.0, "silt": 150.0, "clay": 130.0, "organic": 200.0}
GDD_BASE, HOT_C, HEAVY_MM, WINDOW_D = 5.0, 27.0, 20.0, 14
SEASON = ("04-01", "10-31")


def season_arrays(con: duckdb.DuckDBPyConnection) -> tuple[pd.DataFrame, dict[str, np.ndarray], np.ndarray]:
    """Daily Apr–Oct weather as arrays shaped (cell-year rows, days). Returns keys, arrays, day-of-year."""
    w = con.execute(f"""SELECT cell_id, scenario, year(date) AS year, dayofyear(date) AS doy, month(date) AS month,
                               tmean_c, tmax_c, precip_mm, pet_mm
                        FROM raw_weather_daily
                        WHERE strftime(date, '%m-%d') BETWEEN '{SEASON[0]}' AND '{SEASON[1]}'
                        ORDER BY cell_id, scenario, year, date""").df()
    w["d"] = w.groupby(["cell_id", "scenario", "year"]).cumcount()
    n_days = int(w["d"].max()) + 1
    keys = w[["cell_id", "scenario", "year"]].drop_duplicates().reset_index(drop=True)
    keys["row"] = np.arange(len(keys))
    w = w.merge(keys, on=["cell_id", "scenario", "year"])
    arr = {}
    for c in ("tmean_c", "tmax_c", "precip_mm", "pet_mm", "month"):
        a = np.full((len(keys), n_days), np.nan)
        a[w["row"].to_numpy(), w["d"].to_numpy()] = w[c].to_numpy()
        arr[c] = a
    # leap years have one day more; pad with the last value so cumulative sums stay defined
    for c in arr:
        a = arr[c]
        last = np.where(np.isnan(a[:, -1]), a[:, -2], a[:, -1])
        a[:, -1] = last
    return keys.drop(columns="row"), arr, np.arange(n_days)


def soil_water(precip: np.ndarray, pet: np.ndarray, cap: float) -> np.ndarray:
    """Daily actual ET from the bucket model (rows = cell-years, columns = days)."""
    s = np.full(precip.shape[0], cap)
    aet = np.empty_like(precip)
    for d in range(precip.shape[1]):
        a = pet[:, d] * np.minimum(1.0, s / (0.5 * cap))
        aet[:, d] = a
        s = np.clip(s + precip[:, d] - a, 0.0, cap)
    return aet


def first_true(mask: np.ndarray) -> np.ndarray:
    """Index of the first True per row; n_days if none."""
    has = mask.any(axis=1)
    return np.where(has, mask.argmax(axis=1), mask.shape[1])


def crop_features(arr: dict[str, np.ndarray], crop: Crop, aet: np.ndarray) -> dict[str, np.ndarray]:
    t, tx, p, pet, mon = arr["tmean_c"], arr["tmax_c"], arr["precip_mm"], arr["pet_mm"], arr["month"]
    n, nd = t.shape
    days = np.arange(nd)[None, :]
    t5 = pd.DataFrame(t.T).rolling(5, min_periods=5).mean().to_numpy().T
    sow = first_true(t5 >= crop.sow_t)
    after = days >= sow[:, None]
    gdd = np.cumsum(np.where(after, np.maximum(t - GDD_BASE, 0.0), 0.0), axis=1)
    i_sens, i_fill, i_mat = (first_true(gdd >= g) for g in (crop.sens, crop.fill, crop.mature))
    stage = {"early": (sow, i_sens), "sens": (i_sens, i_fill), "fill": (i_fill, i_mat)}
    out: dict[str, np.ndarray] = {"sow_doy": sow + 91.0}  # day 0 = 1 April = DOY 91 (non-leap)
    for name, (a, b) in stage.items():
        m = (days >= a[:, None]) & (days < b[:, None])
        sp, sa = (pet * m).sum(1), (aet * m).sum(1)
        out[f"drought_{name}"] = np.where(sp > 0, 1 - sa / np.where(sp > 0, sp, 1), 0.0)
        if name in ("sens", "fill"):
            out[f"hot_{name}"] = ((tx >= HOT_C) & m).sum(1).astype(float)
    w_sow = (days >= sow[:, None]) & (days < sow[:, None] + WINDOW_D)
    out["heavy_rain_after_sow"] = ((p >= HEAVY_MM) & w_sow).sum(1).astype(float)
    mat = np.minimum(i_mat, nd - 1)
    w_harv = (days > mat[:, None] - WINDOW_D) & (days <= mat[:, None])
    out["rain_before_harvest"] = (p * w_harv).sum(1)
    out["season_len"] = (np.minimum(i_mat, nd) - sow).astype(float)
    out["immature"] = (i_mat >= nd).astype(float)
    out["gdd_deficit"] = np.maximum(0.0, 1 - gdd[:, -1] / crop.mature)
    out["blight_days"] = (np.isin(mon, (7, 8)) & (t >= 15.0) & (p >= 1.0)).sum(1).astype(float)
    out["beetle_days"] = ((mon == 5) & (tx >= 15.0)).sum(1).astype(float)
    return out


def build(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    keys, arr, _ = season_arrays(con)
    parts = []
    for soil, cap in BUCKET_MM.items():
        aet = soil_water(arr["precip_mm"], arr["pet_mm"], cap)
        for name, crop in CROPS.items():
            f = pd.DataFrame(crop_features(arr, crop, aet))
            parts.append(pd.concat([keys, f], axis=1).assign(crop=name, soil=soil))
    df = pd.concat(parts, ignore_index=True)
    first = ["cell_id", "scenario", "year", "crop", "soil"]
    return df[first + [c for c in df.columns if c not in first]]


def write(con: duckdb.DuckDBPyConnection, df: pd.DataFrame) -> None:
    con.register("_f", df)
    con.execute("CREATE OR REPLACE TABLE c_stage_features AS SELECT * FROM _f")
    con.unregister("_f")


def main() -> None:
    t0 = time.time()
    con = connect()
    df = build(con)
    write(con, df)
    print(f"c_stage_features: {len(df):,} rows ({df.cell_id.nunique()} cells, "
          f"{df.year.min()}–{df.year.max()}, scenarios {sorted(df.scenario.unique())}) in {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
