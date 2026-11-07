"""Climate lane: C2 climate yield risk 2041–2060 by region × crop × SSP (task #18).

Run:  python -m src.c_ensemble      (after `make c`; writes out/C2_climate_yield_risk_submission.csv)

The pack gives one weather realisation per SSP, but the C2 truth is a Monte Carlo. We therefore
build our own ensemble with the delta method (SYSTEM_DESIGN Track C step 7):

* Futures: each of the 30 baseline years 1991–2020 (historical daily weather, every cell) is
  perturbed with the pack's monthly `climate_change_signals` for 2041–2060 vs 1991–2020:
  Tmean/Tmax/Tmin + delta_tmean_c, precipitation × precip_factor, and PET rescaled by the
  Hargreaves temperature term (T + Δ + 17.8) / (T + 17.8). The wet-day factor is not applied
  (total precipitation is preserved). Scenario names: `baseline`, `delta_ssp126/245/585`.
* Features: the same code as training: monthly aggregates (`c_model.cell_year_weather`) and stage
  features (`c_features.build`) recomputed on the perturbed daily weather.
* Yields: the #17 ensemble (fitted on all labels) applied to the **2025 declared parcel mix** with
  each farm's latest management (current irrigation), as the C2 truth specifies.
* mean_yield_change_pct = Σ area × yield over the 30 future years ÷ the same over the 30 baseline
  years − 1. p_bad_year = share of the 30 future years whose region × crop production is below 80 %
  of the baseline mean.
* Cross-check (not submitted): the same model on the pack's own 2041–60 daily weather per SSP.

Assumptions: no CO2 fertilisation, no technology trend, no adaptation. Deterministic.
"""
from __future__ import annotations

import json

import duckdb
import numpy as np
import pandas as pd

from src import c_features, c_model as M
from src import lineage as L
from src.db import REPO_ROOT, connect, git_sha

BASE_YEARS = (1991, 2020)
FUTURE = (2041, 2060)
SSPS = ("ssp126", "ssp245", "ssp585")
BAD_FRACTION = 0.8
MIX_YEAR = 2025
C2_PATH = REPO_ROOT / "out" / "C2_climate_yield_risk_submission.csv"
SCORES_PATH = REPO_ROOT / "out" / "scores" / "C2_ensemble.json"
ENSEMBLE_ID = "c_ensemble:delta_method_v1"


def make_delta_weather(con: duckdb.DuckDBPyConnection) -> None:
    """View `c_weather_delta`: baseline 1991–2020 plus one perturbed copy per SSP (same columns as raw)."""
    y0, y1 = BASE_YEARS
    parts = [f"""SELECT cell_id, date, tmean_c, tmax_c, tmin_c, precip_mm, rad_mj_m2, pet_mm, 'baseline' AS scenario
                 FROM raw_weather_daily WHERE scenario = 'historical' AND year(date) BETWEEN {y0} AND {y1}"""]
    for ssp in SSPS:
        parts.append(f"""
            SELECT w.cell_id, w.date, w.tmean_c + s.delta_tmean_c, w.tmax_c + s.delta_tmean_c,
                   w.tmin_c + s.delta_tmean_c, w.precip_mm * s.precip_factor, w.rad_mj_m2,
                   w.pet_mm * greatest(w.tmean_c + s.delta_tmean_c + 17.8, 0.1) / greatest(w.tmean_c + 17.8, 0.1),
                   'delta_{ssp}'
            FROM raw_weather_daily w JOIN raw_climate_change_signals s
              ON s.scenario = '{ssp}' AND s.month = month(w.date)
            WHERE w.scenario = 'historical' AND year(w.date) BETWEEN {y0} AND {y1}""")
    con.execute("CREATE OR REPLACE VIEW c_weather_delta AS " + " UNION ALL ".join(parts))


