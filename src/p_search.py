"""Prediction layer (v2): the plan finder. Many plans through the same engine, ranked (UI v3, `POST /api/search`).

Deterministic: the same engine, weather path and 2025 parcel mix as /api/simulate; nothing here is an LLM.
1. Singles: every change the engine can run, at a few settings each.
2. Combinations: the best setting of each change that helped on its own, in every combination of two or more.
3. Stress test: the top plans re-run under the other two climate futures ("does it still help if it gets hotter?").
Ranked by mean € at risk a year over the horizon (lower first); ties → fewer changes, then no assumption.
Exact € stay inside (`_eur`); only bands and words leave, like every other endpoint.
"""
from __future__ import annotations

import itertools
import time
from collections.abc import Callable, Iterator

import pandas as pd

from src import p_spec as S

MIN_GAIN = 0.05  # same threshold as p_compare.better: under 5 % is "about the same"
HIGH_EUR = 250_000  # a "costly year": € at risk at or above the €250k band edge (p_spec.EUR_BANDS)
STRESS_TOP = 3
Run = Callable[[dict], pd.DataFrame]  # cleaned spec → region × crop × year cube (p_engine.run_spec(...)[0])

FAMILIES: dict[str, list[tuple[str, dict]]] = {
    "irrigate_pea": [("irrigate_pea", {"type": "irrigate", "crop": "pea", "target": "drought_exposed"}),
                     ("irrigate_pea_all", {"type": "irrigate", "crop": "pea", "target": "all"})],
    "irrigate_potato": [("irrigate_potato", {"type": "irrigate", "crop": "potato", "target": "drought_exposed"})],
    "sow_early": [("sow_early_all", {"type": "earlier_sowing", "crop": "all"}),
                  ("sow_early_pea", {"type": "earlier_sowing", "crop": "pea"})],
    "split": [(f"split_{p}", {"type": "region_split", "crop": "pea", "fi_share": p / 100}) for p in (50, 60, 70, 80)],
    "heat": [(f"heat_pea_{y}", {"type": "heat_tolerant_variety", "crop": "pea", "from_year": y, "penalty_cut": 0.3})
             for y in (2028, 2030)],
}


def describe(lv: dict) -> str:
    """One change in plain words."""
    t = lv["type"]
    if t == "irrigate":
        return f"irrigate {'the driest' if lv.get('target', 'drought_exposed') == 'drought_exposed' else 'all'} {lv['crop']} fields"
    if t == "earlier_sowing":
        return "sow every crop earlier" if lv.get("crop", "all") == "all" else f"sow {lv['crop']} earlier"
    if t == "region_split":
        return f"buy {round(100 * lv['fi_share'])} % of pea from Finland"
    if t == "heat_tolerant_variety":
        return f"heat-tolerant pea from {lv['from_year']} (assumption)"
    if t == "crop_area":
        return f"{lv['crop']} area {lv['change_pct']:+.0f} % in {lv['region']}"
    return t.replace("_", " ")


def label(levers: list[dict]) -> str:
    text = " + ".join(describe(lv) for lv in levers) or "today's plan"
    return text[0].upper() + text[1:]


def mean_eur(cube: pd.DataFrame) -> float:
    return float(cube.groupby("year").eur_loss.sum().mean())


def year_stats(cube: pd.DataFrame) -> dict:
    """Costly years (€ at risk ≥ HIGH_EUR) and the worst year's band."""
    by_year = cube.groupby("year").eur_loss.sum()
    return {"costly_years": int((by_year >= HIGH_EUR).sum()), "worst_year": S.eur_band(float(by_year.max()))}


def _direction(new: float, old: float, down: str, up: str) -> str:
    rel = (new - old) / max(abs(old), 1.0)
    return down if rel < -MIN_GAIN else up if rel > MIN_GAIN else "same"


