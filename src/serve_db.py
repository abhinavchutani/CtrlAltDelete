"""The frozen v1 data that every v2 layer reads (docs/V2_ARCHITECTURE.md, "Repo decision").

    from src.serve_db import connect
    con = connect()                 # read-only on SERVE_DB (default out/serve.duckdb)

`make snapshot` (python -m src.serve_db) copies NAVIGATOR_DB → SERVE_DB. v2 never writes to
v1's tables; reading a copy also avoids the DuckDB lock the Streamlit app holds.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import duckdb

from src.db import REPO_ROOT, db_path, env

DEFAULT_SERVE_DB = "out/serve.duckdb"


def serve_path() -> Path:
    p = Path(env("SERVE_DB", DEFAULT_SERVE_DB)).expanduser()
    return p if p.is_absolute() else REPO_ROOT / p


def exists() -> bool:
    return serve_path().is_file()


def connect(read_only: bool = True) -> duckdb.DuckDBPyConnection:
    """Open serve.duckdb. v2 code always reads; `read_only=False` only for a private copy."""
    path = serve_path()
    if not path.is_file():
        raise FileNotFoundError(f"{path} is missing: run `make snapshot` first")
    return duckdb.connect(str(path), read_only=read_only)


def snapshot(src: Path | None = None, dst: Path | None = None) -> Path:
    """Copy navigator.duckdb to serve.duckdb (a plain file copy; v1 is frozen, so it is stable)."""
    src = src or db_path()
    dst = dst or serve_path()
    if not src.is_file():
        raise FileNotFoundError(f"{src} is missing: build v1 with `make all` (or set NAVIGATOR_DB)")
    if src.with_name(src.name + ".wal").exists():
        print(f"warning: {src.name}.wal exists; the copy may miss unflushed writes", file=sys.stderr)
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(dst.name + ".tmp")
    shutil.copyfile(src, tmp)
    tmp.replace(dst)
    with duckdb.connect(str(dst), read_only=True) as con:  # fail loudly if the copy is unreadable
        n = con.execute("select count(*) from information_schema.tables").fetchone()[0]
    print(f"snapshot: {src} → {dst} ({n} tables, {dst.stat().st_size / 1e6:.1f} MB)")
    return dst


if __name__ == "__main__":
    snapshot()
