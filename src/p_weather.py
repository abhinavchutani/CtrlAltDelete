"""Prediction layer: the weather layer (V2_ARCHITECTURE "Weather layer", `GET /api/weather`).

Run:  python -m src.p_weather      (reads the frozen out/serve.duckdb; writes out/v2/weather/*.json)

One `WeatherFrame` per climate × year: 'historical' 1991–2026 and ssp126 / ssp245 / ssp585 2027–2060,
each with a `WeatherCell` for all 84 grid cells:

* tmax_anom_c        Apr–Sep mean Tmax minus the cell's 1991–2020 mean of the same quantity (0.1 °C)
* precip_anom_pct    Apr–Sep rain sum vs the cell's 1991–2020 mean, in % (whole %)
* drought_index      pea flowering-stage drought (`drought_sens`, 1 − ΣAET/ΣPET from the c_features
                     soil-water bucket) for the cell's most common parcel soil, 'clay' where a cell
                     has no parcels; clipped to 0–1 (2 dp)
* hot_days_flowering pea `hot_sens`: days with Tmax ≥ 27 °C in the flowering stage

Deterministic; every number comes from this code and the pack's daily weather. The futures are one
synthetic realisation per SSP, not forecasts, and none of this describes real farms.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import duckdb
import pandas as pd

from src import c_features
from src.db import REPO_ROOT, env

BASE_YEARS = (1991, 2020)
GROWING_MONTHS = (4, 9)                 # Apr–Sep
HIST_YEARS = (1991, 2026)
FUTURE_YEARS = (2027, 2060)
SSPS = ("ssp126", "ssp245", "ssp585")
DEFAULT_SOIL = "clay"
CELL_KEYS = ("cell_id", "region", "lat", "lon", "tmax_anom_c", "precip_anom_pct",
             "drought_index", "hot_days_flowering")


def serve_db_path() -> Path:
    """The frozen snapshot (env SERVE_DB, default out/serve.duckdb)."""
    p = Path(env("SERVE_DB", "out/serve.duckdb")).expanduser()
    return p if p.is_absolute() else REPO_ROOT / p


def default_dir() -> Path:
    return REPO_ROOT / "out" / "v2" / "weather"


def open_snapshot(path: Path | str | None = None) -> duckdb.DuckDBPyConnection:
    """In-memory connection with the snapshot attached read-only and a `main` view per table or view
    (the snapshot's raw_weather_daily is itself a view over the pack's parquet)."""
    con = duckdb.connect(":memory:")
    con.execute(f"ATTACH '{Path(path) if path else serve_db_path()}' AS s (READ_ONLY)")
    tables = con.execute("""SELECT table_name FROM duckdb_tables() WHERE database_name = 's' UNION
                            SELECT view_name FROM duckdb_views() WHERE database_name = 's' AND NOT internal""").fetchall()
    for (t,) in tables:
        con.execute(f'CREATE VIEW main."{t}" AS SELECT * FROM s."{t}"')
    return con


def _has(con: duckdb.DuckDBPyConnection, table: str) -> bool:
    q = "SELECT count(*) FROM duckdb_views() WHERE view_name = ? UNION ALL SELECT count(*) FROM duckdb_tables() WHERE table_name = ?"
    return sum(r[0] for r in con.execute(q, [table, table]).fetchall()) > 0


def _in_scope_sql() -> str:
    """Scenario × year combinations that make a frame (historical ≤ 2026, SSPs ≥ 2027)."""
    ssps = ", ".join(f"'{s}'" for s in SSPS)
    return (f"((scenario = 'historical' AND year BETWEEN {HIST_YEARS[0]} AND {HIST_YEARS[1]}) OR "
            f"(scenario IN ({ssps}) AND year BETWEEN {FUTURE_YEARS[0]} AND {FUTURE_YEARS[1]}))")


def season_anomalies(con: duckdb.DuckDBPyConnection, source: str = "raw_weather_daily") -> pd.DataFrame:
    """Per (cell_id, scenario, year): Apr–Sep Tmax and rain anomalies vs the cell's 1991–2020 historical mean."""
    m0, m1 = GROWING_MONTHS
    b0, b1 = BASE_YEARS
    return con.execute(f"""
        WITH s AS (
            SELECT cell_id, scenario, year(date) AS year, avg(tmax_c) AS tmax_gs, sum(precip_mm) AS precip_gs
            FROM {source} WHERE month(date) BETWEEN {m0} AND {m1} GROUP BY ALL),
        b AS (
            SELECT cell_id, avg(tmax_gs) AS tmax_base, avg(precip_gs) AS precip_base
            FROM s WHERE scenario = 'historical' AND year BETWEEN {b0} AND {b1} GROUP BY ALL)
        SELECT s.cell_id, s.scenario, s.year,
               round(s.tmax_gs - b.tmax_base, 1) AS tmax_anom_c,
               round(100 * (s.precip_gs / nullif(b.precip_base, 0) - 1), 0) AS precip_anom_pct
        FROM s JOIN b USING (cell_id)
        WHERE {_in_scope_sql()}""").df()


