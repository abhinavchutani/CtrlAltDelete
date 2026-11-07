"""Prediction layer (v2): ScenarioSpec → yields on one plausible weather path → cube + SimResult (task #84, V2-5).

    from src import p_engine as P
    ctx = P.load_context()                      # once at API start-up (fits the v1 models, ~1 min)
    sim, cube = P.simulate(ctx, {"climate": "ssp245", "horizon_end": 2040, "levers": []})

* Weather: 2026 = the observed (historical) year; 2027…horizon = the pack's daily weather for the chosen SSP.
  That is **one plausible weather path**, labelled as such; risk odds come from the delta-method ensemble (c_ensemble).
* Yields: v1's fitted stage models (c_model) on the 2025 declared parcel mix with current management (held for
  every year; the 2027–31 plan mix is a later refinement). Baseline = the same model on 1991–2020 (c_ensemble).
* € at risk: v1's c_euro.losses (shortfall vs the baseline-mean contracted volume × 2025 price × premium);
  exact € stays inside, only bands (p_spec.eur_band) leave.
* Levers map onto v1 hooks (never edited, only imported):
  irrigate → c_euro.with_irrigation(c_euro.exposed_parcels | all parcels of the crop) as `pre_finish`;
  earlier_sowing → stage features rebuilt with c_euro.earlier_sowing_crops();
  heat_tolerant_variety → pea hot-day features × (1 − penalty_cut) from from_year (an ASSUMPTION);
  region_split / crop_area → contracted volume and production rescaled per region (area changes, same yields).
The engine reads only out/serve.duckdb (env SERVE_DB) through a private in-memory copy for v1's temp views.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from src import c_ensemble as E
from src import c_euro as C
from src import c_features
from src import c_model as M
from src import p_spec as S
from src.db import REPO_ROOT, env

BAD_FRACTION = E.BAD_FRACTION
HOT_COLS_PREFIX = ("st_hot_sens", "st_hot_fill")


def serve_db_path() -> Path:
    p = Path(env("SERVE_DB", "out/serve.duckdb")).expanduser()
    return p if p.is_absolute() else REPO_ROOT / p


def private_copy(path: Path | None = None) -> duckdb.DuckDBPyConnection:
    """In-memory DuckDB with read-only views over the snapshot; v1's temp views/tables land in memory only."""
    con = duckdb.connect(":memory:")
    con.execute(f"ATTACH '{path or serve_db_path()}' AS s (READ_ONLY)")
    for (name,) in con.execute("SELECT table_name FROM information_schema.tables WHERE table_catalog = 's'").fetchall():
        con.execute(f'CREATE VIEW main."{name}" AS SELECT * FROM s."{name}"')
    return con


@dataclass
class Ctx:
    con: duckdb.DuckDBPyConnection
    e: E.Context
    prices: pd.DataFrame
    factors: pd.DataFrame
    base_parcel: pd.DataFrame            # baseline 1991–2020 per-parcel predictions
    base_rc: pd.DataFrame                # region × crop baseline mean production (= contracted volume)
    stage: dict[str, pd.DataFrame] = field(default_factory=dict)   # climate → stage features on the path
    exposed: set[str] = field(default_factory=set)
    sowing_stage: dict[str, pd.DataFrame] = field(default_factory=dict)


def _predict(ctx_e: E.Context, wx: pd.DataFrame, st: pd.DataFrame, years, pre_finish=None) -> pd.DataFrame:
    X = E.scenario_features(ctx_e.con, ctx_e.mix, wx, st, years, ctx_e.static, ctx_e.lab, ctx_e.organic, ctx_e.med,
                            pre_finish)
    X = X.assign(yield_pred=M.predict_all(ctx_e.models, X).to_numpy())
    if X.yield_pred.isna().any():
        raise RuntimeError("p_engine: rows without a prediction")
    return X[["parcel_id", "farm_id", "region", "crop", "year", "area_ha", "yield_pred"]]


def load_context(path: Path | None = None) -> Ctx:
    con = private_copy(path)
    e = E.context(con)
    wx_b = e.wx_d[e.wx_d.scenario == "baseline"]
    st_b = e.st_d[e.st_d.scenario == "baseline"].drop(columns="scenario")
    base_parcel = _predict(e, wx_b, st_b, E.BASE_RANGE)
    base_rc = (base_parcel.assign(t=base_parcel.area_ha * base_parcel.yield_pred)
               .groupby(["region", "crop", "year"]).t.sum().groupby(["region", "crop"]).mean().rename("contracted_t").reset_index())
    return Ctx(con, e, C.prices(con), C.import_factor_t(con), base_parcel, base_rc, exposed=C.exposed_parcels(e))


