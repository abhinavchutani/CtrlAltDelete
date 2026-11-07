"""D1 catchment loads: formula unit tests in CI; the full run skips without the pack."""
import numpy as np
import pandas as pd

from src import d_nature as D


def test_priority_formula_matches_pack():
    d = pd.DataFrame({"P": [100.0, 200.0, 300.0], "N": [1000.0, 1000.0, 4000.0],
                      "ecological_status_class": ["good", "bad", "moderate"], "p_sensitivity": [1.6, 1.0, 1.0]})
    out = D.priority(d)
    # medians P 200, N 1000 → (0.5+0.5)·1.0·1.6 = 1.6; (1+0.5)·1.8 = 2.7; (1.5+2)·1.2 = 4.2
    assert np.allclose(out.priority, [1.6, 2.7, 4.2]) and out.priority_rank.tolist() == [3, 2, 1]


def test_calibration_recovers_scale_and_loo_is_zero_for_exact_shape():
    idx = pd.DataFrame({"p_idx": [1.0, 2.0, 4.0], "n_idx": [10.0, 20.0, 40.0]}, index=["A", "B", "C"])
    dev = pd.DataFrame({"catchment_id": ["A", "B", "C"], "apetit_p_to_water_kg": [3.0, 6.0, 12.0],
                        "apetit_n_to_water_kg": [70.0, 140.0, 280.0]})
    sp, sn, loo = D.calibrate(idx, dev)
    assert round(sp, 6) == 3.0 and round(sn, 6) == 7.0 and loo == {"p": 0.0, "n": 0.0}


def test_index_falls_with_distance_and_rises_with_soil_p():
    base = dict(area_ha=1.0, slope_pct=2.0, catch_crop=False, drainage="open_ditch", n_surplus=0.0,
                winter_surplus_mm=200.0, retention=0.2)
    p = pd.DataFrame([{**base, "p_test": 10.0, "dist_to_water_m": 100.0},
                      {**base, "p_test": 10.0, "dist_to_water_m": 600.0},
                      {**base, "p_test": 40.0, "dist_to_water_m": 100.0}])
    i = D.parcel_index(p)
    assert i.p_idx[0] > i.p_idx[1] and i.p_idx[2] > i.p_idx[0] and i.n_idx[0] > i.n_idx[1]
