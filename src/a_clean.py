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
from src.a_detect import farm, persist
from src.a_score import dev_labels, score_a1
from src.db import connect, env

CREATED_BY = "agent:" + (env("AGENT_NAME") or "unknown")


def propose_and_assume(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    cands = farm.detect_all(con)
    ids = persist(con, cands, CREATED_BY)
    if L.dev_mode():
        for iid in ids:
            L.apply_correction(con, iid, approved_by=L.DEV_ASSUMED, reason="dev-mode assumption for scoring")
    return cands


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
    print(cands.groupby(["table_name", "issue_type"]).size().rename("candidates (all years)").to_string())
    print(json.dumps(build_clean(con), indent=1))
    s = score_a1(cands, dev_labels(con), restrict_tables=["farm_survey", "farm_registry"])
    print("dev A1 score on farm tables (2023–24):", json.dumps(s))


if __name__ == "__main__":
    main()
