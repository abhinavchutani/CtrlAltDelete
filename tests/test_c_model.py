"""Tests for src/c_model.py. Logic tests run everywhere; data tests skip without the pack."""
import numpy as np
import pandas as pd
import pytest

from src import c_model as M
from src import load


def test_production_mape_is_area_weighted():
    df = pd.DataFrame({"region": ["R", "R"], "crop": ["pea", "pea"], "year": [2024, 2024],
                       "area_ha": [10.0, 30.0], "yield_t_ha": [3.0, 3.0], "pred": [3.0, 4.0]})
    out = M.production_mape(df, "pred")
    assert out["ape_pct"].iloc[0] == pytest.approx(100 * 30 / 120)


def test_nrmse_averages_over_crops():
    df = pd.DataFrame({"crop": ["a", "a", "b", "b"], "yield_t_ha": [1.0, 1.0, 50.0, 50.0],
                       "pred": [1.1, 0.9, 50.0, 50.0]})
    assert M.nrmse(df, "pred") == pytest.approx(0.05)


def _toy(n_farms=12, years=range(2012, 2024), seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    for f in range(n_farms):
        skill = rng.normal(0, 0.1)
        for y in years:
            row = {"farm_id": f"F{f}", "crop": "pea", "region": "FI_SW", "year": y, "area_ha": 10.0}
            for v in (*M.WVARS, "wb_mm"):
                for m in M.MONTHS:
                    row[f"{v}_m{m}"] = rng.normal()
            row.update(clay_pct=30.0, slope_pct=2.0, drain_subsurface=1.0, irrigated=0.0, n_kg_ha=30.0,
                       sprays=1.0, organic=0.0, **{f"soil_{s}": float(s == "clay") for s in M.SOILS})
            row["yield_t_ha"] = float(np.exp(1.1 + skill + 0.2 * row["wb_mm_m6"] + rng.normal(0, 0.02)))
            rows.append(row)
    df = pd.DataFrame(rows)
    df["clay_x_precip_m5"] = df["clay_pct"] * df["precip_mm_m5"]
    for m in (6, 7):
        df[f"irr_x_wb_m{m}"] = df["irrigated"] * df[f"wb_mm_m{m}"]
    df["is_se"] = 0.0
    return M.add_seasons(df)


def test_fit_is_deterministic_and_learns_farm_skill():
    df = _toy()
    a, b = M.fit_crop(df, "pea"), M.fit_crop(df, "pea")
    assert np.array_equal(a.predict(df), b.predict(df))
    err = np.abs(a.predict(df) - df["yield_t_ha"]) / df["yield_t_ha"]
    base = np.abs(df["yield_t_ha"].mean() - df["yield_t_ha"]) / df["yield_t_ha"]
    assert err.mean() < base.mean()


def test_outlier_flag_is_symmetric():
    lab = pd.DataFrame({"crop": ["pea"] * 5, "region": ["FI_SW"] * 5, "yield_t_ha": [3.0, 3.1, 2.9, 31.0, 0.3]})
    med = lab.groupby(["crop", "region"])["yield_t_ha"].transform("median")
    flag = (lab["yield_t_ha"] > M.OUTLIER_FACTOR * med) | (lab["yield_t_ha"] < med / M.OUTLIER_FACTOR)
    assert flag.tolist() == [False, False, False, True, True]


@pytest.fixture(scope="module")
def con(tmp_path_factory):
    if not (load.pack_dir() / "data").is_dir():
        pytest.skip("data pack not available (set DATA_DIR)")
    from src import c_weather
    c = load.connect(tmp_path_factory.mktemp("db") / "t.duckdb")
    load.load_all(c)
    c_weather.build_parcel_cell(c)
    return c


def test_c1_features_cover_template(con):
    static, wx, lab = M.parcel_static(con), M.cell_year_weather(con), M.labels(con)
    med = lab.groupby(["crop", "region"])[["irrigated", "n_kg_ha", "sprays"]].median().reset_index()
    X = M.c1_features(con, static, wx, lab, M.organic_farms(con), med)
    assert len(X) == 12064
    assert X[M.weather_cols(X)].notna().all().all()


def test_survey_table_prefers_clean(tmp_path):
    import duckdb
    c = duckdb.connect(str(tmp_path / "s.duckdb"))
    assert M.survey_table(c) == "raw_farm_survey_fi"
    c.execute("CREATE TABLE clean_farm_survey (x INT)")
    assert M.survey_table(c) == "clean_farm_survey"


def test_feature_effects_and_drivers_cover_features():
    df = _toy()
    m = M.fit_crop(df, "pea")
    eff = M.feature_effects({"pea": m})
    assert set(eff["feature"]) == set(m.features)
    assert eff.loc[eff.feature == "wb_mm_sja", "effect_pct_per_unit"].notna().all()
    drv = M.year_drivers(m, df[df.year < 2020], df[df.year >= 2020], "pea", "FI_SW", 2021)
    assert 0 < len(drv) <= 6 and all("contribution_pct" in d for d in drv)


def test_ensemble_is_deterministic():
    df = _toy()
    assert np.array_equal(M.fit_crop(df, "pea").predict(df), M.fit_crop(df, "pea").predict(df))
