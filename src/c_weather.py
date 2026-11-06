"""Climate lane: weather access and the parcel → climate-grid-cell link (task #14).

Run:  python -m src.c_weather          (builds c_parcel_cell, prints a summary)

* `build_parcel_cell(con)` links every parcel (01_master/parcels.csv lat/lon) to its nearest
  climate grid cell (great-circle distance) and writes table `c_parcel_cell`
  (parcel_id, farm_id, cell_id, region, distance_km).
* `weather(con, cells=…, scenario=…, start=…, end=…, columns=…)` returns daily weather from the
  `raw_weather_daily` view (Parquet, 4.2M rows) with filters pushed down to DuckDB.
* `weather_for_parcels(con, …)` joins daily weather to parcels through `c_parcel_cell`.

Scenarios in the pack: 'historical' (1991–2026) and 'ssp126' / 'ssp245' / 'ssp585' (2027–2060).
Needs `python -m src.load` first (raw_parcels, raw_climate_grid_cells, raw_weather_daily).
"""
from __future__ import annotations

from typing import Iterable, Sequence

import duckdb
import numpy as np
import pandas as pd

from src import load

EARTH_RADIUS_KM = 6371.0
SCENARIOS = ("historical", "ssp126", "ssp245", "ssp585")
WEATHER_COLUMNS = ("tmean_c", "tmax_c", "tmin_c", "precip_mm", "rad_mj_m2", "pet_mm")


def haversine_km(lat1: np.ndarray, lon1: np.ndarray, lat2: np.ndarray, lon2: np.ndarray) -> np.ndarray:
    """Pairwise great-circle distance; inputs broadcast (use [:, None] vs [None, :] for a matrix)."""
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = p2 - p1
    dlmb = np.radians(lon2) - np.radians(lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(a))


def nearest_cells(parcels: pd.DataFrame, cells: pd.DataFrame) -> pd.DataFrame:
    """For each parcel row (lat, lon) the nearest cell row (cell_id, region, distance_km)."""
    d = haversine_km(parcels["lat"].to_numpy()[:, None], parcels["lon"].to_numpy()[:, None],
                     cells["lat"].to_numpy()[None, :], cells["lon"].to_numpy()[None, :])
    idx = d.argmin(axis=1)
    out = parcels[["parcel_id", "farm_id"]].copy()
    out["cell_id"] = cells["cell_id"].to_numpy()[idx]
    out["region"] = cells["region"].to_numpy()[idx]
    out["distance_km"] = d[np.arange(len(parcels)), idx].round(3)
    return out.reset_index(drop=True)


def build_parcel_cell(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    parcels = con.execute("SELECT parcel_id, farm_id, lat, lon FROM raw_parcels").df()
    cells = con.execute("SELECT cell_id, region, lat, lon FROM raw_climate_grid_cells").df()
    link = nearest_cells(parcels, cells)
    con.register("_link", link)
    con.execute("CREATE OR REPLACE TABLE c_parcel_cell AS SELECT * FROM _link")
    con.unregister("_link")
    return link


def _in_list(values: Iterable[str]) -> str:
    vals = [str(v).replace("'", "''") for v in values]
    return "(" + ",".join(f"'{v}'" for v in vals) + ")"


def weather(con: duckdb.DuckDBPyConnection, cells: Sequence[str] | None = None,
            scenario: str | Sequence[str] | None = "historical", start: str | None = None,
            end: str | None = None, columns: Sequence[str] = WEATHER_COLUMNS) -> pd.DataFrame:
    """Daily weather with filters pushed into the Parquet scan. Dates are ISO strings (inclusive)."""
    bad = set(columns) - set(WEATHER_COLUMNS)
    if bad:
        raise ValueError(f"unknown weather columns: {sorted(bad)}")
    where = []
    if cells is not None:
        where.append(f"cell_id IN {_in_list(cells)}")
    if scenario is not None:
        scen = [scenario] if isinstance(scenario, str) else list(scenario)
        unknown = set(scen) - set(SCENARIOS)
        if unknown:
            raise ValueError(f"unknown scenario(s): {sorted(unknown)}")
        where.append(f"scenario IN {_in_list(scen)}")
    if start:
        where.append(f"date >= DATE '{pd.Timestamp(start).date()}'")
    if end:
        where.append(f"date <= DATE '{pd.Timestamp(end).date()}'")
    sql = (f"SELECT cell_id, scenario, CAST(date AS DATE) AS date, {', '.join(columns)} FROM raw_weather_daily"
           + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY cell_id, date")
    return con.execute(sql).df()


def weather_for_parcels(con: duckdb.DuckDBPyConnection, parcel_ids: Sequence[str], **kw) -> pd.DataFrame:
    """Daily weather for the cells of the given parcels, with parcel_id attached (one row per parcel-day)."""
    link = con.execute(f"SELECT parcel_id, cell_id FROM c_parcel_cell WHERE parcel_id IN {_in_list(parcel_ids)}").df()
    w = weather(con, cells=sorted(link.cell_id.unique()), **kw)
    return link.merge(w, on="cell_id", how="left")


def main() -> None:
    con = load.connect()
    link = build_parcel_cell(con)
    print(f"c_parcel_cell: {len(link):,} parcels → {link.cell_id.nunique()} cells")
    print(link.groupby("region").agg(parcels=("parcel_id", "size"), cells=("cell_id", "nunique"),
                                     max_km=("distance_km", "max"), mean_km=("distance_km", "mean")).round(2).to_string())


if __name__ == "__main__":
    main()
