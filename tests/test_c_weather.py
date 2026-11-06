"""Tests for src/c_weather.py. Geometry tests run everywhere; data tests skip without the pack."""
import numpy as np
import pandas as pd
import pytest

from src import c_weather as cw
from src import load


def test_haversine_known_distance():
    # Helsinki → Turku is ~150 km
    d = cw.haversine_km(np.array([60.1699]), np.array([24.9384]), np.array([60.4518]), np.array([22.2666]))
    assert 145 < d[0] < 155


def test_nearest_cells_picks_closest():
    parcels = pd.DataFrame({"parcel_id": ["p1", "p2"], "farm_id": ["f", "f"], "lat": [60.0, 55.5], "lon": [22.0, 13.0]})
    cells = pd.DataFrame({"cell_id": ["FI", "SE"], "region": ["FI_SW", "SE_SKANE"], "lat": [60.1, 55.6], "lon": [22.1, 13.1]})
    out = cw.nearest_cells(parcels, cells)
    assert out.cell_id.tolist() == ["FI", "SE"] and out.region.tolist() == ["FI_SW", "SE_SKANE"]
    assert (out.distance_km < 20).all()


def test_weather_rejects_unknown_inputs():
    with pytest.raises(ValueError):
        cw.weather(None, scenario="ssp999")
    with pytest.raises(ValueError):
        cw.weather(None, columns=["not_a_column"])


@pytest.fixture(scope="module")
def con(tmp_path_factory):
    if not (load.pack_dir() / "data").is_dir():
        pytest.skip("data pack not available (set DATA_DIR)")
    c = load.connect(tmp_path_factory.mktemp("db") / "t.duckdb")
    load.load_all(c)
    cw.build_parcel_cell(c)
    return c


def test_every_parcel_linked_close_to_a_cell(con):
    n_parcels = con.execute("SELECT count(*) FROM raw_parcels").fetchall()[0][0]
    stats = con.execute("SELECT count(*), max(distance_km) FROM c_parcel_cell").fetchall()[0]
    assert stats[0] == n_parcels == 14213
    assert stats[1] < 25  # 0.25° cells: nearest centre is always within ~20 km


def test_weather_filters(con):
    cell = con.execute("SELECT cell_id FROM c_parcel_cell LIMIT 1").fetchall()[0][0]
    w = cw.weather(con, cells=[cell], scenario="historical", start="2026-06-01", end="2026-06-30")
    assert len(w) == 30 and set(w.scenario) == {"historical"}
    fut = cw.weather(con, cells=[cell], scenario="ssp245", start="2027-01-01", end="2027-12-31", columns=["tmax_c"])
    assert len(fut) == 365 and list(fut.columns) == ["cell_id", "scenario", "date", "tmax_c"]
