"""Prediction layer (v2): adaptation pathways, tipping years and decide-by years (task #91, RISK_MITIGATION §4.2).

GET /api/pathways/{scenario_id}  →  list[PathwayItem] (api.schemas)

Per contract crop (pea, potato) × region of the scenario cube:
1. threshold: bad-year odds > 1 in 4 (TIP_ODDS, the same rule and 10-year window as p_alerts' tipping marker);
2. tipping year: the first year the 10-year rolling share of bad years (< 80 % of the 1991–2020 mean) on the weather
   path passes it; checked against the delta-method ensemble odds for 2041–60 (c_ensemble). When the two disagree,
   the threshold text says "indicative";
3. decide-by = tipping year − the option's longest lead time; None when the threshold is not crossed before the horizon;
4. signpost: a template filled with the 1-in-10 level (90th percentile, 1991–2020) of the driving hazard's indicator
   in that region, from the weather frames (p_weather).
Options: from the adaptation KB (kb/adaptation_options.csv via r_options.options(hazard, crop)), the top
KB_PER_HAZARD per driving hazard in KB rank order; lead times are the KB's indicative values (not yet reviewed by an
agronomist). If the KB is missing, the 5 engine-backed options below are used. The hazards that cost the most € on
the path pick them.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from src import p_alerts as A
from src.db import REPO_ROOT

V2 = REPO_ROOT / "out" / "v2"
# option_id: (option text, hazards, crops, lead time (min, max) years, simulated) — RISK_MITIGATION §7, indicative
OPTIONS: dict[str, tuple[str, tuple[str, ...], tuple[str, ...], tuple[int, int], str]] = {
    "A01": ("Efficient irrigation systems", ("H1",), ("pea", "potato"), (2, 3), "simulated"),
    "A04": ("Heat/drought-tolerant pea variety (breeding partnership / trials)", ("H1", "H2"), ("pea",), (8, 12), "assumption"),
    "A06": ("Earlier sowing to escape heat at flowering", ("H2", "H5"), ("pea", "turnip_rape"), (1, 1), "simulated_with_caveat"),
    "A07": ("Diversify sourcing regions (FI/SE portfolio)", ("H1", "H2", "H3", "H4", "H5"), ("pea",), (1, 1), "simulated"),
    "A08": ("Parcel selection: avoid poorly drained clay for sensitive crops", ("H3",), ("pea", "potato"), (1, 1), "simulated"),
}
PATHWAY_CROPS = ("pea", "potato")
KB_PER_HAZARD = 3


def kb_options(hazards: list[str], crop: str) -> list[tuple[str, str, tuple[str, ...], tuple[int, int], str, str]]:
    """(option_id, text, hazards, (lead min, max), simulated, matched hazard) from the KB, else from OPTIONS."""
    out: dict[str, tuple] = {}
    try:
        from src import r_options
        for h in hazards:
            for o in r_options.options(h, crop)[:KB_PER_HAZARD]:
                out.setdefault(o.option_id, (o.option_id, o.option, tuple(o.hazards), tuple(o.lead_time_yrs), o.simulated, h))
        if out:
            return list(out.values())
    except (ImportError, FileNotFoundError):
        pass
    for oid, (text, o_hz, o_crops, lead, sim) in OPTIONS.items():
        hit = next((h for h in hazards if h in o_hz), None)
        if crop in o_crops and hit:
            out[oid] = (oid, text, o_hz, lead, sim, hit)
    return list(out.values())
SIGNPOST_YEARS = (1991, 2020)


def threshold_text() -> str:
    return f"bad-year odds > 1 in {round(1 / A.TIP_ODDS)}"


def hazards_on_path(cube: pd.DataFrame, region: str, crop: str) -> list[str]:
    """Hazards ranked by the € they cost on this path (from each year's dominant stress driver)."""
    g = cube[(cube.region == region) & (cube.crop == crop)].copy()
    g["hazard"] = [(A.classify(d) or (None, None))[1] for d in g.driver]
    w = g.dropna(subset=["hazard"]).groupby("hazard").eur_loss.sum().sort_values(ascending=False)
    return [h for h, v in w.items() if v > 0]


def signpost_levels(climate_frames=None) -> dict[str, dict[str, float]]:
    """Per region: the 1991–2020 90th percentile of the flowering drought index and hot days (weather frames)."""
    from src import p_weather as W
    rows = []
    for y in range(SIGNPOST_YEARS[0], SIGNPOST_YEARS[1] + 1):
        f = climate_frames(y) if climate_frames else W.get_frame("historical", y)
        for c in f["cells"]:
            rows.append({"region": c["region"], "year": y, "drought": c["drought_index"], "hot": c["hot_days_flowering"]})
    d = pd.DataFrame(rows).groupby(["region", "year"])[["drought", "hot"]].mean().groupby("region").quantile(0.9)
    return {r: {"drought": float(v.drought), "hot": float(v.hot)} for r, v in d.iterrows()}


def signpost(hazard: str | None, region: str, levels: dict, crop: str = "pea") -> str:
    lv = levels.get(region, {})
    if hazard == "H1" and "drought" in lv:
        return (f"3 seasons in a row with the {crop} sensitive-stage drought index above {lv['drought']:.2f} in {region} "
                f"(a 1-in-10 level in {SIGNPOST_YEARS[0]}–{SIGNPOST_YEARS[1]})")
    if hazard == "H2" and "hot" in lv:
        n = int(np.ceil(lv['hot']))
        return (f"3 seasons in a row with more than {n} hot day{'s' * (n != 1)} (Tmax ≥ 27 °C) at {crop} flowering in "
                f"{region} (a 1-in-10 level in {SIGNPOST_YEARS[0]}–{SIGNPOST_YEARS[1]})")
    return f"2 bad years (< {A.BAD_FRACTION:.0%} of the 1991–2020 mean) within 5 seasons in {region}"


def items(cube: pd.DataFrame, climate: str, ensemble_odds: dict | None = None, levels: dict | None = None) -> list[dict]:
    """PathwayItem dicts for one scenario cube (exact numbers stay inside; only years and text leave)."""
    levels = levels or {}
    tips = {(t.region, t.crop): int(t.year) for t in A.tipping_years(cube).itertuples(index=False)}
    out = []
    for (region, crop), _ in cube[cube.crop.isin(PATHWAY_CROPS)].groupby(["region", "crop"]):
        hz = hazards_on_path(cube, region, crop) or ["H1"]
        tip = tips.get((region, crop))
        thr = threshold_text()
        odds = (ensemble_odds or {}).get((region, crop))
        if odds is not None and (odds > A.TIP_ODDS) != (tip is not None):
            thr += f" (indicative: ensemble 2041–60 odds {odds:.0%})"
        for oid, text, _, (lo, hi), sim, hit in kb_options(hz[:2], crop):
            out.append({"crop": crop, "region": region, "climate": climate, "threshold": thr, "tipping_year": tip,
                        "option_id": oid, "option": text, "decide_by": (tip - hi) if tip is not None else None,
                        "signpost": signpost(hit, region, levels, crop), "simulated": sim})
    return sorted(out, key=lambda i: (i["crop"] != "pea", i["region"], i["decide_by"] or 9999, i["option_id"]))


_ODDS: dict[str, dict] = {}
_CACHE: dict[str, list[dict]] = {}


def ensemble_odds(climate: str) -> dict[tuple[str, str], float]:
    """p_bad_year 2041–60 per region × crop from the delta-method ensemble (v1 c_ensemble.risk)."""
    if climate not in _ODDS:
        from src import c_ensemble as E, p_engine
        ctx = p_engine.warm()
        base = E.production(ctx.e, "baseline")
        r = E.risk(base, E.production(ctx.e, f"delta_{climate}"))
        _ODDS[climate] = {(x.region, x.crop): float(x.p_bad_year) for x in r.itertuples(index=False)}
    return _ODDS[climate]


def pathways(scenario_id: str) -> list[dict]:
    """GET /api/pathways/{id} (api/layers.py): presets from out/v2; unknown ids → []."""
    if "/" in scenario_id or ".." in scenario_id:
        return []
    if scenario_id not in _CACHE:
        f, s = V2 / "cube" / f"{scenario_id}.parquet", V2 / "scenarios" / f"{scenario_id}.json"
        if not (f.exists() and s.exists()):
            return []
        climate = json.loads(s.read_text())["spec"]["climate"]
        try:
            levels = signpost_levels()
        except FileNotFoundError:
            levels = {}
        _CACHE[scenario_id] = items(pd.read_parquet(f), climate, ensemble_odds(climate), levels)
    return _CACHE[scenario_id]


if __name__ == "__main__":
    import sys
    for it in pathways(sys.argv[1] if len(sys.argv) > 1 else "current_plan_ssp585"):
        print(f"{it['crop']:7} {it['region']:9} {it['option_id']} tip={it['tipping_year']} decide_by={it['decide_by']} "
              f"{it['simulated']:22} | {it['threshold']} | {it['signpost']}")
