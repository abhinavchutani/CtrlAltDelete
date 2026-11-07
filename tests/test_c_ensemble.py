"""Tests for src/c_ensemble.py. Logic tests run everywhere; the data test skips without the pack."""
import pandas as pd
import pytest

from src import c_ensemble as E
from src import load


def _prod(vals, region="FI_SW", crop="pea"):
    return pd.DataFrame({"region": region, "crop": crop, "year": range(len(vals)), "t": vals})


def test_risk_change_and_bad_years():
    base = _prod([100.0] * 10)
    fut = _prod([90.0] * 8 + [70.0, 75.0])        # two years below 80 % of the baseline mean
    r = E.risk(base, fut).iloc[0]
    assert r.mean_yield_change_pct == pytest.approx(100 * (865 / 1000 - 1))
    assert r.p_bad_year == pytest.approx(0.2)


def test_baseline_against_itself_has_zero_change():
    base = _prod([100.0, 120.0, 60.0, 110.0])
    r = E.risk(base, base).iloc[0]
    assert r.mean_yield_change_pct == pytest.approx(0.0) and r.p_bad_year == pytest.approx(0.25)


def test_delta_weather_applies_signals(tmp_path):
    if not (load.pack_dir() / "data").is_dir():
        pytest.skip("data pack not available (set DATA_DIR)")
    con = load.connect(tmp_path / "t.duckdb")
    load.load_all(con)
    E.make_delta_weather(con)
    got = con.execute("""
        SELECT d.scenario, avg(d.tmean_c - b.tmean_c) AS dt, sum(d.precip_mm) / sum(b.precip_mm) AS pf
        FROM c_weather_delta d JOIN c_weather_delta b USING (cell_id, date)
        WHERE b.scenario = 'baseline' AND d.scenario = 'delta_ssp585' AND month(d.date) = 7 GROUP BY 1""").fetchone()
    exp = con.execute("SELECT delta_tmean_c, precip_factor FROM raw_climate_change_signals "
                      "WHERE scenario = 'ssp585' AND month = 7").fetchone()
    assert got[1] == pytest.approx(exp[0], abs=1e-6) and got[2] == pytest.approx(exp[1], rel=1e-6)
