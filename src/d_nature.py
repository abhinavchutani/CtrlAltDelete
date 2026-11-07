"""Track D1: phosphorus and nitrogen that Apetit-contract parcels deliver to water in 2025, per catchment, and the
SBTN-style priority rank (task #80).

Run:  python -m src.d_nature        (after `make load` and `make a`; writes results + out/D1_catchment_priority_submission.csv)

Model (parcel level, deterministic; shapes from pack docs/SIMULATION_DESIGN.md §8 and NATURE_SBTN.md):
* Parcels: those growing an Apetit crop (pea, potato, carrot, spinach, turnip rape) in 2025, declared.
* P field loss ∝ area × (soil-P test / median)^0.5 × (1 + 0.15 × slope %) × 0.8 if a catch crop.
  A missing soil-P test (18 %) takes the catchment median.
* N field loss ∝ area × (1 + N surplus / 100) × 0.7 if a catch crop × 1.2 if subsurface-drained
  × (winter water surplus / median)². Winter water surplus = Oct–Apr rain − PET in the parcel's weather cell.
  N surplus = survey N in (mineral + manure) − yield × crop N removal; no survey → crop median.
* Delivery to water: exp(−distance / 300 m) for P, exp(−distance / 900 m) for N; then × (1 − catchment retention).
* Two global scale factors (kg/ha) are calibrated on the 6 public dev catchments (geometric mean of truth/model).
  Leave-one-out MAE of log10 on dev: P 0.025, N 0.040 (zero credit at 0.15). The shapes were chosen from a small grid
  by the same leave-one-out check; no per-catchment tuning.
* priority = (P / median(P) + 0.5 × N / median(N)) × state_weight × p_sensitivity  (public formula, task D1).
"""
from __future__ import annotations

import json
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from src import c_weather as W
from src import lineage as L
from src.db import REPO_ROOT, connect, git_sha
from src.load import pack_dir

YEAR = 2025
APETIT_CROPS = ("pea", "potato", "carrot", "spinach", "turnip_rape")
STATE_WEIGHT = {"good": 1.0, "moderate": 1.2, "poor": 1.5, "bad": 1.8}
N_REMOVAL_KG_T = {"pea": 0.0, "potato": 3.5, "carrot": 1.5, "spinach": 4.0, "turnip_rape": 35.0}  # legumes fix N
P_EXP, SLOPE_B, CATCH_P = 0.5, 0.15, 0.8
CATCH_N, SUBSURFACE_N, WS_EXP = 0.7, 1.2, 2.0
DELIV_P_M, DELIV_N_M = 300.0, 900.0
MODEL_ID = "d_nature:parcel_index_v1"
OUT = Path(REPO_ROOT) / "out"


def parcels(con: duckdb.DuckDBPyConnection, year: int = YEAR) -> pd.DataFrame:
    """2025 Apetit-crop parcels with soil, delivery, retention, N surplus and the winter water surplus."""
    crops = ",".join(f"'{c}'" for c in APETIT_CROPS)
    p = con.execute(f"""
        SELECT p.parcel_id, p.farm_id, p.catchment_id, p.area_ha, p.slope_pct, p.dist_to_water_m, p.drainage,
               p.p_test_mgl_latest, h.crop, h.catch_crop, k.nutrient_retention_frac_estimate AS retention
        FROM raw_parcels p JOIN raw_parcel_crop_history_and_plan h USING (parcel_id)
        JOIN raw_catchments k USING (catchment_id)
        WHERE h.year = ? AND h.status = 'declared' AND h.crop IN ({crops})""", [year]).df()
    p["p_test"] = p.p_test_mgl_latest.fillna(p.groupby("catchment_id").p_test_mgl_latest.transform("median"))
    p["p_test"] = p.p_test.fillna(p.p_test_mgl_latest.median())
    p = p.merge(n_surplus(con, year), on=["farm_id", "crop"], how="left")
    med = n_surplus(con, year).groupby("crop").n_surplus.median()
    p["n_surplus"] = p.n_surplus.fillna(p.crop.map(med)).fillna(0.0).clip(-50, 200)
    return p.merge(winter_surplus(con, year), on="parcel_id", how="left")


