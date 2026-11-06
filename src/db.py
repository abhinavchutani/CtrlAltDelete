"""The one DuckDB connection every module uses.

    from src.db import connect
    con = connect()                 # NAVIGATOR_DB from env/.env, default out/navigator.duckdb
    con = connect(read_only=True)   # e.g. the Streamlit app

Paths in NAVIGATOR_DB are relative to the repo root.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import duckdb

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = "out/navigator.duckdb"


def env(key: str, default: str = "") -> str:
    """Read a setting from the environment, falling back to the repo's .env."""
    try:
        from dotenv import load_dotenv

        load_dotenv(REPO_ROOT / ".env", override=False)
    except ImportError:
        pass
    return os.environ.get(key) or default


def db_path() -> Path:
    p = Path(env("NAVIGATOR_DB", DEFAULT_DB)).expanduser()
    return p if p.is_absolute() else REPO_ROOT / p


def connect(path: Path | str | None = None, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    path = Path(path) if path else db_path()
    if not read_only:
        path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(path), read_only=read_only)


def git_sha() -> str:
    """Short SHA of HEAD, for `results.produced_by` (e.g. f"a_inventory@{git_sha()}")."""
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO_ROOT,
                             capture_output=True, text=True, check=True)
        return out.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "nogit"