def summarise(cid: str, levers: list[dict], cube: pd.DataFrame, plan: pd.DataFrame, phase: str) -> dict:
    now, base = mean_eur(cube), mean_eur(plan)
    vs = {"lower": "better", "higher": "worse", "same": "same"}[_direction(now, base, "lower", "higher")]
    return {
        "id": cid, "label": label(levers), "levers": levers, "phase": phase,
        "eur_at_risk_per_year": S.eur_band(now),
        "saves": S.eur_band(base - now) if vs == "better" else None,
        "vs_current_plan": vs,
        **year_stats(cube), "plan_costly_years": year_stats(plan)["costly_years"],
        "co2e_direction": _direction(float(cube.import_tco2e.sum()), float(plan.import_tco2e.sum()), "lower", "higher"),
        "assumption": any(lv["type"] in S.ASSUMPTION_LEVERS for lv in levers),
        "_eur": now,
    }


def public(r: dict) -> dict:
    """What leaves the API: no exact €."""
    return {k: v for k, v in r.items() if not k.startswith("_")}


def rank(results: dict[str, dict]) -> list[str]:
    return sorted(results, key=lambda c: (results[c]["_eur"], len(results[c]["levers"]), results[c]["assumption"], c))


def search(run: Run, climate: str = "ssp245", horizon_end: int = 2040) -> Iterator[dict]:
    """Events: start → candidate × N (singles, then combinations) → stress × STRESS_TOP → done."""
    t0 = time.time()
    clean = lambda c, levers: S.validate({"climate": c, "horizon_end": horizon_end, "levers": levers})[0]  # noqa: E731
    plans: dict[str, pd.DataFrame] = {}

    def plan_of(c: str) -> pd.DataFrame:
        if c not in plans:
            plans[c] = run(clean(c, []))
        return plans[c]

    plan = plan_of(climate)
    singles = [(cid, lv) for opts in FAMILIES.values() for cid, lv in opts]
    total = len(singles)
    yield {"type": "start", "climate": climate, "horizon_end": horizon_end, "total": total,
           "years": horizon_end - S.FIRST_YEAR + 1,
           "plan": {"eur_at_risk_per_year": S.eur_band(mean_eur(plan)), **year_stats(plan)}}

    results: dict[str, dict] = {}
    for cid, lv in singles:
        results[cid] = summarise(cid, [lv], run(clean(climate, [lv])), plan, "single")
        yield {"type": "candidate", "done": len(results), "total": total, "candidate": public(results[cid])}

    # the best setting of each change that helped on its own, in every combination of two or more
    best_of = {}
    for fam, opts in FAMILIES.items():
        b = min((cid for cid, _ in opts), key=lambda c: results[c]["_eur"])
        if results[b]["vs_current_plan"] == "better":
            best_of[fam] = b
    lever_of = dict(singles)
    combos = [c for k in range(2, len(best_of) + 1) for c in itertools.combinations(best_of.values(), k)]
    total += len(combos)
    yield {"type": "phase", "phase": "combo", "total": total, "helped": list(best_of.values())}
    for combo in combos:
        cid, levers = "+".join(combo), [lever_of[c] for c in combo]
        results[cid] = summarise(cid, levers, run(clean(climate, levers)), plan, "combo")
        yield {"type": "candidate", "done": len(results), "total": total, "candidate": public(results[cid])}

    ranking = rank(results)
    for cid in ranking[:STRESS_TOP]:
        futures = {}
        for c in (c for c in S.CLIMATES if c != climate):
            r = summarise(cid, results[cid]["levers"], run(clean(c, results[cid]["levers"])), plan_of(c), "stress")
            futures[c] = {"vs_current_plan": r["vs_current_plan"], "eur_at_risk_per_year": r["eur_at_risk_per_year"],
                          "saves": r["saves"]}
        results[cid]["futures"] = futures
        yield {"type": "stress", "id": cid, "futures": futures}

    best = ranking[0] if results[ranking[0]]["vs_current_plan"] == "better" else None
    yield {"type": "done", "ranking": ranking, "best": best, "tested": len(results),
           "seconds": round(time.time() - t0, 1)}
