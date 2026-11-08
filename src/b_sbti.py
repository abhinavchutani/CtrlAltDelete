"""Track B (human request, 8 Nov): SBTi near-term targets and a decarbonisation pathway. Deterministic, no LLM.

    from src.b_sbti import pathway
    pathway(con, scenario="current_policies", lever_ids=["L11", "L13"], target_year=2030)

    python -m src.b_sbti [--scenario net_zero_2050] [--target-year 2030] [--levers L11 L13 ...]

Inputs (every number traces to one of these; each block returns its `sources`):
* base year: our 2025 inventory in `results` (S1, S2 market, S3, FLAG from Track A, peat soils included);
* rates: pack `07_frameworks/framework_digest.md` "Climate targets: SBTi": S1+2 4.2 %/yr (1.5 °C),
  S3 2.5 %/yr (well-below 2 °C), FLAG 3.03 %/yr, linear absolute contraction from the base year;
* BAU: base × `plant_based_demand_index` (pack `05_scenarios/transition_scenarios.csv`, illustrative), linear
  between the pack's years;
* levers: pack `05_scenarios/decarbonisation_levers.csv` (design estimates). Abatement ramps linearly from
  `earliest_start` over `ramp_years` to the design value and is capped at the bucket's BAU.

Rules that keep the pathway honest (AGENTS.md §8):
* L27 (better measurement) is `measurement`: it never reduces anything.
* L05 (Kantvik steam) and L26 (Pudasjärvi closure) are `structural`: boundary changes, recalculated into the
  base year, never counted as reductions.
* L10 (catch crops) is a `removal`: it counts only once monitored under the GHG Protocol LSR, so not here.
* FLAG sits inside Scope 3 cat 1, so the Scope 3 target covers non-FLAG Scope 3 (S3 − FLAG).
"""
from __future__ import annotations

import argparse
import json
from functools import lru_cache
from pathlib import Path

import duckdb
import pandas as pd

from src.load import pack_dir

BASE_YEAR = 2025
TARGET_YEARS = (2030, 2031, 2032, 2033, 2034, 2035)  # near-term: 5 years (V2) up to 10 years (V1.3.1)
DEFAULT_TARGET_YEAR = 2030
BUCKETS = ("s12", "s3", "flag")
BUCKET_LABEL = {"s12": "Scope 1+2 (market-based)", "s3": "Scope 3 excl. FLAG", "flag": "FLAG (land and farming)"}
RATE_PCT = {"s12": 4.2, "s3": 2.5, "flag": 3.03}
AMBITION = {"s12": "1.5 °C", "s3": "well-below 2 °C", "flag": "1.5 °C (FLAG)"}
SCENARIOS = ("current_policies", "net_zero_2050", "below_2c", "delayed_transition", "ndcs", "low_demand",
             "fragmented_world")
CLASS_NOTE = {
    "measurement": "Better measurement, not a reduction (L27): it changes the number, not the emissions.",
    "structural": "Structural change: recalculate the base year; never a reduction.",
    "removal": "Removal: counts only once monitored under the GHG Protocol LSR (from 2027).",
}
DIGEST = "pack data/07_frameworks/framework_digest.md · Climate targets: SBTi"
LEVERS_CSV = "pack data/05_scenarios/decarbonisation_levers.csv"
SCEN_CSV = "pack data/05_scenarios/transition_scenarios.csv"
HIST_CSV = "pack data/05_scenarios/published_inventory_history.csv"


def _src(kind: str, ref: str, label: str) -> dict:
    return {"kind": kind, "ref": ref, "label": label}


def _csv(rel: str) -> pd.DataFrame:
    return pd.read_csv(pack_dir() / "data" / rel)


