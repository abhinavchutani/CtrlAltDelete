"""Climate lane: monthly-feature yield model → backtest → first C1 CSV (task #15).

Run:  python -m src.c_model            (needs `python -m src.load` and `python -m src.c_weather`)

Fast path of SYSTEM_DESIGN Track C (stage features from daily weather are #16):

* Labels: farm × crop × year yields.
  - FI: `clean_farm_survey` (Track A's corrections applied, #7) when that table exists. Fallback
    only: `raw_farm_survey_fi` with rows outside [median/3, 3 × median] of their crop dropped.
  - SE: Foodhills (`raw_foodhills_odlingsdata_se`), pea, yield = delivered t ÷ area ha.
* Features, built per parcel × year and area-weighted up to the farm's crop area for training:
  Apr–Sep monthly tmean, precip, PET, hot days (Tmax ≥ 27 °C) and water balance from the parcel's
  grid cell; soil class, clay %, slope, drainage; farm management (irrigation, N, sprays, organic).
* Model per crop: ridge regression on log(yield) + a shrunk per-farm effect (the hidden farmer
  skill) + Duan smearing back to t/ha. Deterministic: no random state anywhere.
* For 2027–31 management is each farm's last reported value for that crop (crop × region median
  if the farm never reported it). Weather is the pack's single ssp245 realisation.

Everything is computed by this code; no LLM touches a number.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

from src import lineage as L
from src.db import REPO_ROOT, connect, git_sha

CROPS = ("pea", "carrot", "spinach", "turnip_rape", "potato")
MONTHS = range(4, 10)
WVARS = ("tmean_c", "precip_mm", "pet_mm", "hot_days_tmax_ge_27")
SEASONS = {"am": (4, 5), "mj": (5, 6), "ja": (7, 8), "s": (9,)}   # monthly → seasonal means
SOILS = ("clay", "silt", "fine_sand", "sand", "organic")
OUTLIER_FACTOR = 3.0
RIDGE_ALPHA = 1000.0     # chosen by rolling-origin CV on 2020–2023 (see PR #15 notes), not on the test years
FARM_SHRINK = 2.0          # farm effect = Σ residual / (n + FARM_SHRINK)
TRAIN_END = 2023           # backtest: train ≤ 2023, test 2024–2026
TEST_YEARS = (2024, 2025, 2026)
MODEL_ID = "c_model:monthly_ridge_v1"
C1_PATH = REPO_ROOT / "out" / "C1_yields_2027_2031_submission.csv"
SCORES_PATH = REPO_ROOT / "out" / "scores" / "C1_backtest_monthly.json"


# ── weather and parcel features ───────────────────────────────────────
def cell_year_weather(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """One row per (cell_id, scenario, year) with Apr–Sep monthly columns, e.g. precip_mm_m6."""
    w = con.execute(f"SELECT cell_id, scenario, year, month, {', '.join(WVARS)} FROM raw_weather_monthly "
                    f"WHERE month BETWEEN {min(MONTHS)} AND {max(MONTHS)}").df()
    w["wb_mm"] = w["precip_mm"] - w["pet_mm"]
    wide = w.pivot_table(index=["cell_id", "scenario", "year"], columns="month",
                         values=[*WVARS, "wb_mm"], aggfunc="first")
    wide.columns = [f"{v}_m{m}" for v, m in wide.columns]
    return wide.reset_index()


def parcel_static(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    p = con.execute("""SELECT p.parcel_id, p.farm_id, p.area_ha, p.soil_class_soilmap AS soil,
                              p.clay_pct_soilmap AS clay_pct, p.slope_pct, p.drainage, pc.cell_id, pc.region
                       FROM raw_parcels p JOIN c_parcel_cell pc USING (parcel_id)""").df()
    for s in SOILS:
        p[f"soil_{s}"] = (p["soil"] == s).astype(float)
    p["drain_subsurface"] = (p["drainage"] == "subsurface").astype(float)
    return p.drop(columns=["soil", "drainage"])


def weather_cols(df: pd.DataFrame) -> list[str]:
    """Seasonal weather features (the model uses these; 30 monthly columns overfit in CV)."""
    return [c for c in df.columns if "_s" in c and c.rsplit("_s", 1)[-1] in SEASONS]


def add_seasons(df: pd.DataFrame) -> pd.DataFrame:
    for v in (*WVARS, "wb_mm"):
        for name, months in SEASONS.items():
            df[f"{v}_s{name}"] = df[[f"{v}_m{m}" for m in months]].mean(axis=1)
    return df


# ── labels and management ─────────────────────────────────────────────
def survey_table(con: duckdb.DuckDBPyConnection) -> str:
    """`clean_farm_survey` once Track A has built it, else the raw survey (fallback)."""
    have = con.execute("SELECT 1 FROM information_schema.tables WHERE table_name = 'clean_farm_survey'").fetchone()
    return "clean_farm_survey" if have else "raw_farm_survey_fi"


def labels(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Farm × crop × year yields (FI survey + SE Foodhills) with an `outlier` flag. The ×3 filter only
    applies to rows nobody has cleaned (raw survey fallback); cleaned rows keep real crop failures."""
    src_table = survey_table(con)
    fi = con.execute(f"""SELECT s.record_key, s.farm_id, s.crop, s.year, s.area_ha, s.yield_t_ha,
                               s.irrigated::DOUBLE AS irrigated, s.n_mineral_kg_ha + s.n_manure_kg_ha AS n_kg_ha,
                               s.sprays, 'FI_SW' AS region, {int(src_table == "clean_farm_survey")} AS cleaned
                        FROM {src_table} s""").df()
    se = con.execute("""SELECT 'foodhills:' || odlar_id || ':' || skördeår AS record_key, odlar_id AS farm_id,
                               'pea' AS crop, skördeår AS year, areal_ha AS area_ha,
                               levererad_mängd_ton / areal_ha AS yield_t_ha,
                               (bevattnad = 'ja')::DOUBLE AS irrigated, kvävegiva_kg_ha::DOUBLE AS n_kg_ha,
                               NULL::DOUBLE AS sprays, 'SE_SKANE' AS region, 0 AS cleaned
                        FROM raw_foodhills_odlingsdata_se WHERE areal_ha > 0""").df()
    lab = pd.concat([fi, se], ignore_index=True)
    lab = lab[lab["crop"].isin(CROPS) & lab["yield_t_ha"].notna() & (lab["area_ha"] > 0)].copy()
    med = lab.groupby(["crop", "region"])["yield_t_ha"].transform("median")
    far = (lab["yield_t_ha"] > OUTLIER_FACTOR * med) | (lab["yield_t_ha"] < med / OUTLIER_FACTOR)
    lab["outlier"] = far & (lab["cleaned"] == 0)
    lab.attrs["survey_table"] = src_table
    return lab.reset_index(drop=True)


