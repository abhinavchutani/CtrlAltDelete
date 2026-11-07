"""Read-only data access for the app. Reads precomputed tables only; nothing slow runs live.

Uses NAVIGATOR_DB when it has results; otherwise (or with APP_MOCK=1) the seeded mock DB.
"""
from __future__ import annotations

import duckdb
import pandas as pd
import streamlit as st

from app import mock
from src.db import connect, db_path, env


def _has_results(path) -> bool:
    if not path.exists():
        return False
    try:
        con = duckdb.connect(str(path), read_only=True)
        n = con.execute("SELECT count(*) FROM results").fetchone()[0]
        con.close()
        return n > 0
    except duckdb.Error:
        return False


@st.cache_resource
def source() -> tuple[str, str]:
    """(path, label) of the database the app reads."""
    if env("APP_MOCK") != "1" and _has_results(db_path()):
        return str(db_path()), "live"
    mock.seed()  # rebuilt once per app process (cached), so it always matches the current mock shape
    return str(mock.MOCK_DB), "mock"


def is_mock() -> bool:
    return source()[1] == "mock"


@st.cache_resource
def _con() -> duckdb.DuckDBPyConnection:
    """One read-write connection per app process (the review page writes decisions through it).
    While the app runs it holds the DuckDB file lock, so stop it before `make all`."""
    return connect(source()[0])


def rw() -> duckdb.DuckDBPyConnection:
    """A cursor for writes (review & publish)."""
    return _con().cursor()


def q(sql: str, params: list | None = None) -> pd.DataFrame:
    return _con().cursor().execute(sql, params or []).df()


def has_table(name: str) -> bool:
    return not q("SELECT 1 FROM information_schema.tables WHERE table_name = ?", [name]).empty


def results(where: str = "TRUE", params: list | None = None) -> pd.DataFrame:
    return q(f"SELECT * FROM results WHERE {where} ORDER BY result_id", params)


def lineage(result_id: str) -> pd.DataFrame:
    return q("SELECT source_kind, source_ref, contribution, note FROM lineage WHERE result_id = ? "
             "ORDER BY source_kind, source_ref", [result_id])


def corrections_for(record_keys: list[str]) -> pd.DataFrame:
    if not record_keys:
        return pd.DataFrame()
    marks = ",".join("?" * len(record_keys))
    return q(f"SELECT * FROM corrections WHERE record_key IN ({marks})", record_keys)


def raw_parcels() -> pd.DataFrame:
    """Parcels from the live DB if loaded (make load), else empty."""
    try:
        con = connect(db_path(), read_only=True)
        df = con.execute("SELECT parcel_id, farm_id, lat, lon, area_ha, soil_class_soilmap FROM raw_parcels").df()
        con.close()
        return df
    except (duckdb.Error, OSError):
        return pd.DataFrame()


def flagged(issues: pd.DataFrame) -> pd.DataFrame:
    """Real flags only: allow-listed rows (status `legitimate`, whatever their issue_type) and
    `observation` rows are not issues."""
    return issues[(issues["status"] != "legitimate") & (issues["issue_type"] != "observation")]


def visible(df: pd.DataFrame, show_drafts: bool) -> pd.DataFrame:
    """Only published rows feed the dashboard, unless the reviewer asks to see drafts."""
    return df if show_drafts else df[df["status"] == "published"]
