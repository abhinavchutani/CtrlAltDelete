"""Retrieval layer (v2): the missing-data chaser (task #112; docs/DATA_INGESTION_AND_RETRIEVAL.md §9.2–9.3).

    from src.r_gaps import gaps
    gaps(con, year=2025)      # [{gap_id, record_key, site_id, domain, year, month, owner, impact, draft_message, evidence}]

Run:  python -m src.r_gaps 2025

A gap is a record the inventory needs but nobody delivered: v1's detectors already find them (issue type
`missing_record`, e.g. a meter month missing inside a site × carrier series, REASONING_LOG R06) and propose an
estimate from the neighbouring months. This module only reads those (read-only, src.r_sql), names the owner by
domain and site, and drafts the message to send. It sends nothing: a person copies the draft into Teams or email.
Boundary cases are not gaps (e.g. Bjuv before Foodhills joined in Dec 2025): the detector never flags them.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date

import duckdb

from src import r_sql as S

# Domain of a record key → the owner role that holds the data (configured once, doc §4 'owner' facet).
OWNER_BY_DOMAIN = {"energy": "Energy manager", "fuel": "Energy manager", "refrigerant": "Site maintenance lead",
                   "waste": "Site environment lead", "erp": "Sourcing (purchasing data)", "ship": "Supply chain"}
KEY_RE = re.compile(r"^energy:(?P<site>[^:]+):(?P<year>\d{4})-(?P<month>\d{2}):(?P<carrier>[a-z_]+)$")
SYNTHETIC = "Synthetic data from the hackathon twin; names are roles, not real people."


def _month_name(m: int) -> str:
    return date(2000, m, 1).strftime("%B")


def _fix_value(proposed_fix: str | None) -> float | None:
    try:
        v = json.loads(proposed_fix or "{}").get("new_value")
        return None if v is None else float(v)
    except (ValueError, TypeError, AttributeError):
        return None


def gaps(con: duckdb.DuckDBPyConnection, year: int | None = None) -> dict:
    """Open missing-record issues as gaps with an owner and a drafted message; plus the query result (evidence)."""
    yr = "AND i.year = ?" if year else ""
    res = S.run_sql(f"""SELECT i.issue_id, i.record_key, i.year, i.explanation, i.proposed_fix, s.name AS site_name
                        FROM issues i
                        LEFT JOIN raw_sites s ON s.site_id = regexp_extract(i.record_key, '^[a-z]+:([^:]+):', 1)
                        WHERE i.issue_type = 'missing_record' AND i.status = 'proposed' {yr}
                        ORDER BY i.year, i.record_key""", [year] if year else [], con=con)
    out = []
    for issue_id, key, y, why, fix, site_name in res["rows"]:
        domain = key.split(":", 1)[0]
        m = KEY_RE.match(key)
        site = m["site"] if m else None
        month = int(m["month"]) if m else None
        carrier = m["carrier"].replace("_", " ") if m else "record"
        est = _fix_value(fix)
        where = site_name or site or "the site"
        owner = f"{OWNER_BY_DOMAIN.get(domain, 'Data owner')}, {where}"
        when = f"{_month_name(month)} {y}" if month else str(y)
        impact = (f"estimated at {est:,.3f} MWh from the neighbouring months and used in the inventory as a proposed "
                  f"correction until the real reading arrives" if est is not None else "not in the inventory yet")
        draft = (f"Hi, the {carrier} meter reading for {where} for {when} is missing from our energy data. "
                 f"Right now we use an estimate of {est:,.3f} MWh from the neighbouring months. Could you send the "
                 f"reading, or reply here with it? (ref {key})" if est is not None else
                 f"Hi, the {carrier} data for {where} for {when} is missing. Could you send it? (ref {key})")
        out.append({"gap_id": f"gap:{key}", "record_key": key, "site_id": site, "domain": domain, "year": int(y),
                    "month": month, "owner": owner, "impact": impact, "draft_message": draft,
                    "estimate": est, "explanation": why,
                    "evidence": [{"kind": "table_row", "ref": issue_id, "label": f"issues · {issue_id}: {why}"},
                                 {"kind": "table_row", "ref": key, "label": key}]})
    return {"gaps": out, "result": res}


def main() -> None:
    year = int(sys.argv[1]) if len(sys.argv) > 1 else None
    for g in gaps(S.connect(), year)["gaps"]:
        print(g["record_key"], "|", g["owner"], "|", g["draft_message"])


if __name__ == "__main__":
    main()