def parcel_mix(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """2025 declared contract-crop parcels in the C2 region × crop combinations."""
    combos = con.execute("SELECT DISTINCT region, crop FROM task_template_C2_climate_yield_risk_submission").df()
    mix = con.execute(f"""SELECT h.parcel_id, h.farm_id, h.crop, pc.region, p.area_ha
                          FROM raw_parcel_crop_history_and_plan h JOIN raw_parcels p USING (parcel_id)
                          JOIN c_parcel_cell pc USING (parcel_id)
                          WHERE h.status = 'declared' AND h.year = {MIX_YEAR}""").df()
    return mix.merge(combos, on=["region", "crop"])


def scenario_features(con, mix: pd.DataFrame, wx: pd.DataFrame, stage: pd.DataFrame, years: range,
                      static: pd.DataFrame, lab: pd.DataFrame, organic: pd.DataFrame, med: pd.DataFrame) -> pd.DataFrame:
    """Parcel × weather-year features for one scenario (weather and stage tables already filtered)."""
    X = mix.assign(_k=1).merge(pd.DataFrame({"year": list(years), "_k": 1}), on="_k").drop(columns="_k")
    X = X.merge(static.drop(columns=["farm_id", "region", "area_ha"]), on="parcel_id", how="left")
    X = X.merge(wx.drop(columns="scenario"), on=["cell_id", "year"], how="left")
    X = X.merge(stage, on=["cell_id", "year", "crop", "soil"], how="left")
    X = X.merge(M.management_latest(lab, MIX_YEAR), on=["farm_id", "crop"], how="left")
    X = X.merge(organic, on="farm_id", how="left")
    return M.finish_features(X, med)


def production_by_year(models, X: pd.DataFrame) -> pd.DataFrame:
    X = X.assign(yield_pred=M.predict_all(models, X).to_numpy())
    if X["yield_pred"].isna().any():
        raise RuntimeError("C2: rows without a prediction")
    return (X.assign(t=X["area_ha"] * X["yield_pred"]).groupby(["region", "crop", "year"])["t"].sum().reset_index())


def risk(base: pd.DataFrame, fut: pd.DataFrame) -> pd.DataFrame:
    """mean_yield_change_pct and p_bad_year per region × crop (area is fixed, so production ∝ yield)."""
    bm = base.groupby(["region", "crop"])["t"].mean().rename("base_mean")
    f = fut.join(bm, on=["region", "crop"])
    out = f.groupby(["region", "crop"]).agg(fut_mean=("t", "mean")).join(bm)
    out["p_bad_year"] = f.assign(bad=f["t"] < BAD_FRACTION * f["base_mean"]).groupby(["region", "crop"])["bad"].mean()
    out["mean_yield_change_pct"] = 100 * (out["fut_mean"] / out["base_mean"] - 1)
    return out.reset_index()


def run(con: duckdb.DuckDBPyConnection) -> dict:
    static, lab, organic = M.parcel_static(con), M.labels(con), M.organic_farms(con)
    med = lab.groupby(["crop", "region"])[["irrigated", "n_kg_ha", "sprays"]].median().reset_index()
    wx_hist = M.cell_year_weather(con)
    models = M.fit_all(M.build_training(con, lab, static, wx_hist, organic, med))
    mix = parcel_mix(con)

    make_delta_weather(con)
    wx_d = M.cell_year_weather(con, "c_weather_delta")
    st_d = c_features.build(con, "c_weather_delta")
    st_d = st_d.rename(columns={c: f"st_{c}" for c in st_d.columns if c not in ("cell_id", "scenario", "year", "crop", "soil")})

    def prod(scen: str, wx: pd.DataFrame, st: pd.DataFrame, years: range) -> pd.DataFrame:
        X = scenario_features(con, mix, wx[wx.scenario == scen], st[st.scenario == scen].drop(columns="scenario"),
                              years, static, lab, organic, med)
        return production_by_year(models, X)

    base_years = range(BASE_YEARS[0], BASE_YEARS[1] + 1)
    base = prod("baseline", wx_d, st_d, base_years)
    rows, cross = [], {}
    base_bad = risk(base, base)[["region", "crop", "p_bad_year"]]
    for ssp in SSPS:
        r = risk(base, prod(f"delta_{ssp}", wx_d, st_d, base_years)).assign(scenario=ssp)
        rows.append(r)
        # cross-check on the pack's single 2041–60 realisation (historical-weather baseline, same model)
        st_p = M.stage_features(con, ssp)
        fut_p = prod(ssp, wx_hist, st_p.assign(scenario=ssp), range(FUTURE[0], FUTURE[1] + 1))
        cross[ssp] = risk(base, fut_p)[["region", "crop", "mean_yield_change_pct", "p_bad_year"]].round(3).to_dict("records")
    res = pd.concat(rows, ignore_index=True)
    return {"risk": res, "base_bad": base_bad, "cross_check_pack_realisation": cross, "n_parcels": len(mix),
            "mix_area_ha": float(mix.area_ha.sum())}


def write_csv(con, res: pd.DataFrame) -> pd.DataFrame:
    t = con.execute("SELECT region, crop, scenario, period FROM task_template_C2_climate_yield_risk_submission").df()
    out = t.merge(res[["region", "crop", "scenario", "mean_yield_change_pct", "p_bad_year"]],
                  on=["region", "crop", "scenario"], how="left")
    if out[["mean_yield_change_pct", "p_bad_year"]].isna().any().any():
        raise RuntimeError("C2: template rows without a value")
    out["mean_yield_change_pct"] = out["mean_yield_change_pct"].round(2)
    out["p_bad_year"] = out["p_bad_year"].round(3)
    C2_PATH.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(C2_PATH, index=False)
    return out


def write_results(con, out: pd.DataFrame, base_bad: pd.DataFrame) -> None:
    L.init_schema(con)
    by = f"c_ensemble@{git_sha()}"
    src = [L.src("model", M.MODEL_ID), L.src("model", ENSEMBLE_ID),
           L.src("doc", "04_climate/climate_change_signals.csv"),
           L.src("doc", "04_climate/weather_daily_1991_2060.parquet#historical 1991–2020"),
           L.src("doc", f"03_farming/parcel_crop_history_and_plan.csv#declared {MIX_YEAR}")]
    meth = f"{ENSEMBLE_ID}: 30 delta-perturbed 1991–2020 years, 2025 parcel mix, current management"
    for r in out.itertuples(index=False):
        cat = f"{r.region}:{r.crop}"
        L.write_result(con, f"C2:{r.scenario}:{cat}:yield_change_pct", metric="yield_change_pct",
                       value=float(r.mean_yield_change_pct), unit="%", method=meth, produced_by=by,
                       category=cat, scenario=r.scenario, lineage=src)
        L.write_result(con, f"C2:{r.scenario}:{cat}:p_bad_year", metric="p_bad_year", value=float(r.p_bad_year),
                       unit="share of years", method=meth, produced_by=by, category=cat, scenario=r.scenario,
                       lineage=src)
    for r in base_bad.itertuples(index=False):
        cat = f"{r.region}:{r.crop}"
        L.write_result(con, f"C2:baseline:{cat}:p_bad_year", metric="p_bad_year", value=float(r.p_bad_year),
                       unit="share of years", method=f"{ENSEMBLE_ID}: baseline 1991–2020", produced_by=by,
                       category=cat, scenario="baseline", lineage=src)


def main() -> None:
    con = connect()
    r = run(con)
    out = write_csv(con, r["risk"])
    write_results(con, out, r["base_bad"])
    SCORES_PATH.parent.mkdir(parents=True, exist_ok=True)
    SCORES_PATH.write_text(json.dumps({
        "method": ENSEMBLE_ID, "n_parcels_2025_mix": r["n_parcels"], "mix_area_ha": round(r["mix_area_ha"], 1),
        "submitted": out.round(3).to_dict("records"),
        "baseline_p_bad_year": r["base_bad"].round(3).to_dict("records"),
        "cross_check_pack_realisation_2041_2060": r["cross_check_pack_realisation"],
    }, indent=2, ensure_ascii=False) + "\n")
    print(f"C2: {len(out)} rows → {C2_PATH.relative_to(REPO_ROOT)} (2025 mix: {r['n_parcels']} parcels)")
    print(out.to_string(index=False))


if __name__ == "__main__":
    main()