# ── base year ──────────────────────────────────────────────────────
def base_year(con: duckdb.DuckDBPyConnection, year: int = BASE_YEAR) -> dict:
    """S1, S2 market, S3 and FLAG for `year` from Track A's results (draft or better)."""
    ids = {"s1": f"A2:{year}:actual:total:scope1_total", "s2m": f"A2:{year}:actual:total:scope2_market_total",
           "s3_total": f"A2:{year}:actual:total:scope3_total", "flag": f"A2:{year}:actual:flag:flag_total"}
    rows = dict(con.execute("SELECT result_id, value FROM results WHERE result_id IN (SELECT unnest(?))",
                            [list(ids.values())]).fetchall())
    missing = [k for k, rid in ids.items() if rid not in rows]
    if missing:
        raise LookupError(f"base year {year}: missing {missing} in results (run `make a` then `make snapshot`)")
    v = {k: float(rows[rid]) for k, rid in ids.items()}
    by = {"s12": v["s1"] + v["s2m"], "s3": v["s3_total"] - v["flag"], "flag": v["flag"]}
    total = sum(by.values())
    return {"year": year, "by_bucket": by, "total": total, "scope1": v["s1"], "scope2_market": v["s2m"],
            "scope3": v["s3_total"], "flag_share_pct": 100 * v["flag"] / total,
            "sources": [_src("result", rid, f"{year} inventory · {k}") for k, rid in ids.items()]}


def linear_target(base: float, rate_pct: float, y0: int, y1: int) -> float:
    """SBTi linear absolute contraction: base × (1 − r/100 × (Y1 − Y0)) (same rule as src/e_resolve.py)."""
    return base * (1 - rate_pct / 100 * (y1 - y0))


def targets(base: dict, target_year: int = DEFAULT_TARGET_YEAR) -> dict:
    y0 = base["year"]
    out = {}
    for b in BUCKETS:
        t = linear_target(base["by_bucket"][b], RATE_PCT[b], y0, target_year)
        out[b] = {"label": BUCKET_LABEL[b], "rate_pct_per_yr": RATE_PCT[b], "ambition": AMBITION[b],
                  "base_t": base["by_bucket"][b], "target_t": t,
                  "cut_pct": RATE_PCT[b] * (target_year - y0)}
    return {"base_year": y0, "target_year": target_year, "by_bucket": out,
            "flag_target_required": base["flag_share_pct"] >= 20,
            "sources": [_src("doc", DIGEST, "SBTi rates: 4.2 / 2.5 / 3.03 %/yr; FLAG target if FLAG ≥ 20 %")]}


# ── BAU ────────────────────────────────────────────────────────────
@lru_cache(maxsize=1)
def _demand() -> pd.DataFrame:
    return _csv("05_scenarios/transition_scenarios.csv").pivot(index="year", columns="scenario",
                                                               values="plant_based_demand_index")


def demand_index(scenario: str, year: int) -> float:
    d = _demand()
    if scenario not in d.columns:
        raise ValueError(f"unknown scenario {scenario!r}; one of {sorted(d.columns)}")
    s = d[scenario].dropna()
    full = s.reindex(range(min(s.index), max(s.index) + 1)).interpolate()
    year = min(max(year, int(full.index.min())), int(full.index.max()))
    return float(full[year] / full[BASE_YEAR])


# ── levers ─────────────────────────────────────────────────────────
def lever_class(row: pd.Series) -> tuple[str, str | None]:
    """(class, bucket). class ∈ reduction | measurement | structural | removal."""
    scope, lid = str(row.scope), str(row.lever_id)
    if scope == "measurement" or lid == "L27":
        return "measurement", None
    if scope in ("structural", "scope1_to_scope2") or row.lever_type == "structural":
        return "structural", None
    if lid == "L10" or "removals" in str(row.trade_offs).lower():
        return "removal", "flag"
    if scope.startswith("scope1") or scope.startswith("scope2"):
        return "reduction", "s12"
    return "reduction", "flag" if bool(row.flag) else "s3"


