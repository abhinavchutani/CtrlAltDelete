"""LLM triage for grey-zone data-quality candidates (task #10; SYSTEM_DESIGN Track A step 4).

Run:  python -m src.a_triage          (after `make a`; writes table a_triage, prints a summary)

* Grey zone = proposed issues with GREY_LO ≤ confidence < GREY_HI (soil misreports, seasonal spikes,
  material mismatches, commute units, …). Clear-cut rule hits are not sent.
* The model sees the record, the rule evidence and a few neighbouring records and returns STRICT JSON:
  {"decision": "issue"|"legitimate"|"unsure", "issue_type": <one of the 18>, "confidence": 0-1,
   "explanation": "<one line>"}. It never returns or edits data values (REASONING_LOG R23):
   the proposed fix always comes from the deterministic rule.
* No LLM key → offline stub: the rule's own decision and explanation are kept, marked `offline-stub`.
* Calls are cached by input hash (src/e_llm.py), so reruns reproduce the same table.
* Triage never changes an issue's status; the reviewer sees it next to the rule evidence.
"""
from __future__ import annotations

import json

import duckdb
import pandas as pd

from src import e_llm
from src.a_detect import ISSUE_TYPES
from src.db import connect

GREY_LO, GREY_HI = 0.55, 0.85
DECISIONS = {"issue", "legitimate", "unsure"}
RAW = {"farm_survey": "raw_farm_survey_fi", "erp_purchase_lines": "raw_erp_purchase_lines",
       "energy_meter_readings": "raw_energy_meter_readings", "refrigerant_service_log": "raw_refrigerant_service_log",
       "commuting_survey": "raw_commuting_survey", "waste_transfer_notes": "raw_waste_transfer_notes",
       "shipments": "raw_shipments", "travel_bookings": "raw_travel_bookings", "supplier_pcfs": "raw_supplier_pcfs"}

SYSTEM = (
    "You are a data-quality reviewer for a food company's greenhouse-gas inventory (synthetic hackathon data). "
    "A deterministic rule flagged a record. Decide whether it is a real data error. Legitimate oddities that are "
    "NOT errors: credit notes (movement 122), vessel lots in tonnes (uom TO), seasonal harvest peaks, ammonia "
    "(R717) on ammonia systems. Answer with ONLY a JSON object: "
    '{"decision": "issue"|"legitimate"|"unsure", "issue_type": "<type>", "confidence": <0..1>, '
    '"explanation": "<one short sentence>"}. Never propose corrected values or any other numbers.'
)


def grey_zone(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return con.execute("""SELECT * FROM issues WHERE status = 'proposed' AND confidence >= ? AND confidence < ?
                          ORDER BY issue_id""", [GREY_LO, GREY_HI]).df()


def context(con: duckdb.DuckDBPyConnection, issue: pd.Series, n_neighbours: int = 3) -> dict:
    raw = RAW.get(issue.table_name)
    rec, neigh = {}, []
    if raw:
        df = con.execute(f"SELECT * FROM {raw} WHERE record_key = ?", [issue.record_key]).df()
        if len(df):
            rec = json.loads(df.iloc[0].to_json(date_format="iso"))
            key_col = next((c for c in ("farm_id", "supplier_id", "site_id", "traveller_id") if c in df), None)
            if key_col:
                nb = con.execute(f"SELECT * FROM {raw} WHERE {key_col} = ? AND record_key <> ? LIMIT ?",
                                 [df.iloc[0][key_col], issue.record_key, n_neighbours]).df()
                neigh = json.loads(nb.to_json(orient="records", date_format="iso"))
    return {"table": issue.table_name, "record_key": issue.record_key, "rule": issue.rule_id,
            "rule_issue_type": issue.issue_type, "rule_explanation": issue.explanation,
            "rule_evidence": json.loads(issue.evidence or "{}"), "record": rec, "neighbours": neigh}


def parse(content: str, fallback_type: str) -> dict:
    """Strict JSON parse with validation; anything malformed becomes 'unsure'."""
    try:
        start, end = content.index("{"), content.rindex("}") + 1
        d = json.loads(content[start:end])
        dec = d.get("decision")
        typ = d.get("issue_type") if d.get("issue_type") in ISSUE_TYPES else fallback_type
        conf = float(d.get("confidence"))
        if dec not in DECISIONS or not 0 <= conf <= 1:
            raise ValueError
        return {"decision": dec, "issue_type": typ, "confidence": round(conf, 3),
                "explanation": str(d.get("explanation", ""))[:300]}
    except (ValueError, TypeError, json.JSONDecodeError):
        return {"decision": "unsure", "issue_type": fallback_type, "confidence": 0.0,
                "explanation": "model reply was not valid JSON; kept for human review"}


def triage_one(con: duckdb.DuckDBPyConnection, issue: pd.Series) -> dict:
    if not e_llm.available():
        return {"decision": "issue", "issue_type": issue.issue_type, "confidence": float(issue.confidence),
                "explanation": f"{issue.explanation} (offline stub: rule decision kept)", "model": "offline-stub"}
    msgs = [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": json.dumps(context(con, issue), ensure_ascii=False, default=str)}]
    out = parse(e_llm.chat(msgs).get("content", ""), issue.issue_type)
    return {**out, "model": e_llm.model_name()}


def run(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    grey = grey_zone(con)
    rows = [{"issue_id": r.issue_id, "record_key": r.record_key, "rule_issue_type": r.issue_type,
             "rule_confidence": float(r.confidence), **triage_one(con, r)} for r in grey.itertuples(index=False)]
    df = pd.DataFrame(rows, columns=["issue_id", "record_key", "rule_issue_type", "rule_confidence",
                                     "decision", "issue_type", "confidence", "explanation", "model"])
    con.register("_t", df)
    con.execute("CREATE OR REPLACE TABLE a_triage AS SELECT * FROM _t")
    con.unregister("_t")
    return df


def main() -> None:
    con = connect()
    df = run(con)
    print(f"a_triage: {len(df)} grey-zone issues, model={e_llm.model_name()}")
    if len(df):
        print(df.groupby(["rule_issue_type", "decision"]).size().to_string())


if __name__ == "__main__":
    main()
