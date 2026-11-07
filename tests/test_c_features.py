"""Tests for src/c_features.py. Logic tests run everywhere; the data test skips without the pack."""
import numpy as np
import pytest

from src import c_features as F
from src import load


def _arr(t, p, pet, n_days=214):
    t = np.full((1, n_days), t, float) if np.isscalar(t) else np.asarray(t, float)[None, :]
    mon = np.repeat(np.arange(4, 11), 31)[:n_days][None, :].astype(float)
    return {"tmean_c": t, "tmax_c": t + 6, "precip_mm": np.full_like(t, p), "pet_mm": np.full_like(t, pet), "month": mon}


def test_bucket_stays_in_bounds_and_aet_le_pet():
    rng = np.random.default_rng(1)
    p, pet = rng.gamma(0.6, 4, (50, 214)), rng.uniform(0, 6, (50, 214))
    aet = F.soil_water(p, pet, 90.0)
    assert (aet <= pet + 1e-12).all() and (aet >= 0).all()


def test_dry_season_drives_drought_up():
    crop = F.CROPS["pea"]
    wet, dry = _arr(15.0, 5.0, 3.0), _arr(15.0, 0.0, 5.0)
    fw = F.crop_features(wet, crop, F.soil_water(wet["precip_mm"], wet["pet_mm"], 130.0))
    fd = F.crop_features(dry, crop, F.soil_water(dry["precip_mm"], dry["pet_mm"], 130.0))
    assert fd["drought_sens"][0] > 0.5 > fw["drought_sens"][0]


def test_sowing_waits_for_threshold_and_stages_order():
    t = np.r_[np.full(30, 3.0), np.full(184, 14.0)]
    a = _arr(t, 2.0, 2.0)
    f = F.crop_features(a, F.CROPS["pea"], F.soil_water(a["precip_mm"], a["pet_mm"], 130.0))
    assert 30 <= f["sow_doy"][0] - 91 <= 35            # first 5-day window ≥ 6 °C
    assert f["immature"][0] == 0 and f["season_len"][0] == pytest.approx(900 / 9, abs=2)


def test_cold_year_is_immature():
    a = _arr(7.0, 2.0, 2.0)
    f = F.crop_features(a, F.CROPS["potato"], F.soil_water(a["precip_mm"], a["pet_mm"], 130.0))
    assert f["immature"][0] == 1 and f["gdd_deficit"][0] > 0


def test_feature_table_covers_all_scenarios(tmp_path):
    if not (load.pack_dir() / "data").is_dir():
        pytest.skip("data pack not available (set DATA_DIR)")
    con = load.connect(tmp_path / "t.duckdb")
    load.load_all(con)
    df = F.build(con)
    assert set(df.scenario) == {"historical", "ssp126", "ssp245", "ssp585"}
    assert df.year.min() == 1991 and df.year.max() == 2060 and df.cell_id.nunique() == 84
    assert len(df) == 84 * (36 + 3 * 34) * len(F.CROPS) * len(F.BUCKET_MM)
    assert df.drop(columns=["cell_id", "scenario", "crop", "soil"]).notna().all().all()
