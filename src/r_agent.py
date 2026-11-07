"""Retrieval layer (v2): ask a question about the past, get the answer, its table and its evidence (task #86, V2-9).

Run:  python -m src.r_agent "How did pea deliveries from Swedish farms in 2026 compare with 2021?"

`ask(question) -> dict` shaped like `AskOut` in docs/V2_ARCHITECTURE.md
(status, answer_md, table, evidence, report, pending_approval).

Offline (no LLM key) the demo questions go through deterministic routes; each route is one or two read-only SQL
queries (src.r_sql) or a docs search (src.r_docs). Rules, whatever the route:
* every number in answer_md must be a tool-returned number (v1's e_check post-check); otherwise the reply is blocked;
* evidence comes from the tool results (tables, pack files, record keys, passages), never from prose;
* no route or no rows → status "not_in_data" plus where the data might be (catalog search);
* draft results (pending expert approval) set pending_approval.
The LLM tool loop (task #93) will reuse the same tools and the same `finish`.
"""
from __future__ import annotations

import json
import re
import sys
from typing import Callable

import duckdb

from src import e_check, r_docs
from src import r_sql as S

TABLE_ROWS = 50
NOT_IN_DATA = "Not in the data."
Route = Callable[[duckdb.DuckDBPyConnection, str], dict | None]


# ── shaping ───────────────────────────────────────────────────────────
def ev(kind: str, ref: str, label: str) -> dict:
    return {"kind": kind, "ref": ref, "label": label}


def sql_evidence(res: dict) -> list[dict]:
    out = [ev("table_row", f"{t}", f"{t} ← {res['source_files'].get(t, 'derived table')}") for t in res["tables"]]
    out += [ev("table_row", k, k) for k in res["record_keys"][:10]]
    return out


def doc_evidence(res: dict) -> list[dict]:
    return [ev("doc", f"{p['file']}#{p['section']}", f"{p['file']} § {p['section']}") for p in res["passages"]]


def table_of(res: dict, n: int = TABLE_ROWS) -> dict:
    return {"columns": res["columns"], "rows": [[_plain(v) for v in r] for r in res["rows"][:n]]}


def _plain(v):
    return round(v, 3) if isinstance(v, float) else v if isinstance(v, (int, str, bool)) or v is None else str(v)


def finish(question: str, answer_md: str, results: list[dict], evidence: list[dict], table: dict | None = None,
           report: dict | None = None, pending: bool = False) -> dict:
    """AskOut, after the v1 number post-check: a number no tool returned blocks the reply."""
    bad = e_check.unsupported_numbers(answer_md, results, question)
    if bad:
        return not_in_data(f"Blocked: the draft answer had numbers no tool returned ({', '.join(bad)}).")
    if not evidence:
        return not_in_data("No tool result supports an answer.")
    return {"status": "answered", "answer_md": answer_md, "table": table, "evidence": list({e["ref"]: e for e in evidence}.values()),
            "report": report, "pending_approval": pending}


def not_in_data(why: str = "", hints: list[str] | None = None) -> dict:
    md = NOT_IN_DATA + (f" {why}" if why else "")
    if hints:
        md += "\n\nTables that might hold it: " + ", ".join(f"`{h}`" for h in hints)
    return {"status": "not_in_data", "answer_md": md, "table": None, "evidence": [], "report": None,
            "pending_approval": False}


def years_in(q: str) -> list[int]:
    return sorted({int(y) for y in re.findall(r"\b(19[89]\d|20[0-6]\d)\b", q)})


REPORT_RE = re.compile(r"\breport\b|excel|xlsx|spreadsheet|download|\bfile\b")


def wants_report(q: str) -> bool:
    return bool(REPORT_RE.search(q))


def maybe_report(con, q: str, template: str, params: dict) -> dict | None:
    """The .xlsx for this answer when the question asks for a report (#92); the answer stands without it."""
    if not wants_report(q):
        return None
    try:
        from src.r_report import make_report
        return make_report(con, template, params)
    except Exception:  # noqa: BLE001 — a failed file never blocks the answer
        return None


def previous_question(history: list[dict] | None) -> str | None:
    """The last user question in the chat history ({question} or {role: user, content})."""
    for h in reversed(history or []):
        text = h.get("question") or (h.get("content") if h.get("role", "user") == "user" else None)
        if text and str(text).strip():
            return str(text)
    return None


