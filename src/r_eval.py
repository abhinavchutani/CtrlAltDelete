"""Retrieval layer (v2): the 15-question ask eval (task #93, V2-11).

Run:  python -m src.r_eval            → out/v2/ask_eval.json, one line per question

Each question has an expected answer computed here by its own deterministic SQL (independent of the route or the
LLM that answers it) and a check:
* "number": a number in the answer matches the expected value (within its rounding);
* "contains": the answer text contains every expected word;
* "evidence": an evidence ref contains the expected string;
* "not_in_data": the honest answer is "Not in the data".
Questions marked `needs_llm` have no offline route: without an LLM key they are expected to come back
"not in the data" (reported separately, not a failure of the offline routes).
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import duckdb

from src import e_check
from src import r_sql as S
from src.db import REPO_ROOT

OUT = REPO_ROOT / "out" / "v2" / "ask_eval.json"


@dataclass
class Case:
    qid: str
    question: str
    check: str                                   # number | contains | evidence | not_in_data
    expected: Callable[[duckdb.DuckDBPyConnection], object] | object = None
    needs_llm: bool = False
    history: list[dict] = field(default_factory=list)


def _one(sql: str, params: list | None = None) -> Callable:
    return lambda con: float(con.execute(sql, params or []).fetchone()[0])


def _energy_site_total(site: str, year: int, carrier: str | None = None) -> Callable:
    def f(con):
        from src.r_agent import ENERGY_SQL
        extra = f"AND carrier = '{carrier}'" if carrier else ""
        return float(con.execute(f"SELECT round(sum(mwh), 1) FROM ({ENERGY_SQL}) WHERE site_id = ? {extra}",
                                 [year, year, site]).fetchone()[0])
    return f


CASES = [
    Case("Q01", "How did pea deliveries from Swedish farms in 2026 compare with 2021?", "number",
         _one("SELECT round(sum(levererad_mängd_ton), 1) FROM raw_foodhills_odlingsdata_se "
              "WHERE gröda LIKE 'Ärt%' AND skördeår = 2026")),
    Case("Q02", "Which farms reported peat but were calculated as mineral soil?", "number",
         _one("SELECT count(DISTINCT farm_id) FROM raw_farm_survey_fi WHERE year = 2025 "
              "AND soil_type_reported = 'Organic soil'")),
    Case("Q03", "Energy use per site per month in 2024 as a report", "number", _energy_site_total("S-KAN", 2024)),
    Case("Q04", "What is the guarantee of origin rule?", "evidence", "R05"),
    Case("Q05", "Show farm F0123's yield history", "number",
         _one("SELECT round(yield_t_ha, 2) FROM clean_farm_survey WHERE farm_id = 'F0123' AND year = 2026")),
    Case("Q06", "What were total Scope 1 emissions in 2024?", "number",
         _one("SELECT round(sum(value), 1) FROM results WHERE metric = 'tco2e' AND scope = 'scope1' AND year = 2024")),
    Case("Q07", "Where does the 2024 Scope 2 market-based number come from?", "number",
         _one("SELECT round(sum(value), 1) FROM results WHERE metric = 'tco2e' AND scope = 'scope2_market' "
              "AND year = 2024")),
    Case("Q08", "Show me everything about SUP073", "number",
         _one("SELECT (SELECT count(*) FROM raw_erp_purchase_lines WHERE supplier_id = 'SUP073') + "
              "(SELECT count(*) FROM raw_supplier_pcfs WHERE supplier_id = 'SUP073') + "
              "(SELECT count(*) FROM raw_suppliers WHERE supplier_id = 'SUP073')")),
    Case("Q09", "What can we do about heat at flowering for peas?", "contains", ["A04", "A06"]),
    Case("Q10", "What data is missing for 2025?", "number",
         _one("SELECT count(*) FROM issues WHERE issue_type = 'missing_record' AND status = 'proposed' AND year = 2025")),
    Case("Q11", "How many refrigerant service events were logged at the Säkylä plant in 2024?", "number",
         _one("SELECT count(*) FROM raw_refrigerant_service_log WHERE site_id = 'S-SAK' AND year = 2024"),
         needs_llm=True),
    Case("Q12", "Which site used the most electricity in 2025, after the data corrections?", "number",
         _energy_site_total("S-SAK", 2025, "electricity"), needs_llm=True),
    Case("Q13", "How many contract farms are in the Finnish farm registry?", "number",
         _one("SELECT count(*) FROM raw_farm_registry WHERE country = 'FI'"), needs_llm=True),
    Case("Q14", "What was Apetit's share price in 2024?", "not_in_data"),
    Case("Q15", "What will the Säkylä headcount be in 2035?", "not_in_data"),
]


def passes(case: Case, out: dict, expected) -> tuple[bool, str]:
    md = out.get("answer_md", "")
    if case.check == "not_in_data":
        return out["status"] == "not_in_data", out["status"]
    if out["status"] != "answered":
        return False, "not answered"
    if case.check == "number":
        nums = [v for _, v, _ in e_check.numbers_in(md)] + [float(v) for r in (out.get("table") or {}).get("rows", [])
                                                           for v in r if isinstance(v, (int, float))]
        ok = any(abs(n - expected) <= max(0.051, 0.0005 * abs(expected)) for n in nums)
        return ok, f"expected {expected:g}"
    if case.check == "contains":
        text = md + json.dumps(out.get("table") or {})
        return all(w in text for w in expected), f"expected {expected}"
    if case.check == "evidence":
        return any(expected in e["ref"] or expected in e["label"] for e in out["evidence"]), f"expected {expected}"
    return False, "unknown check"


def run(con: duckdb.DuckDBPyConnection | None = None, out_path: Path = OUT) -> dict:
    from src import e_llm
    from src.r_agent import ask
    con = con or S.connect()
    llm = e_llm.available()
    rows = []
    for c in CASES:
        expected = c.expected(con) if callable(c.expected) else c.expected
        out = ask(c.question, c.history, con=con)
        ok, why = passes(c, out, expected)
        rows.append({"qid": c.qid, "question": c.question, "check": c.check, "needs_llm": c.needs_llm,
                     "expected": expected, "status": out["status"], "pass": ok, "note": why,
                     "evidence_n": len(out["evidence"])})
    offline = [r for r in rows if not r["needs_llm"]]
    summary = {"llm": llm, "passed": sum(r["pass"] for r in rows), "total": len(rows),
               "offline_passed": sum(r["pass"] for r in offline), "offline_total": len(offline),
               "rows": rows}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, indent=1, ensure_ascii=False, default=str))
    return summary


def main() -> None:
    s = run()
    for r in s["rows"]:
        print(f"{'PASS' if r['pass'] else 'fail'}  {r['qid']}  {r['status']:<12} {r['note']:<28} {r['question']}")
    print(f"\nLLM {'on' if s['llm'] else 'off'}: {s['passed']}/{s['total']} pass; "
          f"offline routes {s['offline_passed']}/{s['offline_total']} → {OUT}")
    sys.exit(0)


if __name__ == "__main__":
    main()
