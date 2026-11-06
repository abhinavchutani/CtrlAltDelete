"""Track A detectors: one deterministic function per issue type, returning candidate issues.

Every detector returns a DataFrame with CANDIDATE_COLUMNS. `persist()` writes candidates to the
shared `issues` table through src.lineage (issue_id = f"{rule_id}:{record_key}").
"""
from __future__ import annotations

import duckdb
import pandas as pd

from src import lineage as L

CANDIDATE_COLUMNS = ["table_name", "record_key", "year", "issue_type", "confidence", "rule_id",
                     "explanation", "evidence", "proposed_fix"]

ISSUE_TYPES = {
    "unit_error", "duplicate_record", "currency_error", "material_mismatch", "decimal_shift",
    "missing_record", "meter_spike", "wrong_gas_code", "certificate_mismatch", "soil_misreport",
    "outlier_implausible", "area_mismatch", "coordinate_swap", "pcf_unit_error", "pcf_stale_period",
    "total_mismatch", "missing_leg", "mode_mislabel",
}


def empty() -> pd.DataFrame:
    return pd.DataFrame(columns=CANDIDATE_COLUMNS)


def persist(con: duckdb.DuckDBPyConnection, cands: pd.DataFrame, created_by: str) -> list[str]:
    """Write candidates to `issues`; returns their issue_ids."""
    L.init_schema(con)
    ids = []
    for r in cands.itertuples(index=False):
        if r.issue_type not in ISSUE_TYPES and r.issue_type != "observation":
            raise ValueError(f"unknown issue type {r.issue_type!r}")
        ids.append(L.propose_issue(
            con, table_name=r.table_name, record_key=r.record_key,
            year=None if pd.isna(r.year) else int(r.year), issue_type=r.issue_type,
            confidence=float(r.confidence), rule_id=r.rule_id, explanation=r.explanation,
            evidence=r.evidence, proposed_fix=r.proposed_fix, created_by=created_by))
    return ids
