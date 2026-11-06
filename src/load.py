"""Load every file of the data pack, untouched, into `raw_*` tables in DuckDB.

Run:  python -m src.load            (all tables, prints row counts)
      python -m src.load --db PATH  (custom database file)

Rules (docs/CONTRACTS.md):
* Nothing is cleaned or corrected here. Parsing only: CSV types, the Foodhills file's `;` and
  decimal commas, and the PACT JSON PCFs flattened to one row per file.
* A `record_key` column in the official A1 format is added wherever TASKS_AND_SCORING.md defines one,
  so the same key works in the A1 CSV, the lineage table and the copilot's citations.
* The 4.2M-row daily weather Parquet is registered as a VIEW (`raw_weather_daily`), not copied.
* Task files (dev keys, templates, E questions) are loaded as `task_*` tables for scoring.

Reads the pack location from DATA_DIR (env or .env); default ./data/APETIT_CLIMATE_NATURE_NAVIGATOR_2026.
This module deliberately does not import the pack's own code.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Callable

import duckdb
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = "data/APETIT_CLIMATE_NATURE_NAVIGATOR_2026"
DEFAULT_DB = "out/navigator.duckdb"


# ── configuration ─────────────────────────────────────────────────────
def _env(key: str, default: str) -> str:
    try:
        from dotenv import load_dotenv

        load_dotenv(REPO_ROOT / ".env", override=False)
    except ImportError:  # dotenv is optional
        pass
    return os.environ.get(key) or default


def _resolve(path: str) -> Path:
    p = Path(path).expanduser()
    return p if p.is_absolute() else (REPO_ROOT / p)


def pack_dir() -> Path:
    """Root of the unzipped pack (the folder that contains data/, docs/, tasks/, tools/)."""
    return _resolve(_env("DATA_DIR", DEFAULT_DATA_DIR))


def db_path() -> Path:
    return _resolve(_env("NAVIGATOR_DB", DEFAULT_DB))


# ── record keys (official A1 formats, TASKS_AND_SCORING.md) ───────────
def _key(prefix: str, df: pd.DataFrame, cols: list[str]) -> pd.Series:
    """`prefix:col1:col2…` with every column rendered as text."""
    out = pd.Series(prefix, index=df.index, dtype="string")
    for c in cols:
        out = out + ":" + df[c].astype("string")
    return out


def key_erp(df: pd.DataFrame) -> pd.Series:
    return _key("erp", df, ["doc_no", "line_no"])


def key_energy(df: pd.DataFrame) -> pd.Series:
    ym = df["year"].astype(int).astype(str) + "-" + df["month"].astype(int).map("{:02d}".format)
    return "energy:" + df["site_id"].astype(str) + ":" + ym + ":" + df["carrier"].astype(str)


KEY_BUILDERS: dict[str, Callable[[pd.DataFrame], pd.Series]] = {
    "erp_purchase_lines": key_erp,
    "energy_meter_readings": key_energy,
    "fuel_deliveries": lambda d: _key("fuel", d, ["delivery_id"]),
    "goo_cancellations": lambda d: _key("goo", d, ["site_id", "year"]),
    "refrigerant_service_log": lambda d: _key("refrigerant", d, ["event_id"]),
    "waste_transfer_notes": lambda d: _key("waste", d, ["transfer_note"]),
    "travel_bookings": lambda d: _key("travel", d, ["booking_id"]),
    "commuting_survey": lambda d: _key("commute", d, ["response_id"]),
    "shipments": lambda d: _key("ship", d, ["ref_doc", "ef_id"]),
    "farm_survey_fi": lambda d: _key("farm_survey", d, ["survey_id"]),
    "farm_registry": lambda d: _key("farm", d, ["farm_id"]),
    "supplier_pcfs": lambda d: _key("pcf", d, ["supplier_id", "material_id", "year"]),
    "draft_report_summary": lambda d: _key("report", d, ["year", "line"]),
}

# file stem → table name (drop year-range suffixes so names are stable)
RENAMES = {
    "erp_purchase_lines_2021_2025": "erp_purchase_lines",
    "commuting_survey_2025": "commuting_survey",
    "draft_report_summary_2025": "draft_report_summary",
    "weather_monthly_1991_2060": "weather_monthly",
}

# columns that must stay text (ids with leading zeros etc.)
STR_COLS = {"doc_no", "reference_doc", "ref_doc", "lot_id", "line", "survey_id", "booking_id",
            "transfer_note", "event_id", "delivery_id", "response_id", "shipment_id", "cancellation_id"}


# ── readers ───────────────────────────────────────────────────────────
def read_csv(path: Path) -> pd.DataFrame:
    if path.name.startswith("foodhills_"):
        return pd.read_csv(path, sep=";", decimal=",", encoding="utf-8")
    header = pd.read_csv(path, nrows=0).columns
    dtype = {c: "string" for c in header if c in STR_COLS}
    return pd.read_csv(path, dtype=dtype, low_memory=False)


def read_pcfs(folder: Path) -> pd.DataFrame:
    """PACT v2-style JSON → one row per file. Values kept as declared (no validity check here)."""
    rows = []
    for f in sorted(folder.glob("*.json")):
        js = json.loads(f.read_text())
        pcf = js.get("pcf", {})
        supplier_id, material_id, year = f.stem.split("_")
        rows.append(dict(
            file=f.name, supplier_id=supplier_id, material_id=material_id, year=int(year),
            pcf_id=js.get("id"), status=js.get("status"), created=js.get("created"),
            product_description=js.get("productDescription"),
            declared_unit=pcf.get("declaredUnit"),
            unitary_product_amount=pcf.get("unitaryProductAmount"),
            pcf_excluding_biogenic_raw=pcf.get("pCfExcludingBiogenic"),
            pcf_excluding_biogenic=pd.to_numeric(pcf.get("pCfExcludingBiogenic"), errors="coerce"),
            reference_period_start=pcf.get("referencePeriodStart"),
            reference_period_end=pcf.get("referencePeriodEnd"),
        ))
    return pd.DataFrame(rows)


def table_name(stem: str) -> str:
    return RENAMES.get(stem, stem)


def with_record_key(name: str, df: pd.DataFrame) -> pd.DataFrame:
    builder = KEY_BUILDERS.get(name)
    if builder is not None and len(df):
        df = df.copy()
        df.insert(0, "record_key", builder(df).astype(str))
    return df


# ── loading ───────────────────────────────────────────────────────────
def _write(con: duckdb.DuckDBPyConnection, table: str, df: pd.DataFrame) -> int:
    con.register("_df", df)
    con.execute(f'CREATE OR REPLACE TABLE "{table}" AS SELECT * FROM _df')
    con.unregister("_df")
    return len(df)


def load_all(con: duckdb.DuckDBPyConnection, root: Path | None = None) -> dict[str, int]:
    root = root or pack_dir()
    data = root / "data"
    if not data.is_dir():
        raise FileNotFoundError(f"pack data not found at {data} (set DATA_DIR)")
    counts: dict[str, int] = {}

    for path in sorted(data.glob("0*/*.csv")):
        name = table_name(path.stem)
        counts[f"raw_{name}"] = _write(con, f"raw_{name}", with_record_key(name, read_csv(path)))

    pcfs = with_record_key("supplier_pcfs", read_pcfs(data / "02_raw_feeds" / "supplier_pcfs"))
    counts["raw_supplier_pcfs"] = _write(con, "raw_supplier_pcfs", pcfs)

    weather = (data / "04_climate" / "weather_daily_1991_2060.parquet").resolve()
    con.execute(f"CREATE OR REPLACE VIEW raw_weather_daily AS SELECT * FROM read_parquet('{weather}')")
    counts["raw_weather_daily (view)"] = con.execute("SELECT count(*) FROM raw_weather_daily").fetchall()[0][0]

    tasks = root / "tasks"
    for path in sorted(list(tasks.glob("*.csv")) + list(tasks.glob("dev/*.csv")) + list(tasks.glob("templates/*.csv"))):
        prefix = "task_dev_" if path.parent.name == "dev" else "task_template_" if path.parent.name == "templates" else "task_"
        counts[prefix + path.stem] = _write(con, prefix + path.stem, read_csv(path))
    return counts


def connect(path: Path | None = None) -> duckdb.DuckDBPyConnection:
    path = path or db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(path))


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", type=Path, default=None, help=f"DuckDB file (default NAVIGATOR_DB or {DEFAULT_DB})")
    args = ap.parse_args(argv)
    con = connect(args.db)
    counts = load_all(con)
    width = max(map(len, counts))
    for name, n in counts.items():
        print(f"{name:<{width}}  {n:>10,}")
    print(f"\n{len(counts)} tables/views → {args.db or db_path()}")


if __name__ == "__main__":
    main()