def dominant_soil(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """cell_id → most common parcel soil class (ties broken alphabetically); 'clay' where no parcels."""
    if _has(con, "raw_parcels") and _has(con, "c_parcel_cell"):
        soil = con.execute("""
            SELECT g.cell_id, coalesce(d.soil, ?) AS soil FROM raw_climate_grid_cells g LEFT JOIN (
                SELECT pc.cell_id, p.soil_class_soilmap AS soil,
                       row_number() OVER (PARTITION BY pc.cell_id ORDER BY count(*) DESC, p.soil_class_soilmap) AS r
                FROM raw_parcels p JOIN c_parcel_cell pc USING (parcel_id)
                WHERE p.soil_class_soilmap IS NOT NULL GROUP BY pc.cell_id, p.soil_class_soilmap
            ) d ON d.cell_id = g.cell_id AND d.r = 1""", [DEFAULT_SOIL]).df()
    else:
        soil = con.execute("SELECT cell_id, ? AS soil FROM raw_climate_grid_cells", [DEFAULT_SOIL]).df()
    soil.loc[~soil["soil"].isin(list(c_features.BUCKET_MM)), "soil"] = DEFAULT_SOIL
    return soil


def pea_flowering(con: duckdb.DuckDBPyConnection, source: str = "raw_weather_daily") -> pd.DataFrame:
    """Per (cell_id, scenario, year, soil): pea drought_sens and hot_sens. Uses `c_stage_features` if
    present, else computes them with `c_features.build` (pea only)."""
    if _has(con, "c_stage_features"):
        return con.execute("""SELECT cell_id, scenario, year, soil, drought_sens, hot_sens
                              FROM c_stage_features WHERE crop = 'pea'""").df()
    df = c_features.build(con, source, crops={"pea": c_features.CROPS["pea"]})
    return df[["cell_id", "scenario", "year", "soil", "drought_sens", "hot_sens"]]


def cell_table(con: duckdb.DuckDBPyConnection, source: str = "raw_weather_daily") -> pd.DataFrame:
    """All WeatherCell fields plus climate and year, one row per cell × climate × year."""
    anom = season_anomalies(con, source)
    stage = pea_flowering(con, source).merge(dominant_soil(con), on=["cell_id", "soil"])
    grid = con.execute("SELECT cell_id, region, lat, lon FROM raw_climate_grid_cells").df()
    df = anom.merge(stage.drop(columns="soil"), on=["cell_id", "scenario", "year"], how="left").merge(grid, on="cell_id")
    df["drought_index"] = df["drought_sens"].fillna(0.0).clip(0.0, 1.0).round(2)
    df["hot_days_flowering"] = df["hot_sens"].fillna(0.0).round().astype(int)
    df["precip_anom_pct"] = df["precip_anom_pct"].fillna(0.0)
    df = df.rename(columns={"scenario": "climate"})
    return df[["climate", "year", *CELL_KEYS]].sort_values(["climate", "year", "cell_id"], ignore_index=True)


def frames_from_table(df: pd.DataFrame) -> dict[tuple[str, int], dict]:
    """Group a cell table into WeatherFrame dicts keyed by (climate, year)."""
    out: dict[tuple[str, int], dict] = {}
    for (climate, year), g in df.groupby(["climate", "year"], sort=True):
        cells = g[list(CELL_KEYS)].to_dict("records")
        for c in cells:   # plain JSON types
            c["lat"], c["lon"] = float(c["lat"]), float(c["lon"])
            c["tmax_anom_c"], c["precip_anom_pct"] = float(c["tmax_anom_c"]), float(c["precip_anom_pct"])
            c["drought_index"], c["hot_days_flowering"] = float(c["drought_index"]), int(c["hot_days_flowering"])
        out[(str(climate), int(year))] = {"climate": str(climate), "year": int(year), "cells": cells}
    return out


def frames(con: duckdb.DuckDBPyConnection, source: str = "raw_weather_daily") -> dict[tuple[str, int], dict]:
    """One WeatherFrame dict per (climate, year): historical 1991–2026, each SSP 2027–2060."""
    return frames_from_table(cell_table(con, source))


def write_frames(frames: dict[tuple[str, int], dict], out_dir: Path | str | None = None) -> Path:
    """Write `{climate}_{year}.json` per frame and `index.json` listing the pairs. Returns the folder."""
    d = Path(out_dir) if out_dir else default_dir()
    d.mkdir(parents=True, exist_ok=True)
    for (climate, year), f in frames.items():
        (d / f"{climate}_{year}.json").write_text(json.dumps(f, separators=(",", ":")))
    index = {"frames": [{"climate": c, "year": y} for c, y in sorted(frames)],
             "climates": sorted({c for c, _ in frames}),
             "base_years": list(BASE_YEARS), "growing_months": list(GROWING_MONTHS)}
    (d / "index.json").write_text(json.dumps(index, indent=1))
    return d


def get_frame(climate: str, year: int, out_dir: Path | str | None = None) -> dict:
    """The precomputed WeatherFrame for (climate, year). Raises FileNotFoundError if absent."""
    d = Path(out_dir) if out_dir else default_dir()
    name = f"{climate}_{int(year)}.json"
    if "/" in climate or "\\" in climate or ".." in climate:
        raise ValueError(f"bad climate {climate!r}")
    return json.loads((d / name).read_text())


def drought_check(table: pd.DataFrame, year: int = 2026) -> dict[str, tuple[float, float]]:
    """Per region: (mean drought_index in `year`, mean over historical 1991..year-1)."""
    h = table[table["climate"] == "historical"]
    out = {}
    for region, g in h.groupby("region"):
        out[str(region)] = (float(g.loc[g.year == year, "drought_index"].mean()),
                            float(g.loc[g.year < year, "drought_index"].mean()))
    return out


def main() -> None:
    t0 = time.time()
    con = open_snapshot()
    table = cell_table(con)
    fr = frames_from_table(table)
    d = write_frames(fr)
    dt = time.time() - t0
    n_cells = {len(f["cells"]) for f in fr.values()}
    print(f"p_weather: {len(fr)} frames ({', '.join(sorted({c for c, _ in fr}))}), cells per frame {n_cells}, "
          f"written to {d} in {dt:.1f} s")
    for region, (y, base) in drought_check(table).items():
        print(f"  2026 historical drought_index {region}: {y:.2f} vs 1991–2025 mean {base:.2f} ({y - base:+.2f})")
    t1 = time.perf_counter()
    get_frame("ssp245", 2035)
    print(f"  get_frame('ssp245', 2035): {1000 * (time.perf_counter() - t1):.1f} ms")


if __name__ == "__main__":
    main()
