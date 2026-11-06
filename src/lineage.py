"""Shared writer for the four contract tables: issues, corrections, results, lineage.

Columns are exactly as in docs/CONTRACTS.md (v1). Every module writes through this API.

    from src.db import connect, git_sha
    from src import lineage as L

    con = connect(); L.init_schema(con)                      # idempotent

    # Track A: a detector proposes an issue (issue_id = f"{rule_id}:{record_key}")
    iid = L.propose_issue(con, table_name="erp_purchase_lines", record_key="erp:0042:3", year=2024,
                          issue_type="unit_error", confidence=0.9, rule_id="price_ratio",
                          explanation="price/kg 1000x the material median",
                          evidence={"price_per_kg": 1200.0, "median": 1.2},
                          proposed_fix={"field": "quantity", "old_value": 5, "new_value": 5000},
                          created_by="agent:abhinav-claude")

    # A correction: a human name, or "DEV-ASSUMED" only when NAVIGATOR_DEV_ASSUME=1. Never an agent.
    cid = L.apply_correction(con, iid, approved_by="DEV-ASSUMED", reason="dev scoring")

    # Any track: a number plus its trail. Lineage is required; status always starts as draft.
    L.write_result(con, "A2:2025:scope3:cat1", metric="tco2e", value=1234.5, unit="t CO2e",
                   scope="3", category="cat1", year=2025, scenario="actual",
                   method="reference_calculator v1 + corrections", produced_by=f"a_inventory@{git_sha()}",
                   lineage=[L.src("record", "erp:0042:3", 12.3), L.src("factor", "EF-123"),
                            L.src("correction", cid)])

    L.publish(con, ["A2:2025:scope3:cat1"], by="<human name>")   # humans only; checks lineage
    L.orphan_published(con)          # published result_ids with no lineage (must be empty)
    L.export_corrections(con)        # -> out/corrections.csv

Run `python -m src.lineage` to create the tables in NAVIGATOR_DB.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, NamedTuple

import duckdb

from src.db import REPO_ROOT, connect, env

ISSUE_STATUSES = {"proposed", "approved", "rejected", "legitimate"}
RESULT_STATUSES = {"draft", "approved", "published"}
SOURCE_KINDS = {"record", "factor", "correction", "model", "doc"}
DEV_ASSUMED = "DEV-ASSUMED"

SCHEMA = """
CREATE TABLE IF NOT EXISTS issues (
  issue_id VARCHAR PRIMARY KEY, table_name VARCHAR, record_key VARCHAR, year INTEGER,
  issue_type VARCHAR, confidence DOUBLE, rule_id VARCHAR, explanation VARCHAR, evidence VARCHAR,
  proposed_fix VARCHAR, status VARCHAR, created_by VARCHAR, created_at TIMESTAMP);
CREATE TABLE IF NOT EXISTS corrections (
  correction_id VARCHAR PRIMARY KEY, issue_id VARCHAR, record_key VARCHAR, field VARCHAR,
  old_value VARCHAR, new_value VARCHAR, reason VARCHAR, approved_by VARCHAR, approved_at TIMESTAMP);
CREATE TABLE IF NOT EXISTS results (
  result_id VARCHAR PRIMARY KEY, metric VARCHAR, scope VARCHAR, category VARCHAR, year INTEGER,
  scenario VARCHAR, value DOUBLE, unit VARCHAR, method VARCHAR, status VARCHAR,
  produced_by VARCHAR, created_at TIMESTAMP);
CREATE TABLE IF NOT EXISTS lineage (
  result_id VARCHAR, source_kind VARCHAR, source_ref VARCHAR, contribution DOUBLE, note VARCHAR);
