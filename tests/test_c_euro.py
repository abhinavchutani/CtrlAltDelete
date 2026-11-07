"""Tests for src/c_euro.py (logic only; the full run is covered by `make c`)."""
import pandas as pd
import pytest

from src import c_euro as C


def _prod(region, vals, crop="pea"):
    return pd.DataFrame({"region": region, "crop": crop, "year": range(len(vals)), "t": vals})


PR = pd.DataFrame({"region": ["FI_SW", "SE_SKANE"], "crop": ["pea", "pea"], "price": [400.0, 400.0],
                   "premium": [0.5, 0.5]})


def test_loss_is_shortfall_times_price_times_premium():
    base = _prod("FI_SW", [100.0, 100.0])
    loss = C.losses(base, _prod("FI_SW", [80.0, 110.0]), PR)
    assert loss["shortfall_t"].tolist() == [20.0, 0.0]
    assert loss["eur_loss"].tolist() == [20 * 400 * 0.5, 0.0]


def test_pooling_two_anticorrelated_regions_removes_the_loss():
    base = pd.concat([_prod("FI_SW", [100.0, 100.0]), _prod("SE_SKANE", [100.0, 100.0])])
    prod = pd.concat([_prod("FI_SW", [120.0, 80.0]), _prod("SE_SKANE", [80.0, 120.0])])
    loss = C.losses(base, prod, PR)
    separate = loss.groupby("year")["eur_loss"].sum().mean()
    assert separate == pytest.approx(20 * 400 * 0.5)
    assert C.pooled_pea_loss(loss).mean() == pytest.approx(0.0)


def test_earlier_sowing_lowers_every_threshold():
    crops = C.earlier_sowing_crops()
    assert all(crops[k].sow_t == pytest.approx(v.sow_t - C.SOWING_SHIFT_C) for k, v in C.c_features.CROPS.items())


def test_irrigation_override_only_touches_listed_parcels():
    X = pd.DataFrame({"parcel_id": ["a", "b"], "irrigated": [0.0, 0.0]})
    assert C.with_irrigation({"a"})(X)["irrigated"].tolist() == [1.0, 0.0]


def test_robust_rebalance_prefers_share_good_in_every_scenario():
    import numpy as np
    shares = np.array([0.0, 0.5, 1.0])
    curves = {"a": {"fi_share_now_pct": 50.0, "_curve": (shares, np.array([90.0, 100.0, 50.0]), 1)},
              "b": {"fi_share_now_pct": 50.0, "_curve": (shares, np.array([95.0, 100.0, 200.0]), 1)}}
    r = C.robust_rebalance(curves)           # share 1.0 wins in 'a' but loses badly in 'b'
    assert r["fi_share_opt_pct"] == 0.0 and r["rebalance_pp"] == -50.0 and r["min_gain_pct"] == 5.0