@lru_cache(maxsize=1)
def levers() -> tuple[dict, ...]:
    df = _csv("05_scenarios/decarbonisation_levers.csv")
    out = []
    for r in df.itertuples(index=False):
        s = pd.Series(r._asdict())
        cls, bucket = lever_class(s)
        cost = None if pd.isna(r.indicative_cost_eur_per_tco2e) else float(r.indicative_cost_eur_per_tco2e)
        out.append({"id": r.lever_id, "name": r.name, "class": cls, "bucket": bucket,
                    "abatement_t_design": float(r.abatement_tco2e_2030_design) if cls == "reduction" else 0.0,
                    "eur_per_t": cost, "start": int(r.earliest_start), "ramp_years": max(1, int(r.ramp_years)),
                    "confidence": r.confidence, "note": CLASS_NOTE.get(cls),
                    "source": _src("doc", f"{LEVERS_CSV} · {r.lever_id}", "design estimate (pack), not measured")})
    # MACC order: reductions by € per t (cheapest first), then the rest
    return tuple(sorted(out, key=lambda x: (x["class"] != "reduction", x["eur_per_t"] if x["eur_per_t"] is not None
                                            else 1e9, x["id"])))


def ramp(lever: dict, year: int) -> float:
    """Share of the design abatement reached in `year` (0 before the start, 1 after the ramp)."""
    return min(1.0, max(0.0, (year - lever["start"] + 1) / lever["ramp_years"]))


# ── pathway ────────────────────────────────────────────────────────
def history() -> list[dict]:
    h = _csv("05_scenarios/published_inventory_history.csv")
    out = []
    for r in h.itertuples(index=False):
        s3 = r.scope3_restated if pd.notna(r.scope3_restated) else r.scope3
        out.append({"year": int(r.year), "total_t": float(r.scope1 + r.scope2_market + s3),
                    "scope3_restated": bool(pd.notna(r.scope3_restated)), "note": str(r.note) if pd.notna(r.note) else ""})
    return out


def pathway(con: duckdb.DuckDBPyConnection, scenario: str = "current_policies", lever_ids: list[str] | None = None,
            target_year: int = DEFAULT_TARGET_YEAR, end_year: int = 2035) -> dict:
    if target_year not in TARGET_YEARS:
        raise ValueError(f"target_year must be one of {TARGET_YEARS} (SBTi near-term: 5–10 years)")
    base = base_year(con)
    tg = targets(base, target_year)
    chosen = set(lever_ids or [])
    known = {lv["id"] for lv in levers()}
    if unknown := sorted(chosen - known):
        raise ValueError(f"unknown lever ids {unknown}")
    active = [lv for lv in levers() if lv["id"] in chosen and lv["class"] == "reduction"]
    years = []
    for y in range(base["year"], end_year + 1):
        k = demand_index(scenario, y)
        row = {"year": y, "demand_index": round(k, 4)}
        for b in BUCKETS:
            bau = base["by_bucket"][b] * k
            cut = sum(lv["abatement_t_design"] * ramp(lv, y) for lv in active if lv["bucket"] == b)
            tgt = linear_target(base["by_bucket"][b], RATE_PCT[b], base["year"], min(y, target_year)) \
                if y <= target_year else None
            row[b] = {"bau_t": bau, "abated_t": min(cut, bau), "with_levers_t": bau - min(cut, bau), "target_t": tgt}
        for key in ("bau_t", "abated_t", "with_levers_t"):
            row[key] = sum(row[b][key] for b in BUCKETS)
        row["target_t"] = sum(row[b]["target_t"] for b in BUCKETS) if y <= target_year else None
        years.append(row)
    end = next(r for r in years if r["year"] == target_year)
    gap = {}
    for b in BUCKETS + ("total",):
        cell = end if b == "total" else end[b]
        need = cell["bau_t"] - cell["target_t"]
        gap[b] = {"gap_t": cell["with_levers_t"] - cell["target_t"], "needed_t": need,
                  "closed_pct": 100.0 if need <= 0 else max(0.0, min(100.0, 100 * cell["abated_t"] / need))}
    cost = sum(lv["abatement_t_design"] * ramp(lv, target_year) * (lv["eur_per_t"] or 0.0) for lv in active)
    return {"scenario": scenario, "base": base, "targets": tg, "years": years, "gap": gap,
            "levers": [dict(lv, selected=lv["id"] in chosen) for lv in levers()],
            "counted_lever_ids": [lv["id"] for lv in active],
            "ignored_lever_ids": sorted(chosen - {lv["id"] for lv in active}),
            "lever_cost_eur_per_yr": cost, "history": history(), "warnings": warnings(con, base),
            "sources": base["sources"] + tg["sources"] + [
                _src("doc", f"{SCEN_CSV} · {scenario} · plant_based_demand_index", "BAU growth (illustrative)"),
                _src("doc", LEVERS_CSV, "lever abatement and € per t (design estimates)"),
                _src("doc", HIST_CSV, "published history (restated Scope 3 where given)")],
            "synthetic": True}