"""


class Source(NamedTuple):
    """One lineage link. `contribution` is a share or absolute amount, if known."""
    kind: str
    ref: str
    contribution: float | None = None
    note: str = ""


def src(kind: str, ref: str, contribution: float | None = None, note: str = "") -> Source:
    return Source(kind, ref, contribution, note)


def init_schema(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(SCHEMA)


def dev_mode() -> bool:
    return env("NAVIGATOR_DEV_ASSUME", "0") == "1"


def _now() -> datetime:
    return datetime.now().replace(microsecond=0)


def _json(x: Any) -> str:
    return "" if x is None else x if isinstance(x, str) else json.dumps(x, sort_keys=True, default=str)


def _check_human(name: str, allow_dev: bool) -> None:
    """Agents never approve. DEV-ASSUMED is allowed only for corrections, only in dev mode."""
    n = (name or "").strip()
    if not n or n.lower().startswith(("agent:", "agent-")) or n.lower().endswith("-claude"):
        raise ValueError(f"approver must be a human, got {name!r}")
    if n == DEV_ASSUMED and not (allow_dev and dev_mode()):
        raise ValueError("DEV-ASSUMED is only allowed for corrections when NAVIGATOR_DEV_ASSUME=1")


# ── issues ────────────────────────────────────────────────────────────
def propose_issue(con: duckdb.DuckDBPyConnection, *, table_name: str, record_key: str, year: int | None,
                  issue_type: str, confidence: float, rule_id: str, explanation: str,
                  evidence: dict | str | None, proposed_fix: dict | str | None, created_by: str,
                  status: str = "proposed") -> str:
    """Insert or refresh an issue. Re-running a detector never resets a human decision."""
    if status not in ISSUE_STATUSES:
        raise ValueError(f"bad issue status {status!r}")
    issue_id = f"{rule_id}:{record_key}"
    prev = con.execute("SELECT status FROM issues WHERE issue_id = ?", [issue_id]).fetchone()
    if prev and prev[0] != "proposed":
        status = prev[0]
    con.execute("DELETE FROM issues WHERE issue_id = ?", [issue_id])
    con.execute("INSERT INTO issues VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                [issue_id, table_name, record_key, year, issue_type, float(confidence), rule_id,
                 explanation, _json(evidence), _json(proposed_fix), status, created_by, _now()])
    return issue_id


def set_issue_status(con: duckdb.DuckDBPyConnection, issue_id: str, status: str) -> None:
    if status not in ISSUE_STATUSES:
        raise ValueError(f"bad issue status {status!r}")
    con.execute("UPDATE issues SET status = ? WHERE issue_id = ?", [status, issue_id])


# ── corrections ───────────────────────────────────────────────────────
def apply_correction(con: duckdb.DuckDBPyConnection, issue_id: str, *, approved_by: str, reason: str,
                     field: str | None = None, old_value: Any = None, new_value: Any = None) -> str:
    """Record an approved change. Field/old/new default to the issue's proposed_fix.

    A human approval marks the issue `approved`; a DEV-ASSUMED one leaves it `proposed` for review.
    """
    _check_human(approved_by, allow_dev=True)
    row = con.execute("SELECT record_key, proposed_fix FROM issues WHERE issue_id = ?", [issue_id]).fetchone()
    if row is None:
        raise KeyError(f"unknown issue {issue_id!r}")
    fix = json.loads(row[1]) if row[1] else {}
    field = field if field is not None else fix.get("field")
    old_value = old_value if old_value is not None else fix.get("old_value")
    new_value = new_value if new_value is not None else fix.get("new_value")
    if not field:
        raise ValueError(f"issue {issue_id!r} has no proposed_fix; pass field/old_value/new_value")
    cid = f"corr:{issue_id}"
    con.execute("DELETE FROM corrections WHERE correction_id = ?", [cid])
    con.execute("INSERT INTO corrections VALUES (?,?,?,?,?,?,?,?,?)",
                [cid, issue_id, row[0], field, _json(old_value) if old_value is not None else None,
                 _json(new_value) if new_value is not None else None, reason, approved_by, _now()])
    if approved_by != DEV_ASSUMED:
        set_issue_status(con, issue_id, "approved")
    return cid


def export_corrections(con: duckdb.DuckDBPyConnection, path: Path | str | None = None) -> Path:
    path = Path(path) if path else REPO_ROOT / "out" / "corrections.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    con.execute("SELECT * FROM corrections ORDER BY correction_id").df().to_csv(path, index=False)
    return path


# ── results + lineage ─────────────────────────────────────────────────
def write_result(con: duckdb.DuckDBPyConnection, result_id: str, *, metric: str, value: float, unit: str,
                 method: str, produced_by: str, lineage: Iterable[Source | tuple],
                 scope: str | None = None, category: str | None = None, year: int | None = None,
                 scenario: str = "actual") -> None:
    """Write (or rewrite) one number with its trail. Rewriting resets it to `draft`."""
    links = [Source(*l) for l in lineage]
    if not links:
        raise ValueError(f"result {result_id!r} needs at least one lineage row")
    for l in links:
        if l.kind not in SOURCE_KINDS:
            raise ValueError(f"bad source_kind {l.kind!r} (one of {sorted(SOURCE_KINDS)})")
    con.execute("DELETE FROM results WHERE result_id = ?", [result_id])
    con.execute("DELETE FROM lineage WHERE result_id = ?", [result_id])
    con.execute("INSERT INTO results VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                [result_id, metric, scope, category, year, scenario, float(value), unit, method,
                 "draft", produced_by, _now()])
    con.executemany("INSERT INTO lineage VALUES (?,?,?,?,?)",
                    [[result_id, l.kind, str(l.ref), l.contribution, l.note] for l in links])


def orphan_published(con: duckdb.DuckDBPyConnection) -> list[str]:
    """Published results without lineage. Must be empty; tests/test_lineage.py enforces it."""
    return [r[0] for r in con.execute(
        "SELECT r.result_id FROM results r WHERE r.status = 'published' AND NOT EXISTS "
        "(SELECT 1 FROM lineage l WHERE l.result_id = r.result_id) ORDER BY 1").fetchall()]


def _set_result_status(con: duckdb.DuckDBPyConnection, result_ids: list[str], status: str, by: str) -> None:
    _check_human(by, allow_dev=False)
    for rid in result_ids:
        if not con.execute("SELECT 1 FROM lineage WHERE result_id = ? LIMIT 1", [rid]).fetchone():
            raise ValueError(f"result {rid!r} has no lineage; cannot set {status}")
        con.execute("UPDATE results SET status = ? WHERE result_id = ?", [status, rid])


def approve(con: duckdb.DuckDBPyConnection, result_ids: list[str], by: str) -> None:
    _set_result_status(con, result_ids, "approved", by)


def publish(con: duckdb.DuckDBPyConnection, result_ids: list[str], by: str) -> None:
    """Humans only. Only published results feed CSVs, the dashboard and the copilot."""
    _set_result_status(con, result_ids, "published", by)


def main() -> None:
    con = connect()
    init_schema(con)
    print("tables:", [r[0] for r in con.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_name IN "
        "('issues','corrections','results','lineage') ORDER BY 1").fetchall()])


if __name__ == "__main__":
    main()
