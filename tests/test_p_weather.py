"""Tests for the weather layer (src/p_weather.py). Unit tests use a tiny fake DuckDB; one test reads
the frozen snapshot out/serve.duckdb and skips when it is missing (CI)."""
from __future__ import annotations

import json
import time

import duckdb
import numpy as np
import pandas as pd
import pytest

from src import p_weather as pw
from src.db import REPO_ROOT

CELL_KEYS = {"cell_id", "region", "lat", "lon", "tmax_anom_c", "precip_anom_pct",
             "drought_index", "hot_days_flowering"}


def _days(cell: str, scenario: str, year: int, tmax: float, precip: float) -> pd.DataFrame:
    d = pd.date_range(f"{year}-04-01", f"{year}-10-31", freq="D")
    return pd.DataFrame({"cell_id": cell, "scenario": scenario, "date": d, "tmean_c": 14.0, "tmax_c": tmax,
                         "tmin_c": 8.0, "precip_mm": precip, "rad_mj_m2": 15.0, "pet_mm": 3.0})


@pytest.fixture()
def fake_con() -> duckdb.DuckDBPyConnection:
    """Two cells; baseline 1991–2020 tmax 20 °C, 2 mm/day. 2021: A hotter and drier, B cooler and wetter.
    ssp245 2030: A at tmax 23 °C."""
    parts = [_days(c, "historical", y, 20.0, 2.0) for c in ("A", "B") for y in range(1991, 2021)]
    parts += [_days("A", "historical", 2021, 22.0, 1.0), _days("B", "historical", 2021, 19.0, 3.0),
              _days("A", "ssp245", 2030, 23.0, 2.0), _days("B", "ssp245", 2030, 20.0, 2.0)]
    w = pd.concat(parts, ignore_index=True)
    grid = pd.DataFrame({"cell_id": ["A", "B"], "region": ["FI_SW", "SE_SKANE"], "lat": [60.1, 55.6], "lon": [22.1, 13.2]})
    con = duckdb.connect(":memory:")
    con.register("_w", w)
    con.register("_g", grid)
    con.execute("CREATE TABLE raw_weather_daily AS SELECT * FROM _w")
    con.execute("CREATE TABLE raw_climate_grid_cells AS SELECT * FROM _g")
    return con


def test_anomaly_math(fake_con):
    a = pw.season_anomalies(fake_con).set_index(["cell_id", "scenario", "year"])
    assert a.loc[("A", "historical", 2021), "tmax_anom_c"] == pytest.approx(2.0)
    assert a.loc[("A", "historical", 2021), "precip_anom_pct"] == pytest.approx(-50.0)
    assert a.loc[("B", "historical", 2021), "tmax_anom_c"] == pytest.approx(-1.0)
    assert a.loc[("B", "historical", 2021), "precip_anom_pct"] == pytest.approx(50.0)
    # futures are measured against the historical 1991–2020 base
    assert a.loc[("A", "ssp245", 2030), "tmax_anom_c"] == pytest.approx(3.0)
    assert a.loc[("A", "historical", 2000), "tmax_anom_c"] == pytest.approx(0.0)


def test_frame_shape(fake_con):
    fr = pw.frames(fake_con)
    assert ("historical", 2021) in fr and ("ssp245", 2030) in fr
    assert len(fr) == 30 + 1 + 1
    f = fr[("historical", 2021)]
    assert set(f) == {"climate", "year", "cells"} and f["climate"] == "historical" and f["year"] == 2021
    assert len(f["cells"]) == 2
    for c in f["cells"]:
        assert set(c) == CELL_KEYS
        assert 0.0 <= c["drought_index"] <= 1.0
        assert isinstance(c["hot_days_flowering"], int)
    a = next(c for c in f["cells"] if c["cell_id"] == "A")
    b = next(c for c in f["cells"] if c["cell_id"] == "B")
    assert a["region"] == "FI_SW" and a["lat"] == pytest.approx(60.1)
    assert a["hot_days_flowering"] == 0                 # tmax 22 < 27
    assert a["drought_index"] >= b["drought_index"]     # 1 mm/day vs 3 mm/day against PET 3
    json.dumps(f)                                       # plain JSON types


def test_hot_days_and_soil(fake_con):
    fake_con.execute("UPDATE raw_weather_daily SET tmax_c = 30 WHERE cell_id = 'A' AND year(date) = 2021")
    parcels = pd.DataFrame({"parcel_id": ["p1", "p2", "p3"], "soil_class_soilmap": ["sand", "sand", "clay"]})
    pc = pd.DataFrame({"parcel_id": ["p1", "p2", "p3"], "cell_id": ["A", "A", "A"]})
    fake_con.register("_p", parcels)
    fake_con.register("_pc", pc)
    fake_con.execute("CREATE TABLE raw_parcels AS SELECT * FROM _p")
    fake_con.execute("CREATE TABLE c_parcel_cell AS SELECT * FROM _pc")
    soil = pw.dominant_soil(fake_con).set_index("cell_id")["soil"]
    assert soil["A"] == "sand" and soil["B"] == "clay"   # B has no parcels → clay
    a = next(c for c in pw.frames(fake_con)[("historical", 2021)]["cells"] if c["cell_id"] == "A")
    assert a["hot_days_flowering"] > 0


def test_write_and_get(fake_con, tmp_path):
    fr = pw.frames(fake_con)
    pw.write_frames(fr, tmp_path)
    idx = json.loads((tmp_path / "index.json").read_text())
    assert {"climate": "ssp245", "year": 2030} in idx["frames"] and len(idx["frames"]) == len(fr)
    assert pw.get_frame("historical", 2021, tmp_path) == fr[("historical", 2021)]
    with pytest.raises(FileNotFoundError):
        pw.get_frame("ssp585", 2031, tmp_path)


@pytest.mark.skipif(not (REPO_ROOT / "out" / "serve.duckdb").exists(), reason="needs out/serve.duckdb")
def test_snapshot_2035_ssp245(tmp_path):
    con = pw.open_snapshot()
    fr = pw.frames(con)
    assert len(fr) == 36 + 3 * 34
    f = fr[("ssp245", 2035)]
    assert len(f["cells"]) == 84
    assert all(set(c) == CELL_KEYS for c in f["cells"])
    assert {c["region"] for c in f["cells"]} == {"FI_SW", "SE_SKANE"}
    assert not any(np.isnan(c[k]) for c in f["cells"] for k in ("tmax_anom_c", "precip_anom_pct", "drought_index"))
    pw.write_frames({("ssp245", 2035): f}, tmp_path)
    t0 = time.perf_counter()
    assert pw.get_frame("ssp245", 2035, tmp_path) == f
    assert time.perf_counter() - t0 < 0.2