def n_surplus(con: duckdb.DuckDBPyConnection, year: int) -> pd.DataFrame:
    sv = con.execute("""SELECT farm_id, crop, n_mineral_kg_ha + n_manure_kg_ha AS n_in, yield_t_ha
                        FROM clean_farm_survey WHERE year = ?""", [year]).df()
    sv["n_surplus"] = sv.n_in - sv.yield_t_ha * sv.crop.map(N_REMOVAL_KG_T).fillna(10.0)
    return sv.groupby(["farm_id", "crop"]).n_surplus.mean().reset_index()


def winter_surplus(con: duckdb.DuckDBPyConnection, year: int) -> pd.DataFrame:
    """Oct–Apr rain − PET (mm, floor 10) of the calendar year, per parcel via its weather cell."""
    if not con.execute("SELECT count(*) FROM information_schema.tables WHERE table_name='c_parcel_cell'").fetchall()[0][0]:
        W.build_parcel_cell(con)
    w = W.weather(con, scenario="historical", start=f"{year}-01-01", end=f"{year}-12-31", columns=["precip_mm", "pet_mm"])
    w = w[pd.to_datetime(w.date).dt.month.isin([1, 2, 3, 4, 10, 11, 12])]
    cell = w.groupby("cell_id")[["precip_mm", "pet_mm"]].sum()
    ws = (cell.precip_mm - cell.pet_mm).clip(lower=10).rename("winter_surplus_mm").reset_index()
    link = con.execute("SELECT parcel_id, cell_id FROM c_parcel_cell").df()
    return link.merge(ws, on="cell_id")[["parcel_id", "winter_surplus_mm"]]


def parcel_index(p: pd.DataFrame) -> pd.DataFrame:
    """Unscaled delivered P and N per parcel (multiply by the calibrated kg/ha scale)."""
    keep = 1 - p.retention
    p = p.assign(
        p_idx=p.area_ha * (p.p_test / p.p_test.median()) ** P_EXP * (1 + SLOPE_B * p.slope_pct)
        * np.where(p.catch_crop, CATCH_P, 1.0) * np.exp(-p.dist_to_water_m / DELIV_P_M) * keep,
        n_idx=p.area_ha * (1 + p.n_surplus.clip(lower=0) / 100) * np.where(p.catch_crop, CATCH_N, 1.0)
        * np.where(p.drainage == "subsurface", SUBSURFACE_N, 1.0)
        * (p.winter_surplus_mm / p.winter_surplus_mm.median()) ** WS_EXP
        * np.exp(-p.dist_to_water_m / DELIV_N_M) * keep)
    return p


def calibrate(idx: pd.DataFrame, dev: pd.DataFrame) -> tuple[float, float, dict]:
    """Global kg/ha scales (geometric mean of truth / index over dev catchments) + leave-one-out log10 MAE."""
    m = dev.set_index("catchment_id").join(idx)
    out, loo = {}, {}
    for nut in ("p", "n"):
        r = np.log10(m[f"apetit_{nut}_to_water_kg"] / m[f"{nut}_idx"])
        out[nut] = float(10 ** r.mean())
        loo[nut] = round(float(np.mean([abs(r[j] - r.drop(j).mean()) for j in r.index])), 4)
    return out["p"], out["n"], loo


def priority(d: pd.DataFrame) -> pd.DataFrame:
    d = d.copy()
    d["priority"] = (d.P / d.P.median() + 0.5 * d.N / d.N.median()) * d.ecological_status_class.map(STATE_WEIGHT) \
        * d.p_sensitivity
    d["priority_rank"] = d.priority.rank(ascending=False, method="first").astype(int)
    return d