# ── base-year warnings ─────────────────────────────────────────────
def warnings(con: duckdb.DuckDBPyConnection, base: dict) -> list[dict]:
    out = []
    peat = Path(__file__).resolve().parents[1] / "out/scores/peat_reveal_2025.json"
    if peat.is_file():
        p = json.loads(peat.read_text())
        out.append({"id": "peat", "title": "Peat soils are in our base year, not in the current calculator",
                    "body": (f"The farm calculator assumes mineral soil: {p['mineral_only_t']:,.0f} t. With drained "
                             f"organic soils it is {p['with_organic_soils_t']:,.0f} t (+{p['extra_from_peat_t']:,.0f} t, "
                             f"{p['farms_with_peat_emissions']} farms). Fix the calculator before the base year is set."),
                    "sources": [_src("result", "out/scores/peat_reveal_2025.json", "peat reveal 2025")]})
    ev = _csv("05_scenarios/structural_events.csv")
    for r in ev.itertuples(index=False):
        rel = str(r.relevance)
        if "recalculation" in rel or r.type in ("divestment_operational",) or "scope 1 biogenic" in rel:
            out.append({"id": f"event:{r.date}", "title": f"{r.event} ({r.date[:7]})", "body": rel[0].upper() + rel[1:]
                        + (". Not a reduction." if r.type != "acquisition" else "."),
                        "sources": [_src("doc", f"pack data/05_scenarios/structural_events.csv · {r.date}", r.type)]})
    return out


def serve(scenario: str = "current_policies", levers: list[str] | None = None,
          target_year: int = DEFAULT_TARGET_YEAR) -> dict:
    """The API's real layer (POST /api/sbti/pathway): reads out/serve.duckdb."""
    from src import serve_db
    with serve_db.connect() as con:
        return pathway(con, scenario, levers or [], target_year)


def main() -> None:
    from src import serve_db
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", default="current_policies", choices=SCENARIOS)
    ap.add_argument("--target-year", type=int, default=DEFAULT_TARGET_YEAR)
    ap.add_argument("--levers", nargs="*", default=[])
    a = ap.parse_args()
    p = pathway(serve_db.connect(), a.scenario, a.levers, a.target_year)
    b = p["base"]
    print(f"Base year {b['year']}: {b['total']:,.0f} t (FLAG {b['flag_share_pct']:.1f} %) · synthetic twin")
    for k, t in p["targets"]["by_bucket"].items():
        g = p["gap"][k]
        print(f"  {t['label']:<26} {t['base_t']:>10,.0f} → {t['target_t']:>10,.0f} t by {a.target_year} "
              f"(−{t['cut_pct']:.1f} %) · gap {g['gap_t']:>9,.0f} t · closed {g['closed_pct']:.0f} %")
    print(f"  total gap {p['gap']['total']['gap_t']:,.0f} t · levers counted {p['counted_lever_ids']} "
          f"ignored {p['ignored_lever_ids']} · € {p['lever_cost_eur_per_yr']:,.0f}/yr")


if __name__ == "__main__":
    main()
