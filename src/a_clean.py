"""Build clean_farm_survey and clean_farm_registry (task #7, hand-off to the Climate lane).

Run:  python -m src.a_clean        (needs `python -m src.load`; prints dev scores)

1. Farm detectors (src/a_detect/farm.py) propose issues into `issues`.
2. In dev mode (NAVIGATOR_DEV_ASSUME=1) every proposed fix is applied as a DEV-ASSUMED correction;
   otherwise only human-approved corrections are applied.
3. clean_* = raw_* with those corrections applied, plus:
   `corrected_fields` (comma list), and for the survey `crop_organic_share` / `farm_organic_share`
   from the soil map and `parcel_ha` (declared parcel area), so downstream code can use soil evidence.
"""
from __future__ import annotations

import json

import duckdb
import pandas as pd

from src import lineage as L
from src.a_detect import farm, ops, ops2, persist
from src.a_score import dev_labels, score_a1
from src.db import connect, env

COVERED = {
    "farm tables": ["farm_survey", "farm_registry"],
    "ops tables": ["erp_purchase_lines", "energy_meter_readings", "fuel_deliveries", "goo_cancellations", "refrigerant_service_log"],
    "ops2 tables": ["travel_bookings", "shipments", "waste_transfer_notes", "supplier_pcfs", "draft_report_summary", "commuting_survey"],
    "ALL dev labels": None,
}
CREATED_BY = "agent:" + (env("AGENT_NAME") or "unknown")


def propose_and_assume(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    cands = pd.concat([farm.detect_all(con), ops.detect_all(con), ops2.detect_all(con)], ignore_index=True)
    if "status" not in cands:
        cands["status"] = "proposed"
    cands["status"] = cands["status"].fillna("proposed")
    ids = persist(con, cands, CREATED_BY)
    retire_stale(con, ids)
    if L.dev_mode():
        for iid, st, fix in zip(ids, cands.status, cands.proposed_fix):
            if st == "proposed" and isinstance(fix, dict):
                L.apply_correction(con, iid, approved_by=L.DEV_ASSUMED, reason="dev-mode assumption for scoring")
    return cands


def retire_stale(con: duckdb.DuckDBPyConnection, current_ids: list[str]) -> int:
    """Drop this agent's earlier detector issues that no rule raises any more (a rule was tightened), with their
    DEV-ASSUMED corrections, so re-running `make a` on an existing database gives the same result as a fresh one.
    Anything a human touched (approved/rejected, or a human-approved correction) is kept."""
    con.register("_cur", pd.DataFrame({"issue_id": list(current_ids) or [""]}))
    stale = con.execute("""
        SELECT i.issue_id FROM issues i WHERE i.created_by = ? AND i.status IN ('proposed', 'legitimate', 'observation')
          AND i.issue_id NOT IN (SELECT issue_id FROM _cur)
          AND NOT EXISTS (SELECT 1 FROM corrections c WHERE c.issue_id = i.issue_id AND c.approved_by <> ?)""",
                        [CREATED_BY, L.DEV_ASSUMED]).df().issue_id.tolist()
    con.unregister("_cur")
    if stale:
        con.register("_st", pd.DataFrame({"issue_id": stale}))
        con.execute("DELETE FROM corrections WHERE issue_id IN (SELECT issue_id FROM _st)")
        con.execute("DELETE FROM issues WHERE issue_id IN (SELECT issue_id FROM _st)")
        con.unregister("_st")
    return len(stale)


def active_corrections(con: duckdb.DuckDBPyConnection, table_name: str) -> pd.DataFrame:
    """Corrections that count now: human-approved always; DEV-ASSUMED only in dev mode."""
    dev = "OR c.approved_by = 'DEV-ASSUMED'" if L.dev_mode() else ""
    return con.execute(f"""
        SELECT c.record_key, c.field, c.new_value FROM corrections c JOIN issues i USING (issue_id)
        WHERE i.table_name = ? AND i.status <> 'rejected'
          AND (c.approved_by <> 'DEV-ASSUMED' {dev})""", [table_name]).df()


def _apply(df: pd.DataFrame, corr: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["corrected_fields"] = ""
    idx = {k: i for i, k in zip(df.index, df.record_key)}
    for c in corr.itertuples(index=False):
        i = idx.get(c.record_key)
        if i is None:
            continue
        fields = c.field.split(",")
        values = str(c.new_value).split(",") if len(fields) > 1 else [c.new_value]
        for f, v in zip(fields, values):
            df.at[i, f] = float(v) if df[f].dtype.kind in "if" else v
        df.at[i, "corrected_fields"] = ",".join(filter(None, [df.at[i, "corrected_fields"], c.field]))
    return df


def build_clean(con: duckdb.DuckDBPyConnection) -> dict[str, int]:
    sv = farm.survey_with_parcels(con)
    keep = list(con.execute("SELECT * FROM raw_farm_survey_fi LIMIT 0").df().columns) + \
        ["parcel_ha", "crop_organic_share", "farm_organic_share"]
    clean_sv = _apply(sv[keep], active_corrections(con, "farm_survey"))
    reg = con.execute("SELECT * FROM raw_farm_registry").df()
    clean_reg = _apply(reg, active_corrections(con, "farm_registry"))
    for name, df in [("clean_farm_survey", clean_sv), ("clean_farm_registry", clean_reg)]:
        con.register("_df", df)
        con.execute(f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM _df")
        con.unregister("_df")
    return {"clean_farm_survey": len(clean_sv), "clean_farm_registry": len(clean_reg),
            "survey_rows_corrected": int((clean_sv.corrected_fields != "").sum())}


def main() -> None:
    con = connect()
    L.init_schema(con)
    cands = propose_and_assume(con)
    print(cands.groupby(["table_name", "status", "issue_type"]).size().rename("candidates (all years)").to_string())
    print(json.dumps(build_clean(con), indent=1))
    flagged, labels = cands[cands.status == "proposed"], dev_labels(con)
    for name, tables in COVERED.items():
        print(f"dev A1 score, {name} (2023–24):", json.dumps(score_a1(flagged, labels, restrict_tables=tables)))


if __name__ == "__main__":
    main()