def run(con: duckdb.DuckDBPyConnection, write: bool = True) -> tuple[pd.DataFrame, dict]:
    p = parcel_index(parcels(con))
    idx = p.groupby("catchment_id")[["p_idx", "n_idx"]].sum()
    dev = con.execute("SELECT * FROM task_dev_D1_dev_catchments_2025").df()
    sp, sn, loo = calibrate(idx, dev)
    k = con.execute("SELECT * FROM raw_catchments").df().set_index("catchment_id")
    d = k.join(idx, how="left").fillna({"p_idx": 0.0, "n_idx": 0.0})
    d["P"], d["N"] = d.p_idx * sp, d.n_idx * sn
    d = priority(d[d.P > 0]).reset_index()
    meta = {"scale_p_kg_ha": round(sp, 4), "scale_n_kg_ha": round(sn, 4), "dev_loo_mae_log10": loo,
            "n_parcels": int(len(p)), "n_catchments": int(len(d)), "method": MODEL_ID}
    if write:
        write_results(con, d, meta)
    return d, meta


def write_results(con: duckdb.DuckDBPyConnection, d: pd.DataFrame, meta: dict) -> None:
    L.init_schema(con)
    by = f"d_nature@{git_sha()}"
    src = [L.src("model", MODEL_ID), L.src("doc", "06_nature/parcels + 03_farming/parcel_crop_history_and_plan#2025"),
           L.src("doc", "06_nature/catchments.csv#retention"), L.src("doc", "tasks/dev/D1_dev_catchments_2025.csv#calibration"),
           L.src("doc", "pack docs/NATURE_SBTN.md#D1 priority formula")]
    for r in d.itertuples(index=False):
        for metric, val, unit in [("p_to_water_kg", r.P, "kg P"), ("n_to_water_kg", r.N, "kg N"),
                                  ("priority", r.priority, "index"), ("priority_rank", r.priority_rank, "rank")]:
            L.write_result(con, f"D1:{YEAR}:{r.catchment_id}:{metric}", metric=metric, value=float(val), unit=unit,
                           category=r.catchment_id, year=YEAR, scenario="actual", produced_by=by, lineage=src,
                           method=f"{MODEL_ID}: parcel index × calibrated scale; LOO dev MAE log10 {meta['dev_loo_mae_log10']}")


def export(d: pd.DataFrame) -> pd.DataFrame:
    tmpl = pd.read_csv(pack_dir() / "tasks" / "templates" / "D1_catchment_priority_submission.csv")[["catchment_id", "region"]]
    out = tmpl.merge(d[["catchment_id", "P", "N", "priority_rank"]], on="catchment_id", how="left")
    out = out.rename(columns={"P": "apetit_p_to_water_kg", "N": "apetit_n_to_water_kg"})
    out["apetit_p_to_water_kg"] = out.apetit_p_to_water_kg.fillna(0.0).round(2)
    out["apetit_n_to_water_kg"] = out.apetit_n_to_water_kg.fillna(0.0).round(2)
    nxt = int(out.priority_rank.max()) if out.priority_rank.notna().any() else 0
    out["priority_rank"] = out.priority_rank.fillna(nxt + 1).astype(int)  # no Apetit sourcing → after all ranked ones
    out.to_csv(OUT / "D1_catchment_priority_submission.csv", index=False)
    return out


def main() -> None:
    con = connect()
    d, meta = run(con)
    out = export(d)
    (OUT / "scores").mkdir(parents=True, exist_ok=True)
    (OUT / "scores" / "D1_dev.json").write_text(json.dumps(meta, indent=1))
    print(f"D1: {len(out)} catchments → out/D1_catchment_priority_submission.csv; {json.dumps(meta)}")
    print(d.sort_values("priority_rank").head(5)[["catchment_id", "region", "ecological_status_class", "P", "N",
                                                  "priority", "priority_rank"]].round(1).to_string(index=False))


if __name__ == "__main__":
    main()