def _path_stage(ctx: Ctx, climate: str, crops: dict | None = None) -> pd.DataFrame:
    """Stage features for 2026 (historical) + 2027… (the SSP path)."""
    cache = ctx.sowing_stage if crops else ctx.stage
    if climate not in cache:
        if crops:
            st = c_features.build(ctx.con, "raw_weather_daily", crops=crops)
            st = st.rename(columns={c: f"st_{c}" for c in st.columns if c not in ("cell_id", "scenario", "year", "crop", "soil")})
            hist, fut = st[st.scenario == "historical"], st[st.scenario == climate]
            hist, fut = hist.drop(columns="scenario"), fut.drop(columns="scenario")
        else:
            hist, fut = M.stage_features(ctx.con, "historical"), M.stage_features(ctx.con, climate)
        cache[climate] = pd.concat([hist[hist.year == S.FIRST_YEAR], fut[fut.year > S.FIRST_YEAR]], ignore_index=True)
    return cache[climate]


def _path_weather(ctx: Ctx, climate: str) -> pd.DataFrame:
    w = ctx.e.wx_hist
    return pd.concat([w[(w.scenario == "historical") & (w.year == S.FIRST_YEAR)],
                      w[(w.scenario == climate) & (w.year > S.FIRST_YEAR)]], ignore_index=True)


def _pre_finish(ctx: Ctx, levers: list[dict]):
    fns = []
    for lv in levers:
        if lv["type"] == "irrigate":
            crop_parcels = set(ctx.e.mix.loc[ctx.e.mix.crop == lv["crop"], "parcel_id"])
            target = ctx.exposed & crop_parcels if lv["target"] == "drought_exposed" else crop_parcels
            fns.append(C.with_irrigation(target))
        elif lv["type"] == "heat_tolerant_variety":
            cut, y0 = 1 - float(lv["penalty_cut"]), int(lv["from_year"])

            def heat(X: pd.DataFrame, cut=cut, y0=y0) -> pd.DataFrame:
                X = X.copy()
                rows = (X.crop == "pea") & (X.year >= y0)
                for c in [c for c in X.columns if c.startswith(HOT_COLS_PREFIX)]:
                    X.loc[rows, c] = X.loc[rows, c] * cut
                return X
            fns.append(heat)
    if not fns:
        return None

    def apply(X: pd.DataFrame) -> pd.DataFrame:
        for f in fns:
            X = f(X)
        return X
    return apply


def _volume_factors(ctx: Ctx, levers: list[dict]) -> pd.DataFrame:
    """Per region × crop multiplier on area (both production and contracted volume)."""
    f = ctx.base_rc[["region", "crop"]].assign(k=1.0)
    for lv in levers:
        if lv["type"] == "region_split":
            v = ctx.base_rc[ctx.base_rc.crop == "pea"].set_index("region").contracted_t
            now = float(v["FI_SW"] / v.sum())
            share = {"FI_SW": lv["fi_share"] / now, "SE_SKANE": (1 - lv["fi_share"]) / (1 - now)}
            for r, k in share.items():
                f.loc[(f.crop == "pea") & (f.region == r), "k"] *= k
        elif lv["type"] == "crop_area":
            f.loc[(f.crop == lv["crop"]) & (f.region == lv["region"]), "k"] *= 1 + lv["change_pct"] / 100
    return f


