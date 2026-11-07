"""Deterministic question resolvers for the offline copilot (task #59).

General phrase rules over Track A's results (no per-question-id logic). Each rule maps the question to
explicit `results` filters, sums or combines the rows in code, and returns them as tool results so the
evidence lists every row and filter. A combined number (a share, a target) is returned as a `derived`
record with its formula and inputs, so the number check (src/e_check.py) can verify it.

Rules (first match wins; anything ambiguous returns None → "not in the data"):
* site lines   "<scope 1 + fuels | refrigerants | location/market-based Scope 2> … at <site> … <year>"
               site names from raw_sites; fuels from the line-item ids (e.g. LNG, LPG, light fuel oil)
* sea legs     "category 4 … sea legs … (bulk / reefer vessels / Ro-Pax)"
* method total "<plain scope question> after <method clause>" → the plain total (our pipeline applies it)
* peat share   "share … contract-farm … emissions … drained organic soils" → extra ÷ with-organic total
* SBTi target  "with <Y0> as base year … <r> %/yr linear … Scope 1+2 (market-based) … <Y1> … target"
               → (S1 + S2 market)_Y0 × (1 − r/100 × (Y1 − Y0))
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import duckdb

from src import e_tools

YEAR = re.compile(r"\b(20\d{2})\b")
SEA_MODES = {"bulk": "EF-TKM-SHIP-BULK", "reefer vessel": "EF-TKM-SHIP-REEFER", "ro-pax": "EF-TKM-ROPAX"}


@dataclass
class Resolved:
    value: float
    unit: str
    prose: str
    tool_results: list[dict]


def _sites(con: duckdb.DuckDBPyConnection) -> dict[str, str]:
    """lower-case name keyword → site_id, from raw_sites ('Säkylä plant' → 'säkylä')."""
    try:
        rows = con.execute("SELECT site_id, name FROM raw_sites").fetchall()
    except duckdb.Error:
        return {}
    out = {}
    for sid, name in rows:
        base = re.sub(r"\(.*?\)", "", str(name)).strip().lower()
        out[base.split()[0]] = sid
        if "head office" in base:
            out["head office"] = sid
    return out


def _site(con, q: str) -> str | None:
    hits = {sid for key, sid in _sites(con).items() if key in q}
    return hits.pop() if len(hits) == 1 else None


def _lines(con, year: int, scope: str, category: str, site: str, suffixes: list[str] | None = None) -> dict:
    """Line items `A2:{year}:actual:{scope}:{category}:{site}[:suffix]` via query_results (one call per filter)."""
    parts = [f"{category}:{site}:{s}" for s in suffixes] if suffixes else [f"{category}:{site}"]
    rows = []
    for p in parts:
        rows += e_tools.query_results(con, metric="tco2e_line", scope=scope, year=year, text=p, limit=50)["rows"]
    rows = list({r["result_id"]: r for r in rows}.values())
    return {"filters": {"metric": "tco2e_line", "scope": scope, "year": year, "text_any": parts},
            "n_rows": len(rows), "rows": rows, "sum": round(sum(r["value"] for r in rows), 6), "sum_unit": "t CO2e"}


def site_lines(con, q: str, year: int) -> Resolved | None:
    site = _site(con, q)
    if not site:
        return None
    if "refrigerant" in q or "fugitive" in q:
        res, what = _lines(con, year, "scope1", "fugitive_refrigerants", site), "refrigerant (fugitive) emissions"
    elif "location-based scope 2" in q:
        res, what = _lines(con, year, "scope2_location", "purchased_electricity", site), "location-based Scope 2 (electricity)"
    elif "market-based scope 2" in q:
        res, what = _lines(con, year, "scope2_market", "purchased_electricity", site), "market-based Scope 2 (electricity)"
    elif "scope 1" in q:
        ids = [r[0] for r in con.execute("SELECT result_id FROM results WHERE metric = 'tco2e_line' AND year = ? AND "
                                         "result_id LIKE ?", [year, f"%:stationary_and_mobile_combustion:{site}:%"]).fetchall()]
        carriers = sorted({i.rsplit(":", 1)[1] for i in ids})
        named = [c for c in carriers if c.replace("_", " ") in q]
        if not named:
            return None
        res, what = _lines(con, year, "scope1", "stationary_and_mobile_combustion", site, named), \
            f"Scope 1 combustion of {' + '.join(c.replace('_', ' ') for c in named)}"
    else:
        return None
    if not res["rows"]:
        return None
    return Resolved(res["sum"], "t CO2e", f"{res['sum']:,.1f} t CO2e: {what} at site `{site}` in {year} "
                                          f"(sum of `{res['n_rows']}` inventory line{'s' * (res['n_rows'] != 1)}).", [res])


def sea_legs(con, q: str, year: int) -> Resolved | None:
    if not ("category 4" in q and ("sea leg" in q or "vessel" in q)):
        return None
    efs = [ef for key, ef in SEA_MODES.items() if key in q] or list(SEA_MODES.values())
    rows = []
    for ef in efs:
        rows += e_tools.query_results(con, metric="tco2e_line", scope="scope3", year=year,
                                      text=f"cat04_upstream_transport:inbound:{ef}")["rows"]
    if not rows:
        return None
    res = {"filters": {"metric": "tco2e_line", "category": "cat04 inbound", "ef_ids": efs, "year": year},
           "n_rows": len(rows), "rows": rows, "sum": round(sum(r["value"] for r in rows), 6), "sum_unit": "t CO2e"}
    return Resolved(res["sum"], "t CO2e", f"{res['sum']:,.1f} t CO2e: category 4 inbound sea legs "
                                          f"({', '.join(f'`{e}`' for e in efs)}) in {year}.", [res])


def peat_share(con, q: str, year: int) -> Resolved | None:
    if not ("share" in q and "organic soil" in q and "farm" in q):
        return None
    extra = e_tools.query_results(con, metric="tco2e", year=year, text="extra_from_peat")
    total = e_tools.query_results(con, metric="farm_tco2e", year=year, scenario="with_organic_soils", category="all_farms")
    if not (extra["rows"] and total["rows"]):
        return None
    e, t = extra["rows"][0]["value"], total["rows"][0]["value"]
    v = round(100 * e / t, 4)
    derived = {"derived": {"formula": "100 × extra_from_peat ÷ with_organic_soils all_farms", "inputs": [e, t], "value": v}}
    return Resolved(v, "%", f"{v:.1f} % of {year} Finnish contract-farm emissions come from drained organic soils "
                            f"({e:,.0f} of {t:,.0f} t CO2e).", [extra, total, derived])


_BASE = re.compile(r"with (20\d{2}) as (?:the )?base year")
_RATE = re.compile(r"(\d+(?:\.\d+)?) ?%/yr")


def linear_target(con, q: str, year: int) -> Resolved | None:
    b, r = _BASE.search(q), _RATE.search(q)
    if not (b and r and "target" in q and "scope 1+2" in q and "market-based" in q) or "flag" in q:
        return None
    y0, rate = int(b.group(1)), float(r.group(1))
    later = [int(y) for y in YEAR.findall(q) if int(y) > y0]
    if len(set(later)) != 1:
        return None
    y1 = later[0]
    parts = [e_tools.query_results(con, metric="tco2e", scope="total", category=c, year=y0)
             for c in ("scope1_total", "scope2_market_total")]
    if not all(p["rows"] for p in parts):
        return None
    base = sum(p["rows"][0]["value"] for p in parts)
    v = round(base * (1 - rate / 100 * (y1 - y0)), 4)
    derived = {"derived": {"formula": f"(S1 + S2 market)_{y0} × (1 − {rate}/100 × ({y1} − {y0}))",
                           "inputs": [base, rate, y0, y1], "value": v}}
    return Resolved(v, "t CO2e", f"{v:,.1f} t CO2e in {y1}: the {y0} base of {base:,.1f} t (Scope 1 + Scope 2 "
                                 f"market) reduced linearly by {rate} % of the base per year.", parts + [derived])


RULES = (linear_target, peat_share, sea_legs, site_lines)


def resolve(con: duckdb.DuckDBPyConnection, question: str) -> Resolved | None:
    q = question.lower()
    years = [int(y) for y in YEAR.findall(q)]
    if not years:
        return None
    for rule in RULES:
        r = rule(con, q, years[0])
        if r is not None:
            return r
    return None


def strip_method_clause(question: str) -> str:
    """'… emissions in 2025 after reconciling X with Y (tCO2e)?' → '… emissions in 2025 (tCO2e)?'"""
    return re.sub(r"\s+after (?:reconciling|correcting)[^?(]*", " ", question).replace("  ", " ")
