"""Tests for src/c_deliveries.py (logic only)."""
import pandas as pd
import pytest

from src import c_deliveries as D


def _rows():
    return pd.DataFrame({"farm_id": ["a", "b", "a", "c"], "year": [2025, 2025, 2026, 2026],
                         "record_key": ["k1", "k2", "k3", "k4"], "t": [100.0, 50.0, 130.0, 500.0]})


def test_matched_uses_only_farms_in_both_years():
    r = D.change(_rows(), 2026, matched=True)
    assert r["pct"] == pytest.approx(30.0) and r["n_farms"] == 1
    assert r["raw_pct"] == pytest.approx(100 * (630 / 150 - 1))


def test_unmatched_is_total_change_with_all_keys():
    r = D.change(_rows(), 2026, matched=False)
    assert r["pct"] == pytest.approx(100 * (630 / 150 - 1))
    assert r["keys"] == ["k1", "k2", "k3", "k4"]