def run_spec(ctx: Ctx, spec: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(region × crop × year cube, farm × year cube) for a cleaned spec. Exact € inside."""
    years = range(S.FIRST_YEAR, spec["horizon_end"] + 1)
    levers = spec["levers"]
    sow = any(lv["type"] == "earlier_sowing" for lv in levers)
    st = _path_stage(ctx, spec["climate"], C.earlier_sowing_crops() if sow else None)
    par = _predict(ctx.e, _path_weather(ctx, spec["climate"]), st, years, _pre_finish(ctx, levers))
    k = _volume_factors(ctx, levers)
    par = par.merge(k, on=["region", "crop"], how="left").fillna({"k": 1.0})
    par["t"] = par.area_ha * par.yield_pred * par.k
    rc = par.groupby(["region", "crop", "year"]).t.sum().reset_index()
    base = ctx.base_rc.merge(k, on=["region", "crop"]).assign(t=lambda d: d.contracted_t * d.k)[["region", "crop", "t"]]
    loss = C.losses(base.assign(year=0), rc, ctx.prices)            # contracted = baseline mean × area factor
    loss = loss.merge(ctx.factors[["region", "crop", "net_tco2e_per_t"]], on=["region", "crop"], how="left")
    loss["import_tco2e"] = loss.shortfall_t * loss.net_tco2e_per_t.fillna(0.0)
    loss["change_pct"] = 100 * (loss.t / loss.contracted_t - 1)
    loss["bad_year"] = loss.t < BAD_FRACTION * loss.contracted_t
    loss["eur_band"] = loss.eur_loss.map(S.eur_band)
    fb = (ctx.base_parcel.assign(t=ctx.base_parcel.area_ha * ctx.base_parcel.yield_pred)
          .groupby(["farm_id", "year"]).t.sum().groupby("farm_id").mean().rename("base_t"))
    farm = par.assign(t0=par.area_ha * par.yield_pred).groupby(["farm_id", "year"]).t0.sum().reset_index().join(fb, on="farm_id")
    farm["change_pct"] = 100 * (farm.t0 / farm.base_t - 1)
    farm["risk"] = np.select([farm.change_pct <= -20, farm.change_pct <= -10], ["bad", "watch"], "ok")
    cols = ["region", "crop", "year", "t", "contracted_t", "change_pct", "bad_year", "shortfall_t", "eur_loss", "eur_band",
            "import_tco2e"]
    return loss[cols].sort_values(["region", "crop", "year"]).reset_index(drop=True), farm[["farm_id", "year", "change_pct", "risk"]]


def confidence(spec: dict) -> tuple[str, list[str]]:
    why = []
    if S.has_assumption(spec):
        why.append("assumption: heat-tolerant variety (penalty cut is not measured)")
    if spec["horizon_end"] > 2040:
        why.append("years beyond 2040")
    elif spec["horizon_end"] > 2031:
        why.append("years 2032–2040: one weather path, model trained on 2012–2025")
    else:
        why.append("near-term years 2026–2031")
    if any(lv["type"] == "irrigate" and lv.get("target") == "all" for lv in spec["levers"]):
        why.append("irrigating farms that never irrigated: outside the training range")
    level = "low" if (S.has_assumption(spec) or spec["horizon_end"] > 2040 or len(why) > 1 and "outside" in why[-1]) \
        else "medium" if spec["horizon_end"] > 2031 else "high"
    return level, why


def meters(spec: dict, cube: pd.DataFrame, plan: pd.DataFrame | None) -> dict:
    eur_year = cube.groupby("year").eur_loss.sum()
    co2 = float(cube.import_tco2e.sum())
    vs, co2_dir = "same", "same"
    if plan is not None:
        p_eur, p_co2 = float(plan.groupby("year").eur_loss.sum().mean()), float(plan.import_tco2e.sum())
        rel = (float(eur_year.mean()) - p_eur) / max(p_eur, 1.0)
        vs = "better" if rel < -0.05 else "worse" if rel > 0.05 else "same"
        rc = (co2 - p_co2) / max(p_co2, 1.0)
        co2_dir = "lower" if rc < -0.05 else "higher" if rc > 0.05 else "same"
    level, why = confidence(spec)
    return {"eur_at_risk_per_year": S.eur_band(float(eur_year.mean())), "vs_current_plan": vs, "co2e_direction": co2_dir,
            "confidence": level, "confidence_why": why}


def sim_result(sid: str, spec: dict, cube: pd.DataFrame, plan: pd.DataFrame | None) -> dict:
    regions = [{"region": r.region, "crop": r.crop, "year": int(r.year), "change_vs_baseline_pct": float(round(r.change_pct)),
                "eur_at_risk": r.eur_band, "bad_year": bool(r.bad_year)} for r in cube.itertuples(index=False)]
    return {"scenario_id": sid, "spec": spec, "years": list(range(S.FIRST_YEAR, spec["horizon_end"] + 1)),
            "regions": regions, "farms_url": f"/api/cube/{sid}/farms", "alerts": [],      # alerts: task #89
            "meters": meters(spec, cube, plan), "better": None, "synthetic": True}


def simulate(ctx: Ctx, spec: dict, sid: str | None = None, plan: pd.DataFrame | None = None) -> tuple[dict, dict]:
    """(SimResult dict, {'regions': cube, 'farms': farm cube, 'problems': [...], 'seconds': s})."""
    t0 = time.time()
    clean, problems = S.validate(spec)
    cube, farms = run_spec(ctx, clean)
    if plan is None and clean["levers"]:
        plan, _ = run_spec(ctx, {**clean, "levers": []})
    sim = sim_result(sid or S.scenario_id(clean), clean, cube, plan)
    return sim, {"regions": cube, "farms": farms, "problems": problems, "seconds": round(time.time() - t0, 1)}


if __name__ == "__main__":
    import json
    import sys
    t = time.time()
    ctx = load_context()
    print(f"context {time.time() - t:.1f}s")
    climate = sys.argv[1] if len(sys.argv) > 1 else "ssp245"
    sim, cube = simulate(ctx, {"climate": climate, "horizon_end": 2040, "levers": []}, sid=f"current_plan_{climate}")
    r = cube["regions"]
    print(f"simulate {cube['seconds']}s;", json.dumps(sim["meters"]))
    print(r[(r.crop == "pea") & (r.year <= 2030)][["region", "year", "t", "change_pct", "bad_year", "eur_band"]].round(1).to_string(index=False))