def fmt(x: float, d: int = 1) -> str:
    return f"{x:,.{d}f}"


# ── routes (the 5 demo questions + v1's scope totals) ────────────────
def route_se_pea_deliveries(con, q: str) -> dict | None:
    if not (re.search(r"deliver", q) and re.search(r"swed|\bse\b|foodhills|sk[aå]ne", q) and re.search(r"\bpeas?\b|ärt", q)):
        return None
    yrs = years_in(q) or [2021, 2026]
    ph = ",".join("?" * len(yrs))
    res = S.run_sql(f"""SELECT skördeår AS harvest_year, round(sum(levererad_mängd_ton), 1) AS delivered_t,
                               count(DISTINCT odlar_id) AS growers, round(sum(areal_ha), 1) AS area_ha,
                               round(sum(levererad_mängd_ton) / sum(areal_ha), 2) AS t_per_ha
                        FROM raw_foodhills_odlingsdata_se WHERE gröda LIKE 'Ärt%' AND skördeår IN ({ph})
                        GROUP BY 1 ORDER BY 1""", yrs, con=con)
    if not res["rows"]:
        return not_in_data(f"No Swedish pea deliveries for {yrs}.", ["raw_foodhills_odlingsdata_se"])
    rows = {r[0]: r for r in res["rows"]}
    parts = [f"{y}: {fmt(r[1])} t from {r[2]} growers ({fmt(r[4], 2)} t/ha)" for y, r in rows.items()]
    derived = {}
    if len(rows) >= 2:
        a, b = rows[min(rows)], rows[max(rows)]
        chg = round(100 * (b[1] / a[1] - 1), 1)
        derived = {"derived": {"formula": f"({max(rows)} t / {min(rows)} t − 1) × 100", "value": chg}}
        parts.append(f"change {min(rows)}→{max(rows)}: {chg:+.1f} %")
    md = ("Swedish pea deliveries (Foodhills grower records, harvest year): " + "; ".join(parts) + ".\n\n"
          "*Synthetic twin data. Source: the Swedish grower file (columns skördeår, gröda, levererad_mängd_ton).*")
    evidence = sql_evidence(res) + ([ev("assumption", "derived:change_pct", derived["derived"]["formula"])] if derived else [])
    report = maybe_report(con, q, "deliveries_by_farm_year", {"region": "SE_SKANE", "crop": "pea", "years": yrs})
    return finish(q, md, [res, derived], evidence, table_of(res), report=report)


def route_peat_as_mineral(con, q: str) -> dict | None:
    if not (re.search(r"peat|organic soil", q) and re.search(r"mineral|calculat", q)):
        return None
    yr = (years_in(q) or [2025])[-1]
    res = S.run_sql("""SELECT farm_id, crop, year, area_ha, record_key FROM raw_farm_survey_fi
                       WHERE soil_type_reported = 'Organic soil' AND year = ? ORDER BY farm_id, crop""", [yr], con=con)
    mis = S.run_sql("""SELECT count(DISTINCT c.record_key) AS soil_corrections FROM corrections c
                       WHERE c.field = 'soil_type_reported' AND c.record_key IN
                             (SELECT record_key FROM raw_farm_survey_fi WHERE year = ?)""", [yr], con=con)
    calc = S.run_sql("""SELECT DISTINCT calculator_note FROM raw_current_calculator_footprints LIMIT 3""", con=con)
    docs = r_docs.search_docs("current calculator assumes mineral soil organic soils included", k=2, con=con)
    if not res["rows"]:
        return not_in_data(f"No survey rows report organic (peat) soil in {yr}.", ["raw_farm_survey_fi"])
    farms = sorted({r[0] for r in res["rows"]})
    n_mis = mis["rows"][0][0]
    md = (f"In {yr}, {len(farms)} farms ({res['n_rows']} crop rows) reported organic (peat) soil in the survey. "
          f"The current calculator treats every farm as mineral soil, so their peat emissions are missing there. "
          f"Our data review also proposes a soil correction (survey says mineral, soil map and the farm's own history say peat) "
          f"for {n_mis} more survey rows that year, pending expert approval.\n\n"
          f"Farms: {', '.join(farms[:15])}{' …' if len(farms) > 15 else ''}")
    evidence = sql_evidence(res) + sql_evidence(calc) + [ev("table_row", "corrections:soil_type_reported", "corrections (soil_type_reported)")] \
        + doc_evidence(docs)
    return finish(q, md, [res, mis, calc, docs, {"n_farms": len(farms)}], evidence, table_of(res), pending=n_mis > 0)


