"""Climate lane: C3 — climate yield risk in €, replacement-import emissions and adaptation (task #19).

Run:  python -m src.c_euro      (after `make c`; writes results + out/scores/C3_euro_risk.json)

Builds on the C2 ensemble (src/c_ensemble.py): region × crop production for each of the 30
weather-years per scenario (baseline 1991–2020 and delta-method 2041–60 per SSP), 2025 parcel mix.

* Contracted volume V = baseline mean production. Shortfall in a year = max(0, V − production).
* € loss in a year = shortfall t × 2025 contract price × replacement-import premium: the extra cost of
  buying the missing volume as imports instead of paying the contract price
  (`05_scenarios/contract_prices_and_replacement_premiums.csv`). Reported as the expected €/yr
  (mean over the 30 years) and the 1-in-10-year loss (90th percentile).
* Replacement-import emissions: shortfall × (import factor + reefer truck transport − the domestic
  farm factor that is no longer emitted). The pack has no frozen-pea/potato import factor, so imported
  vegetables use the closest frozen-vegetable factor (EF-FROZ-CAUL-NL) and rapeseed uses EF-RAP-PL;
  transport assumes 1,500 km by reefer truck (EF-TKM-TRUCK-REEFER). These are stated proxies.
* Adaptation actions, each with €/yr avoided, t CO2e/yr avoided and an owner role:
  1. Two-region pea sourcing (procurement): one contracted pool across FI_SW + SE_SKANE vs two separate
     pools; the hedge is the expected loss avoided because a weak region is covered by a strong one in
     the same year. Illustrated with the observed 2026 split.
  2. Irrigation of drought-exposed pea and potato parcels (contract farming): the top quartile of
     flowering-stage drought (baseline years) that are not irrigated today get `irrigated = 1`.
  3. Earlier sowing (field advisors): sowing thresholds 1 °C lower for all crops, stage features
     recomputed.
Deterministic; every number is computed here and written to `results` with lineage.
"""
from __future__ import annotations

import dataclasses
import json

import duckdb
import numpy as np
import pandas as pd

from src import c_ensemble as E
from src import c_features
from src import lineage as L
from src.db import REPO_ROOT, connect, git_sha

PRICE_YEAR = 2025
IMPORT_EF = {"pea": "EF-FROZ-CAUL-NL", "potato": "EF-FROZ-CAUL-NL", "carrot": "EF-FROZ-CAUL-NL",
             "spinach": "EF-FROZ-CAUL-NL", "turnip_rape": "EF-RAP-PL"}
DOMESTIC_EF = {("FI_SW", "pea"): "EF-VEG-PEA-FI", ("FI_SW", "potato"): "EF-VEG-POT-FI",
               ("FI_SW", "carrot"): "EF-VEG-CAR-FI", ("FI_SW", "spinach"): "EF-VEG-SPI-FI",
               ("FI_SW", "turnip_rape"): "EF-RAP-FI", ("SE_SKANE", "pea"): "EF-VEG-PEA-SE"}
TRANSPORT_EF, TRANSPORT_KM = "EF-TKM-TRUCK-REEFER", 1500.0
IRRIGATION_CROPS, IRRIGATION_QUANTILE = ("pea", "potato"), 0.75
SOWING_SHIFT_C = 1.0
SCENARIOS = ("baseline", *E.SSPS)
SCORES_PATH = REPO_ROOT / "out" / "scores" / "C3_euro_risk.json"
MODEL_ID = "c_euro:shortfall_premium_v1"
OWNERS = {"two_region_pea": "procurement", "irrigation": "contract farming (field advisors)",
          "earlier_sowing": "contract farming (agronomy)"}


