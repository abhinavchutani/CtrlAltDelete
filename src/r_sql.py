"""Retrieval layer (v2): read-only SQL over the frozen v1 snapshot (task #86, V2-9).

    from src.r_sql import run_sql
    run_sql("SELECT site_id, sum(value) FROM raw_energy_meter_readings WHERE year = 2024 GROUP BY 1")

Safety, enforced in code (never by a prompt):
* one statement; it must start with SELECT or WITH; write/DDL/IO keywords are refused;
* file-reading table functions (read_csv, read_parquet, glob, …) are refused;
* every referenced table must be on the allow-list: raw_*, clean_*, results, lineage, corrections;
* the connection is DuckDB read_only on out/serve.duckdb (env SERVE_DB), so a write would fail anyway;
* at most MAX_ROWS rows come back; a query running longer than TIMEOUT_S is interrupted.
Each answer carries its evidence: the tables used, the pack file behind each raw table and up to 20 record keys.
"""
from __future__ import annotations

import re
import threading
from functools import lru_cache
from pathlib import Path

import duckdb

from src.db import REPO_ROOT, env

MAX_ROWS = 500
TIMEOUT_S = 5.0
ALLOWED_PREFIXES = ("raw_", "clean_")
ALLOWED_TABLES = {"results", "lineage", "corrections"}
FORBIDDEN = re.compile(
    r"\b(insert|update|delete|merge|create|drop|alter|truncate|attach|detach|copy|export|import|pragma|install|load|"
    r"call|set|reset|vacuum|checkpoint|grant|revoke|begin|commit|rollback|use)\b", re.I)
FILE_FUNCS = re.compile(r"\b(read_\w+|duckdb_\w+|glob|sniff_csv|parquet_\w+|query_table|query|getenv|current_setting)\s*\(", re.I)


class SqlRefused(ValueError):
    """The statement is not a safe, allow-listed SELECT."""


def serve_db_path() -> Path:
    p = Path(env("SERVE_DB", "out/serve.duckdb")).expanduser()
    return p if p.is_absolute() else REPO_ROOT / p


def connect() -> duckdb.DuckDBPyConnection:
    """Read-only connection to the frozen snapshot (src.serve_db when platform's #83 lands)."""
    try:
        from src.serve_db import connect as serve_connect  # type: ignore[import-not-found]
        return serve_connect(read_only=True)
    except ImportError:
        return duckdb.connect(str(serve_db_path()), read_only=True)


def _strip(sql: str) -> str:
    sql = re.sub(r"--[^\n]*", " ", sql)
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.S)
    return sql.strip().rstrip(";").strip()


def _without_strings(sql: str) -> str:
    return re.sub(r"'(?:[^']|'')*'", "''", sql)


def allowed_table(name: str) -> bool:
    n = name.lower().split(".")[-1].strip('"')
    return n.startswith(ALLOWED_PREFIXES) or n in ALLOWED_TABLES


def check(sql: str, con: duckdb.DuckDBPyConnection | None = None) -> tuple[str, list[str]]:
    """The cleaned statement and its tables, or SqlRefused with the reason."""
    s = _strip(sql)
    bare = _without_strings(s)
    if not s:
        raise SqlRefused("empty statement")
    if ";" in bare:
        raise SqlRefused("one statement only")
    if not re.match(r"^\s*(select|with)\b", bare, re.I):
        raise SqlRefused("only SELECT (or WITH … SELECT) is allowed")
    if m := FORBIDDEN.search(bare):
        raise SqlRefused(f"'{m.group(1).upper()}' is not allowed in a read-only query")
    if m := FILE_FUNCS.search(bare):
        raise SqlRefused(f"table function '{m.group(1)}' is not allowed; query the loaded tables")
    try:
        parse_me = re.sub(r"\?|\$\d+", "NULL", s)  # placeholders can't be parsed for table names
        tables = sorted((con or duckdb.connect()).get_table_names(parse_me))
    except duckdb.Error as e:
        raise SqlRefused(f"could not parse: {e}") from e
    bad = [t for t in tables if not allowed_table(t)]
    if bad:
        raise SqlRefused(f"table(s) not on the allow-list: {', '.join(bad)} (raw_*, clean_*, results, lineage, corrections)")
    return s, tables


@lru_cache(maxsize=1)
def source_files() -> dict[str, str]:
    """raw_<table> → pack file path (relative to the pack's data/), as src.load names them."""
    from src.load import pack_dir, table_name
    data = pack_dir() / "data"
    out = {f"raw_{table_name(p.stem)}": str(p.relative_to(data)) for p in sorted(data.glob("0*/*.csv"))} if data.is_dir() else {}
    out["raw_supplier_pcfs"] = "02_raw_feeds/supplier_pcfs/*.json"
    out["raw_weather_daily"] = "04_climate/weather_daily_1991_2060.parquet"
    return out


def run_sql(sql: str, params: list | None = None, con: duckdb.DuckDBPyConnection | None = None,
            max_rows: int = MAX_ROWS, timeout_s: float = TIMEOUT_S) -> dict:
    """Rows of a safe SELECT, capped and timed, with tables, source files and record keys as evidence."""
    own = con is None
    con = con or connect()
    try:
        s, tables = check(sql, con)
        timer = threading.Timer(timeout_s, con.interrupt)
        timer.start()
        try:
            cur = con.execute(f"SELECT * FROM ({s}) AS _q LIMIT {int(max_rows) + 1}", params or [])
            cols = [d[0] for d in cur.description]
            rows = cur.fetchall()
        except duckdb.InterruptException as e:
            raise SqlRefused(f"query took longer than {timeout_s:g} s") from e
        except duckdb.Error as e:
            raise SqlRefused(f"query failed: {str(e).splitlines()[0]}") from e
        finally:
            timer.cancel()
    finally:
        if own:
            con.close()
    truncated = len(rows) > max_rows
    rows = [list(r) for r in rows[:max_rows]]
    keys = []
    if "record_key" in cols:
        i = cols.index("record_key")
        keys = list(dict.fromkeys(str(r[i]) for r in rows if r[i] is not None))[:20]
    files = source_files()
    return {"sql": s, "params": params or [], "columns": cols, "rows": rows, "n_rows": len(rows),
            "truncated": truncated, "tables": tables,
            "source_files": {t: files[t] for t in tables if t in files}, "record_keys": keys}


def main(argv: list[str] | None = None) -> None:
    import json
    import sys
    sql = " ".join(argv if argv is not None else sys.argv[1:]) or "SELECT count(*) AS n FROM results"
    try:
        out = run_sql(sql)
        print(json.dumps({k: v for k, v in out.items() if k != "rows"} | {"rows": out["rows"][:10]}, default=str, indent=1))
    except SqlRefused as e:
        print(f"refused: {e}")


if __name__ == "__main__":
    main()