def management_latest(lab: pd.DataFrame, upto: int) -> pd.DataFrame:
    """Each farm × crop's last reported irrigation / N / sprays up to `upto` (management is valid even
    when the yield is an outlier)."""
    m = lab[lab["year"] <= upto].sort_values("year").groupby(["farm_id", "crop"]).last()
    return m[["irrigated", "n_kg_ha", "sprays"]].reset_index()


def organic_farms(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return con.execute("SELECT farm_id, organic_certified::DOUBLE AS organic FROM raw_farm_registry").df()


# ── feature assembly ──────────────────────────────────────────────────
def farm_crop_year_features(con, lab: pd.DataFrame, static: pd.DataFrame, wx: pd.DataFrame) -> pd.DataFrame:
    """Area-weighted parcel features for each label row (parcels of that farm with that crop that year;
    all the farm's parcels if the declared history has none)."""
    hist = con.execute("SELECT parcel_id, farm_id, year, crop FROM raw_parcel_crop_history_and_plan "
                       "WHERE status = 'declared'").df()
    hist = hist.merge(lab[["farm_id", "crop", "year"]].drop_duplicates(), on=["farm_id", "crop", "year"])
    keyed = hist.merge(static.drop(columns=["farm_id"]), on="parcel_id")
    have = keyed[["farm_id", "crop", "year"]].drop_duplicates()
    missing = lab[["farm_id", "crop", "year"]].drop_duplicates().merge(have, how="left", indicator=True)
    missing = missing[missing["_merge"] == "left_only"].drop(columns="_merge")
    fallback = missing.merge(static, on="farm_id")
    rows = pd.concat([keyed, fallback], ignore_index=True)
    rows = rows.merge(wx[wx["scenario"] == "historical"].drop(columns="scenario"), on=["cell_id", "year"])
    num = [c for c in rows.columns if c not in ("parcel_id", "farm_id", "crop", "year", "cell_id", "region", "area_ha")]
    rows[num] = rows[num].mul(rows["area_ha"], axis=0)
    agg = rows.groupby(["farm_id", "crop", "year"])[num + ["area_ha"]].sum()
    agg[num] = agg[num].div(agg["area_ha"], axis=0)
    return agg.drop(columns="area_ha").reset_index()


def finish_features(df: pd.DataFrame, mgmt_fallback: pd.DataFrame) -> pd.DataFrame:
    """Fill missing management with crop × region medians and add interactions."""
    df = df.merge(mgmt_fallback, on=["crop", "region"], how="left", suffixes=("", "_med"))
    for c in ("irrigated", "n_kg_ha", "sprays"):
        df[c] = df[c].fillna(df[f"{c}_med"]).fillna(0.0)
        df = df.drop(columns=f"{c}_med")
    df["organic"] = df["organic"].fillna(0.0)
    for m in (6, 7):
        df[f"irr_x_wb_m{m}"] = df["irrigated"] * df[f"wb_mm_m{m}"]
    df["clay_x_precip_m5"] = df["clay_pct"] * df["precip_mm_m5"]
    df["is_se"] = (df["region"] == "SE_SKANE").astype(float)
    return add_seasons(df)


def feature_list(df: pd.DataFrame) -> list[str]:
    static = ["clay_pct", "slope_pct", "drain_subsurface", *[f"soil_{s}" for s in SOILS],
              "irrigated", "n_kg_ha", "sprays", "organic", "is_se",   # no year trend: worse in CV
              "irr_x_wb_m6", "irr_x_wb_m7", "clay_x_precip_m5"]
    return weather_cols(df) + [c for c in static if c in df.columns]


# ── model ─────────────────────────────────────────────────────────────
@dataclass
class CropModel:
    crop: str
    features: list[str]
    scaler: StandardScaler
    ridge: Ridge
    farm_effect: dict[str, float]
    smear: float
    n_train: int
    meta: dict = field(default_factory=dict)

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        z = self.scaler.transform(X[self.features].to_numpy(dtype=float))
        b = X["farm_id"].map(self.farm_effect).fillna(0.0).to_numpy()
        return np.exp(self.ridge.predict(z) + b) * self.smear


def fit_crop(df: pd.DataFrame, crop: str) -> CropModel:
    """Ridge on log(yield) with a shrunk farm effect, alternating twice; area-weighted."""
    feats = [f for f in feature_list(df) if df[f].std() > 0]
    X = df[feats].to_numpy(dtype=float)
    y = np.log(df["yield_t_ha"].to_numpy())
    w = df["area_ha"].to_numpy()
    scaler = StandardScaler().fit(X)
    z = scaler.transform(X)
    b = np.zeros(len(df))
    effect: dict[str, float] = {}
    for _ in range(3):
        ridge = Ridge(alpha=RIDGE_ALPHA).fit(z, y - b, sample_weight=w)
        res = pd.Series(y - ridge.predict(z), index=df.index)
        g = res.groupby(df["farm_id"])
        effect = (g.sum() / (g.size() + FARM_SHRINK)).to_dict()
        b = df["farm_id"].map(effect).to_numpy()
    resid = y - ridge.predict(z) - b
    smear = float(np.average(np.exp(resid), weights=w))
    return CropModel(crop, feats, scaler, ridge, effect, smear, len(df))


def fit_all(train: pd.DataFrame) -> dict[str, CropModel]:
    return {c: fit_crop(train[train["crop"] == c].reset_index(drop=True), c)
            for c in CROPS if (train["crop"] == c).sum() >= 20}


def predict_all(models: dict[str, CropModel], X: pd.DataFrame) -> pd.Series:
    out = pd.Series(np.nan, index=X.index)
    for c, m in models.items():
        idx = X.index[X["crop"] == c]
        if len(idx):
            out.loc[idx] = m.predict(X.loc[idx])
    return out


# ── backtest ──────────────────────────────────────────────────────────
def production_mape(df: pd.DataFrame, pred: str) -> pd.DataFrame:
    """C1 aggregate metric: |Σ area × pred − Σ area × actual| / Σ area × actual by region × crop × year."""
    g = df.assign(p_act=df["area_ha"] * df["yield_t_ha"], p_pred=df["area_ha"] * df[pred]) \
          .groupby(["region", "crop", "year"])[["p_act", "p_pred"]].sum()
    g["ape_pct"] = 100 * (g["p_pred"] - g["p_act"]).abs() / g["p_act"]
    return g.reset_index()


def nrmse(df: pd.DataFrame, pred: str) -> float:
    """RMSE / mean of actual yields, computed per crop and averaged (yields differ 30× between crops)."""
    vals = [np.sqrt(((g[pred] - g["yield_t_ha"]) ** 2).mean()) / g["yield_t_ha"].mean()
            for _, g in df.groupby("crop")]
    return float(np.mean(vals))


def backtest(data: pd.DataFrame) -> dict:
    train = data[data["year"] <= TRAIN_END]
    test = data[data["year"].isin(TEST_YEARS)].copy()
    models = fit_all(train)
    test["pred"] = predict_all(models, test).to_numpy()
    farm_mean = train.groupby(["farm_id", "crop"])["yield_t_ha"].mean().rename("baseline")
    test = test.join(farm_mean, on=["farm_id", "crop"])
    crop_mean = train.groupby(["crop", "region"])["yield_t_ha"].mean()
    test["baseline"] = test["baseline"].fillna(test.set_index(["crop", "region"]).index.map(crop_mean).to_series(index=test.index))
    mape_m, mape_b = production_mape(test, "pred"), production_mape(test, "baseline")
    cells = mape_m.merge(mape_b[["region", "crop", "year", "ape_pct"]], on=["region", "crop", "year"],
                         suffixes=("_model", "_baseline"))
    return {
        "train_years": f"≤{TRAIN_END}", "test_years": list(TEST_YEARS), "n_test_rows": int(len(test)),
        "production_mape_pct": {"model": round(float(mape_m["ape_pct"].mean()), 2),
                                "farm_mean_baseline": round(float(mape_b["ape_pct"].mean()), 2)},
        "farm_nrmse": {"model": round(nrmse(test, "pred"), 4), "farm_mean_baseline": round(nrmse(test, "baseline"), 4)},
        "by_region_crop_year": cells.round(2).to_dict(orient="records"),
        "note": "nRMSE is farm-level (labels are per farm); the C1 scorer uses parcel level.",
    }


# ── C1 run ────────────────────────────────────────────────────────────
def c1_features(con, static, wx, lab, organic, mgmt_med) -> pd.DataFrame:
    t = con.execute("SELECT parcel_id, farm_id, region, year, crop, area_ha FROM "
                    "task_template_C1_yields_2027_2031_submission").df()
    X = t.merge(static.drop(columns=["farm_id", "region", "area_ha"]), on="parcel_id", how="left")
    X = X.merge(wx[wx["scenario"] == "ssp245"].drop(columns="scenario"), on=["cell_id", "year"], how="left")
    X = X.merge(management_latest(lab, 2026), on=["farm_id", "crop"], how="left").merge(organic, on="farm_id", how="left")
    X = finish_features(X, mgmt_med)
    assert len(X) == len(t), "template rows lost in the feature join"
    return X


def build_training(con, lab, static, wx, organic, mgmt_med) -> pd.DataFrame:
    clean = lab[~lab["outlier"]]
    f = farm_crop_year_features(con, clean, static, wx)
    d = clean.merge(f, on=["farm_id", "crop", "year"], how="inner").merge(organic, on="farm_id", how="left")
    return finish_features(d, mgmt_med)


def write_results(con, models, bt: dict, c1: pd.DataFrame, survey: str) -> None:
    L.init_schema(con)
    by = f"c_model@{git_sha()}"
    model_src = [L.src("model", MODEL_ID), L.src("doc", "docs/SYSTEM_DESIGN.md#track-c-weather-yield-risk"),
                 L.src("doc", f"{survey}#labels", note="FI training labels"),
                 L.src("doc", "raw_foodhills_odlingsdata_se#labels", note="SE training labels")]
    for k, v in (("production_mape_pct", bt["production_mape_pct"]["model"]), ("farm_nrmse", bt["farm_nrmse"]["model"])):
        L.write_result(con, f"C1:backtest:{k}", metric=k, value=v, unit="pct" if "pct" in k else "ratio",
                       method=f"{MODEL_ID}, train ≤{TRAIN_END}, test 2024–26", produced_by=by,
                       category="all", year=2026, scenario="backtest",
                       lineage=model_src + [L.src("doc", "out/scores/C1_backtest_monthly.json")])
    prod = c1.assign(t=c1["area_ha"] * c1["yield_t_ha_pred"]).groupby(["region", "crop", "year"])["t"].sum()
    for (region, crop, year), t in prod.items():
        L.write_result(con, f"C1:{year}:{region}:{crop}:production", metric="production_t", value=float(t),
                       unit="t", method=f"{MODEL_ID}, Σ area × predicted yield", produced_by=by,
                       category=f"{region}:{crop}", year=int(year), scenario="ssp245",
                       lineage=model_src + [L.src("record", "tasks/templates/C1_yields_2027_2031_submission.csv"),
                                            L.src("doc", "04_climate/weather_daily_1991_2060.parquet#ssp245")])


def main() -> None:
    con = connect()
    static, wx, lab = parcel_static(con), cell_year_weather(con), labels(con)
    organic = organic_farms(con)
    mgmt_med = lab.groupby(["crop", "region"])[["irrigated", "n_kg_ha", "sprays"]].median().reset_index()
    print(f"labels: {len(lab):,} rows from {lab.attrs['survey_table']} + Foodhills; "
          f"{int(lab['outlier'].sum())} dropped by the ×{OUTLIER_FACTOR:g} filter (uncleaned rows only)")
    data = build_training(con, lab, static, wx, organic, mgmt_med)
    bt = backtest(data)
    print("backtest:", json.dumps({k: bt[k] for k in ("production_mape_pct", "farm_nrmse", "n_test_rows")}))
    models = fit_all(data)
    X = c1_features(con, static, wx, lab, organic, mgmt_med)
    X["yield_t_ha_pred"] = predict_all(models, X).round(3).to_numpy()
    if X["yield_t_ha_pred"].isna().any():
        raise RuntimeError(f"{int(X['yield_t_ha_pred'].isna().sum())} C1 rows without a prediction")
    cols = ["parcel_id", "farm_id", "region", "year", "crop", "area_ha", "yield_t_ha_pred"]
    C1_PATH.parent.mkdir(parents=True, exist_ok=True)
    X[cols].to_csv(C1_PATH, index=False)
    SCORES_PATH.parent.mkdir(parents=True, exist_ok=True)
    SCORES_PATH.write_text(json.dumps(bt, indent=2, ensure_ascii=False) + "\n")
    write_results(con, models, bt, X[cols], lab.attrs["survey_table"])
    print(f"C1: {len(X):,} rows → {C1_PATH.relative_to(REPO_ROOT)}")
    print(X.groupby(["region", "crop"])["yield_t_ha_pred"].mean().round(2).to_string())


if __name__ == "__main__":
    main()