ENERGY_SQL = """
WITH raw AS (
  SELECT r.record_key, r.site_id, r.year, r.month, r.carrier,
         coalesce(try_cast(c.new_value AS DOUBLE), r.value) AS mwh, c.record_key IS NOT NULL AS corrected
  FROM raw_energy_meter_readings r LEFT JOIN corrections c ON c.record_key = r.record_key AND c.field = 'value'
  WHERE r.year = ?),
added AS (
  SELECT c.record_key, regexp_extract(c.record_key, '^energy:([^:]+):', 1) AS site_id,
         try_cast(regexp_extract(c.record_key, ':(\\d{4})-', 1) AS INTEGER) AS year,
         try_cast(regexp_extract(c.record_key, '-(\\d{2}):', 1) AS INTEGER) AS month,
         regexp_extract(c.record_key, ':([a-z_]+)$', 1) AS carrier, try_cast(c.new_value AS DOUBLE) AS mwh, TRUE AS corrected
  FROM corrections c WHERE c.record_key LIKE 'energy:%' AND c.field = 'value'
    AND c.record_key NOT IN (SELECT record_key FROM raw_energy_meter_readings))
SELECT site_id, month, carrier, round(mwh, 3) AS mwh, corrected, record_key FROM raw
UNION ALL SELECT site_id, month, carrier, round(mwh, 3), corrected, record_key FROM added WHERE year = ?
ORDER BY site_id, carrier, month"""


def route_energy_by_site_month(con, q: str) -> dict | None:
    if not (re.search(r"energy|electricity|mwh", q) and re.search(r"site", q) and re.search(r"month", q)):
        return None
    yr = (years_in(q) or [2024])[-1]
    res = S.run_sql(ENERGY_SQL, [yr, yr], con=con)
    if not res["rows"]:
        return not_in_data(f"No meter readings for {yr}.", ["raw_energy_meter_readings"])
    tot = S.run_sql(f"SELECT site_id, round(sum(mwh), 1) AS mwh, sum(corrected::INT) AS corrected_months "
                    f"FROM ({ENERGY_SQL}) GROUP BY 1 ORDER BY 2 DESC", [yr, yr], con=con)
    parts = ", ".join(f"{r[0]} {fmt(r[1])} MWh" for r in tot["rows"])
    n_corr = sum(r[2] for r in tot["rows"])
    md = (f"Energy use per site in {yr} (all carriers, MWh): {parts}. The table has one row per site × carrier × month; "
          f"{n_corr} readings use a proposed correction (unit error, spike or missing month), pending expert approval.")
    report = maybe_report(con, q, "energy_by_site_month", {"year": yr})
    return finish(q, md, [res, tot], sql_evidence(res), table_of(res), report=report, pending=n_corr > 0)


def route_rule(con, q: str) -> dict | None:
    if not re.search(r"\brule\b|how (do|does|should) we (count|treat|handle)|what does .* (say|require)", q):
        return None
    topic = re.sub(r"\b(what|is|the|rule|for|about|our|on|do|does|we|how|count|treat|handle)\b", " ", q)
    docs = r_docs.search_docs(topic + " rule", k=3, con=con, prefer_rules=True)
    if not docs["passages"]:
        return not_in_data("No passage in the pack docs or our method note covers it.")
    md = "From the sources:\n\n" + "\n\n".join(f"> {p['text']}\n> — *{p['file']} § {p['section']}*" for p in docs["passages"])
    return finish(q, md, [docs], doc_evidence(docs))


