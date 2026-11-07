"""Expert review & publish logic (task #21). The page in app/views/review.py is a thin UI over this.

Rules (SYSTEM_DESIGN "Expert review and approval"):
* Every decision needs a reviewer name typed by a human. src.lineage rejects agents, DEV-ASSUMED and
  empty names; the app never pre-fills one.
* Accept / edit → a `corrections` row (approved_by, approved_at, reason). Reject → issue status `rejected`.
* Bulk accept only for high-confidence rule hits; soil misreports always need individual review.
  Each bulk item is still logged as its own correction.
* Recalculate reruns the pipeline. Results it rewrites go back to `draft`; results whose value did not
  change keep the status a human gave them.
* Publish is human-only and requires lineage (src.lineage.publish).
"""
from __future__ import annotations

import duckdb
import pandas as pd

from src import lineage as L

INDIVIDUAL_ONLY = {"soil_misreport"}   # map ~88 % accurate: never bulk (SYSTEM_DESIGN, REASONING_LOG R07)
BULK_MIN_CONFIDENCE = 0.9


def reviewer_error(name: str) -> str | None:
    """None if `name` may approve; otherwise the reason it may not."""
    try:
        L._check_human(name, allow_dev=False)
        return None
    except ValueError as e:
        return str(e)


def _has(con: duckdb.DuckDBPyConnection, table: str) -> bool:
    return bool(con.execute("SELECT count(*) FROM information_schema.tables WHERE table_name = ?", [table]).fetchone()[0])


def queue(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Proposed issues, most confident first, with the LLM triage verdict where one exists (#10)."""
    triage = ("LEFT JOIN (SELECT issue_id, decision AS triage, explanation AS triage_note FROM a_triage) t USING (issue_id)"
              if _has(con, "a_triage") else "")
    cols = ", t.triage, t.triage_note" if triage else ", NULL AS triage, NULL AS triage_note"
    return con.execute(f"""SELECT i.issue_id, i.issue_type, i.table_name, i.record_key, i.year, i.confidence,
                                  i.rule_id, i.explanation, i.evidence, i.proposed_fix{cols}
                           FROM issues i {triage}
                           WHERE i.status = 'proposed' AND i.issue_type <> 'observation'
                           ORDER BY i.confidence DESC, i.issue_id""").df()


def accept(con: duckdb.DuckDBPyConnection, issue_id: str, by: str, comment: str = "",
           new_value: str | None = None) -> str:
    """Accept the proposed fix (or an edited new value). Returns the correction_id."""
    return L.apply_correction(con, issue_id, approved_by=by, reason=comment or "accepted in review app",
                              new_value=new_value if new_value not in (None, "") else None)


def reject(con: duckdb.DuckDBPyConnection, issue_id: str, by: str, comment: str = "") -> None:
    L._check_human(by, allow_dev=False)
    note = f" | rejected by {by}" + (f": {comment}" if comment else "")
    con.execute("UPDATE issues SET status = 'rejected', explanation = explanation || ? WHERE issue_id = ?",
                [note, issue_id])


def bulk_candidates(q: pd.DataFrame) -> pd.DataFrame:
    return q[(q["confidence"] >= BULK_MIN_CONFIDENCE) & ~q["issue_type"].isin(INDIVIDUAL_ONLY)]


def bulk_accept(con: duckdb.DuckDBPyConnection, issue_ids: list[str], by: str, comment: str = "") -> list[str]:
    """Accept several high-confidence issues; each becomes its own correction row."""
    q = queue(con).set_index("issue_id")
    bad = [i for i in issue_ids if i not in q.index or q.at[i, "issue_type"] in INDIVIDUAL_ONLY
           or q.at[i, "confidence"] < BULK_MIN_CONFIDENCE]
    if bad:
        raise ValueError(f"not eligible for bulk accept (individual review needed): {bad[:5]}")
    return [accept(con, i, by, comment or "bulk accept (high-confidence rule)") for i in issue_ids]


def recalculate(con: duckdb.DuckDBPyConnection, mock: bool) -> pd.DataFrame:
    """Rerun the pipeline; returns the results whose value changed (they are now `draft`)."""
    before = con.execute("SELECT result_id, value, status FROM results").df().set_index("result_id")
    if mock:
        from app import mock as M
        M.recalculate(con)
    else:
        from src import a_inventory
        a_inventory.run(con)
    after = con.execute("SELECT result_id, value FROM results").df().set_index("result_id")
    joined = after.join(before.rename(columns={"value": "value_before"}), how="left")
    same = joined[(joined["value"] - joined["value_before"]).abs() < 1e-9]
    for rid, status in same["status"].items():  # unchanged numbers keep the human's earlier decision
        if status in ("approved", "published"):
            con.execute("UPDATE results SET status = ? WHERE result_id = ?", [status, rid])
    changed = joined[~joined.index.isin(same.index)]
    return changed.reset_index()[["result_id", "value_before", "value"]]


def publish(con: duckdb.DuckDBPyConnection, result_ids: list[str], by: str) -> None:
    L.publish(con, result_ids, by=by)


def audit_log(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return con.execute("SELECT c.approved_at, c.approved_by, c.record_key, c.field, c.old_value, c.new_value, "
                       "c.reason, i.rule_id, i.issue_type FROM corrections c LEFT JOIN issues i USING (issue_id) "
                       "ORDER BY c.approved_at DESC, c.correction_id").df()