# ── inputs ────────────────────────────────────────────────────────────
def prices(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Contract price €/t and replacement premium per region × crop (pea_SE for Swedish peas)."""
    p = con.execute("SELECT item, contract_price_eur_t AS price, replacement_import_premium_frac AS premium "
                    "FROM raw_contract_prices_and_replacement_premiums WHERE year = ?", [PRICE_YEAR]).df()
    p["region"] = np.where(p["item"] == "pea_SE", "SE_SKANE", "FI_SW")
    p["crop"] = p["item"].str.replace("_SE", "", regex=False)
    return p[["region", "crop", "price", "premium"]]


def import_factor_t(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Net t CO2e per t of replacement import, per region × crop, with the factor ids used."""
    ef = dict(con.execute("SELECT ef_id, kgco2e_per_unit FROM raw_emission_factor_library").fetchall())
    rows = []
    for (region, crop), dom in DOMESTIC_EF.items():
        imp = IMPORT_EF[crop]
        net = ef[imp] + ef[TRANSPORT_EF] * TRANSPORT_KM / 1000 - ef[dom]   # kg/kg = t/t
        rows.append({"region": region, "crop": crop, "net_tco2e_per_t": net, "efs": [imp, TRANSPORT_EF, dom]})
    return pd.DataFrame(rows)


# ── € risk ────────────────────────────────────────────────────────────
def losses(base: pd.DataFrame, prod: pd.DataFrame, pr: pd.DataFrame) -> pd.DataFrame:
    """Per region × crop × year: shortfall t and € loss against the baseline-mean contracted volume."""
    v = base.groupby(["region", "crop"])["t"].mean().rename("contracted_t")
    d = prod.join(v, on=["region", "crop"]).merge(pr, on=["region", "crop"])
    d["shortfall_t"] = (d["contracted_t"] - d["t"]).clip(lower=0)
    d["eur_loss"] = d["shortfall_t"] * d["price"] * d["premium"]
    return d


def summarise(loss: pd.DataFrame, fac: pd.DataFrame) -> pd.DataFrame:
    g = loss.groupby(["region", "crop"]).agg(eur_at_risk=("eur_loss", "mean"),
                                             eur_at_risk_p90=("eur_loss", lambda s: float(np.quantile(s, 0.9))),
                                             shortfall_t=("shortfall_t", "mean"),
                                             contracted_t=("contracted_t", "first")).reset_index()
    g = g.merge(fac[["region", "crop", "net_tco2e_per_t"]], on=["region", "crop"], how="left")
    g["import_tco2e"] = g["shortfall_t"] * g["net_tco2e_per_t"]
    return g


def pooled_pea_loss(loss: pd.DataFrame) -> pd.Series:
    """€ loss per year if FI + SE pea volumes form one pool (shortfall in one covered by surplus in the other)."""
    p = loss[loss["crop"] == "pea"]
    w = p.pivot_table(index="year", columns="region", values=["t", "contracted_t", "price", "premium"])
    short = (w["contracted_t"].sum(axis=1) - w["t"].sum(axis=1)).clip(lower=0)
    unit = (w["contracted_t"] * w["price"] * w["premium"]).sum(axis=1) / w["contracted_t"].sum(axis=1)
    return short * unit


def observed_2026_split(con: duckdb.DuckDBPyConnection, lab_table: str) -> dict:
    """Observed pea yield in 2026 vs the 2012–25 mean, per region (area-weighted), and the pooled effect."""
    q = f"""
      WITH y AS (
        SELECT 'FI_SW' AS region, year, sum(area_ha * yield_t_ha) / sum(area_ha) AS y
          FROM {lab_table} WHERE crop = 'pea' GROUP BY 1, 2
        UNION ALL
        SELECT 'SE_SKANE', skördeår, sum(levererad_mängd_ton) / sum(areal_ha)
          FROM raw_foodhills_odlingsdata_se GROUP BY 1, 2)
      SELECT region, max(y) FILTER (WHERE year = 2026) / avg(y) FILTER (WHERE year < 2026) - 1 AS dev
      FROM y GROUP BY 1 ORDER BY 1"""
    dev = dict(con.execute(q).fetchall())
    return {f"{r}_2026_vs_mean_pct": round(100 * v, 1) for r, v in dev.items()}


def rebalance(loss: pd.DataFrame, step: float = 0.01) -> dict:
    """FI share of the contracted pea volume (total fixed) that minimises the expected pooled € loss.
    Each region's production scales with its contracted volume (same yields, more or less area)."""
    p = loss[loss["crop"] == "pea"].pivot_table(index="year", columns="region", values=["t", "contracted_t", "price", "premium"])
    v, t = p["contracted_t"].iloc[0], p["t"]
    unit = (p["price"] * p["premium"]).iloc[0]
    v_tot, s_now = float(v.sum()), float(v["FI_SW"] / v.sum())
    shares = np.round(np.arange(0.0, 1.0 + 1e-9, step), 4)
    exp_loss = []
    for s in shares:
        new_v = pd.Series({"FI_SW": s * v_tot, "SE_SKANE": (1 - s) * v_tot})
        prod = t["FI_SW"] * new_v["FI_SW"] / v["FI_SW"] + t["SE_SKANE"] * new_v["SE_SKANE"] / v["SE_SKANE"]
        cost = float((new_v * unit).sum() / v_tot)          # €/t of replacement for this mix
        exp_loss.append(float(((v_tot - prod).clip(lower=0) * cost).mean()))
    exp_loss = np.array(exp_loss)
    best = np.flatnonzero(np.isclose(exp_loss, exp_loss.min()))
    s_opt = float(shares[best[np.argmin(np.abs(shares[best] - s_now))]])   # tie → closest to today
    i_now = int(np.argmin(np.abs(shares - s_now)))
    return {"fi_share_now_pct": round(100 * s_now, 1), "fi_share_opt_pct": round(100 * s_opt, 1),
            "rebalance_pp": round(100 * (s_opt - s_now), 1),
            "eur_now": round(float(exp_loss[i_now]), 0), "eur_opt": round(float(exp_loss.min()), 0),
            "_curve": (shares, exp_loss, i_now)}


def robust_rebalance(per_scen: dict[str, dict]) -> dict:
    """The FI share whose *worst* relative gain across all scenarios is largest (robust to which future
    happens). The per-scenario optima move a lot because the loss curve is flat; this one does not."""
    shares = next(iter(per_scen.values()))["_curve"][0]
    gains = np.vstack([1 - c["_curve"][1] / c["_curve"][1][c["_curve"][2]] for c in per_scen.values()])
    worst = gains.min(axis=0)
    i = int(np.argmax(worst))
    now = next(iter(per_scen.values()))["fi_share_now_pct"]
    return {"fi_share_now_pct": now, "fi_share_opt_pct": round(100 * float(shares[i]), 1),
            "rebalance_pp": round(100 * float(shares[i]) - now, 1),
            "min_gain_pct": round(100 * float(worst[i]), 2), "max_gain_pct": round(100 * float(gains[:, i].max()), 2)}


# ── adaptation ────────────────────────────────────────────────────────
def exposed_parcels(ctx: E.Context) -> set[str]:
    """Pea/potato parcels in the top quartile of baseline flowering-stage drought, not irrigated today."""
    st = ctx.st_d[ctx.st_d.scenario == "baseline"].groupby(["cell_id", "crop", "soil"])["st_drought_sens"].mean()
    mix = ctx.mix.merge(ctx.static[["parcel_id", "cell_id", "soil"]], on="parcel_id")
    mix = mix[mix.crop.isin(IRRIGATION_CROPS)].join(st, on=["cell_id", "crop", "soil"])
    mgmt = ctx.lab.sort_values("year").groupby(["farm_id", "crop"])["irrigated"].last()
    mix = mix.join(mgmt, on=["farm_id", "crop"])
    thr = mix.groupby(["region", "crop"])["st_drought_sens"].transform(lambda s: s.quantile(IRRIGATION_QUANTILE))
    return set(mix[(mix["st_drought_sens"] >= thr) & (mix["irrigated"].fillna(0) < 0.5)]["parcel_id"])


def with_irrigation(parcels: set[str]):
    def f(X: pd.DataFrame) -> pd.DataFrame:
        X = X.copy()
        X.loc[X["parcel_id"].isin(parcels), "irrigated"] = 1.0
        return X
    return f


def earlier_sowing_crops() -> dict:
    return {k: dataclasses.replace(v, sow_t=v.sow_t - SOWING_SHIFT_C) for k, v in c_features.CROPS.items()}


# ── run ───────────────────────────────────────────────────────────────
def run(con: duckdb.DuckDBPyConnection) -> dict:
    ctx = E.context(con)
    pr, fac = prices(con), import_factor_t(con)
    base = E.production(ctx, "baseline")
    irr = exposed_parcels(ctx)
    st_sow = E.stage_delta(con, earlier_sowing_crops())
    out = {"risk": [], "actions": [], "n_irrigated_parcels": len(irr)}
    for scen in SCENARIOS:
        key = "baseline" if scen == "baseline" else f"delta_{scen}"
        loss = losses(base, E.production(ctx, key), pr)
        s = summarise(loss, fac).assign(scenario=scen)
        out["risk"].append(s)
        sep = loss[loss.crop == "pea"].groupby("year")["eur_loss"].sum()
        hedge = float(sep.mean() - pooled_pea_loss(loss).mean())
        l_irr = summarise(losses(base, E.production(ctx, key, pre_finish=with_irrigation(irr)), pr), fac)
        l_sow = summarise(losses(base, E.production(ctx, key, st=st_sow), pr), fac)
        for action, alt, crops in (("irrigation", l_irr, IRRIGATION_CROPS), ("earlier_sowing", l_sow, None)):
            a, b = s, alt
            if crops:
                a, b = s[s.crop.isin(crops)], alt[alt.crop.isin(crops)]
            out["actions"].append({"scenario": scen, "action": action,
                                   "eur_saved": float(a.eur_at_risk.sum() - b.eur_at_risk.sum()),
                                   "tco2e_avoided": float(a.import_tco2e.sum() - b.import_tco2e.sum())})
        short_sep = loss[loss.crop == "pea"].groupby("year")["shortfall_t"].sum().mean()
        p = loss[loss.crop == "pea"].pivot_table(index="year", columns="region", values=["t", "contracted_t"])
        short_pool = (p["contracted_t"].sum(axis=1) - p["t"].sum(axis=1)).clip(lower=0).mean()
        avg_fac = float(fac[fac.crop == "pea"].net_tco2e_per_t.mean())
        out.setdefault("rebalance", {})[scen] = rebalance(loss)
        out["actions"].append({"scenario": scen, "action": "two_region_pea", "eur_saved": hedge,
                               "tco2e_avoided": float((short_sep - short_pool) * avg_fac)})
    out["risk"] = pd.concat(out["risk"], ignore_index=True)
    out["actions"] = pd.DataFrame(out["actions"])
    obs = observed_2026_split(con, E.M.survey_table(con))
    v = base[base.crop == "pea"].groupby("region")["t"].mean()      # contracted pea volume per region
    pooled = sum(v[r] * obs[f"{r}_2026_vs_mean_pct"] for r in v.index) / v.sum()
    obs["pooled_FI_SE_2026_vs_mean_pct"] = round(float(pooled), 1)
    obs["contracted_share_FI_pct"] = round(float(100 * v["FI_SW"] / v.sum()), 1)
    out["observed_2026"] = obs
    out["rebalance"]["robust_all_scenarios"] = robust_rebalance(out["rebalance"])
    for v in out["rebalance"].values():
        v.pop("_curve", None)
    return out


def write_results(con: duckdb.DuckDBPyConnection, r: dict) -> None:
    L.init_schema(con)
    by = f"c_euro@{git_sha()}"
    base_src = [L.src("model", MODEL_ID), L.src("model", E.ENSEMBLE_ID),
                L.src("doc", "05_scenarios/contract_prices_and_replacement_premiums.csv#2025")]
    for x in r["risk"].itertuples(index=False):
        cat = f"{x.region}:{x.crop}"
        efs = [L.src("factor", e) for e in (IMPORT_EF[x.crop], TRANSPORT_EF, DOMESTIC_EF[(x.region, x.crop)])]
        for metric, val, unit in (("eur_at_risk", x.eur_at_risk, "€/yr"), ("eur_at_risk_p90", x.eur_at_risk_p90, "€ (1-in-10 yr)"),
                                  ("shortfall_t", x.shortfall_t, "t/yr"), ("import_tco2e", x.import_tco2e, "t CO2e/yr")):
            L.write_result(con, f"C3:{x.scenario}:{cat}:{metric}", metric=metric, value=float(val), unit=unit,
                           method=f"{MODEL_ID}: shortfall × price × premium; imports net of domestic factor",
                           produced_by=by, category=cat, scenario=x.scenario,
                           lineage=base_src + (efs if metric == "import_tco2e" else []))
    for scen, rb in r["rebalance"].items():
        scen = "all" if scen == "robust_all_scenarios" else scen
        for metric, unit in (("rebalance_pp", "percentage points"), ("fi_share_opt_pct", "%")):
            L.write_result(con, f"C3:{scen}:pea:{metric}", metric=metric, value=float(rb[metric]), unit=unit,
                           method=f"{MODEL_ID}: FI share of contracted pea volume minimising expected pooled € loss "
                                  f"(today {rb['fi_share_now_pct']} %)", produced_by=by, category="pea:FI_share",
                           scenario=scen, lineage=base_src)
    summary = {"two_region_pea": "eur_hedge", "irrigation": "eur_irrigation", "earlier_sowing": "eur_sowing"}
    for a in r["actions"].itertuples(index=False):
        cat = f"{a.action} | owner: {OWNERS[a.action]}"
        for metric, val, unit in (("eur_saved", a.eur_saved, "€/yr"), ("tco2e_avoided", a.tco2e_avoided, "t CO2e/yr"),
                                  (summary[a.action], a.eur_saved, "€/yr")):
            L.write_result(con, f"C3:{a.scenario}:{a.action}:{metric}", metric=metric, value=float(val), unit=unit,
                           method=f"{MODEL_ID}: avoided expected loss vs no action", produced_by=by, category=cat,
                           scenario=a.scenario, lineage=base_src)


def main() -> None:
    con = connect()
    r = run(con)
    write_results(con, r)
    SCORES_PATH.parent.mkdir(parents=True, exist_ok=True)
    SCORES_PATH.write_text(json.dumps({
        "method": MODEL_ID, "price_year": PRICE_YEAR, "n_irrigated_parcels": r["n_irrigated_parcels"],
        "observed_2026": r["observed_2026"], "pea_rebalance": r["rebalance"],
        "risk": r["risk"].round(1).to_dict("records"), "actions": r["actions"].round(1).to_dict("records"),
    }, indent=2, ensure_ascii=False) + "\n")
    print(r["risk"].pivot_table(index=["region", "crop"], columns="scenario", values="eur_at_risk").round(0).to_string())
    print(r["actions"].round(0).to_string(index=False))
    print("observed 2026:", r["observed_2026"])


if __name__ == "__main__":
    main()