def route_farm_yield_history(con, q: str) -> dict | None:
    m = re.search(r"\b(f\d{4})\b", q)
    if not (m and re.search(r"yield|harvest", q)):
        return None
    farm = m.group(1).upper()
    res = S.run_sql("""SELECT year, crop, area_ha, yield_t_ha, corrected_fields, record_key FROM clean_farm_survey
                       WHERE farm_id = ? ORDER BY year, crop""", [farm], con=con)
    if not res["rows"]:
        return not_in_data(f"No survey rows for farm {farm}.", ["clean_farm_survey", "raw_farm_survey_fi"])
    lines = [f"{r[0]} {r[1]}: {fmt(r[3], 2)} t/ha on {fmt(r[2], 2)} ha" + (" (corrected)" if r[4] else "") for r in res["rows"]]
    md = f"Farm {farm}, survey yields after the data review:\n\n" + "\n".join(f"- {l}" for l in lines)
    report = maybe_report(con, q, "farm_yield_history", {"farm_id": farm})
    return finish(q, md, [res], sql_evidence(res), table_of(res), report=report, pending=any(r[4] for r in res["rows"]))


def route_v1_totals(con, q: str) -> dict | None:
    """v1's resolver for plain scope totals ('What were total Scope 1 emissions in 2024?'), reused as is."""
    from src import e_agent, e_resolve
    f = e_agent.parse_plain_numeric(e_resolve.strip_method_clause(q))
    r = e_resolve.resolve(con, q) if f is None else None
    if f is None and r is None:
        return None
    a = e_agent.stub_answer(con, q, "numeric")
    if a.blocked or a.markdown.startswith(e_agent.NOT_IN_DATA):
        return None
    prose = a.markdown.split(e_check.EVIDENCE_MARK)[0].strip()
    evidence = [ev("result", e.split("`")[1] if "`" in e else e, e) for e in a.evidence]
    return {"status": "answered", "answer_md": prose, "table": None, "evidence": evidence, "report": None,
            "pending_approval": a.pending}


def route_options(con, q: str) -> dict | None:
    """Adaptation options from kb/adaptation_options.csv (#87), e.g. 'what can we do about heat at flowering?'."""
    from src import r_options
    out = r_options.answer(q)
    if out is None:
        return None
    return finish(q, out["answer_md"], [out["table"]], out["evidence"], out["table"], pending=out["pending_approval"])


ROUTES: list[Route] = [route_se_pea_deliveries, route_peat_as_mineral, route_energy_by_site_month,
                       route_farm_yield_history, route_options, route_rule, route_v1_totals]


def hints(q: str) -> list[str]:
    try:
        from src.r_catalog import catalog_search
        return [t["table"] for t in catalog_search(q, k=3)["tables"]]
    except Exception:  # noqa: BLE001 — the catalog is optional for the fallback
        return []


def ask(question: str, history: list[dict] | None = None, con: duckdb.DuckDBPyConnection | None = None) -> dict:
    """AskOut for one question, validated against api.schemas.AskOut (the v2 contract)."""
    from api.schemas import AskOut
    return AskOut.model_validate(_ask(question, history, con)).model_dump()


def _ask(question: str, history: list[dict] | None = None, con: duckdb.DuckDBPyConnection | None = None) -> dict:
    """Offline: deterministic routes. (LLM tool loop: task #93.)"""
    own = con is None
    if own:
        if not S.serve_db_path().exists():
            return not_in_data("No snapshot yet: run `make snapshot` (out/serve.duckdb).")
        con = S.connect()
    try:
        q = question.strip().lower()
        for route in ROUTES:
            try:
                out = route(con, q)
            except S.SqlRefused as e:
                out = not_in_data(f"The query was refused: {e}.")
            if out is not None:
                return out
        prev = previous_question(history)
        if wants_report(q) and prev:   # "make that a report": rerun the previous question with a report
            return _ask(f"{prev} as a report", None, con)
        return not_in_data("No offline route answers this yet; the LLM mode (task #93) will try the tools.", hints(question))
    finally:
        if own:
            con.close()


def main() -> None:
    q = " ".join(sys.argv[1:]) or "How did pea deliveries from Swedish farms in 2026 compare with 2021?"
    out = ask(q)
    print(out["status"], "\n", out["answer_md"], "\n")
    if out["table"]:
        print("table:", out["table"]["columns"], f"{len(out['table']['rows'])} rows")
    print("evidence:", json.dumps([e["label"] for e in out["evidence"]][:8], ensure_ascii=False))
    if out["report"]:
        print("report:", out["report"].get("filename"))


if __name__ == "__main__":
    main()
