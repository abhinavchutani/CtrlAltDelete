"""p_hedge frontier math and p_pathways rules on fake data (CI); contract checks on the snapshot (skip without it)."""
import numpy as np
import pandas as pd
import pytest

from src import p_alerts as A, p_hedge as H, p_pathways as W


def test_cvar_is_mean_of_worst_tenth():
    assert H.cvar(np.arange(30.0)) == pytest.approx((27 + 28 + 29) / 3)


def test_frontier_pooling_beats_one_region_and_marks_now_and_best():
    years = range(2041, 2061)
    fi = pd.Series([100.0 if y % 2 else 60.0 for y in years], index=list(years))      # anti-correlated regions
    se = pd.Series([60.0 if y % 2 else 100.0 for y in years], index=list(years))
    t = pd.DataFrame({"FI_SW": fi, "SE_SKANE": se})
    v = pd.Series({"FI_SW": 80.0, "SE_SKANE": 80.0})
    f = H.mark(H.frontier(t, v, pd.Series({"FI_SW": 100.0, "SE_SKANE": 100.0})), now=0.3)
    half = f[f.fi_share == 0.5].iloc[0]
    assert half.expected == pytest.approx(0.0) and f[f.fi_share == 0.0].iloc[0].expected > 0   # 50/50 hedges fully
    assert f[f.is_best].fi_share.iloc[0] == 0.5 and f[f.is_now].fi_share.iloc[0] == 0.3
    assert "Moving 20 pp of pea volume to FI_SW" in H.why(f)


def test_pathway_threshold_window_and_decide_by():
    assert (A.TIP_ODDS, A.TIP_WINDOW) == (0.25, 10) and W.threshold_text() == "bad-year odds > 1 in 4"
    years = list(range(2026, 2045))
    bad = {2034, 2036, 2038}
    cube = pd.DataFrame({"region": "SE_SKANE", "crop": "pea", "year": years, "bad_year": [y in bad for y in years],
                         "eur_loss": [300_000.0 if y in bad else 0.0 for y in years],
                         "driver": ["st_hot_sens" if y in bad else None for y in years]})
    items = {i["option_id"]: i for i in W.items(cube, "ssp585", levels={"SE_SKANE": {"drought": 0.7, "hot": 2.2}})}
    assert set(items) == {"A04", "A06", "A07"}                                # H2 options for pea
    assert items["A04"]["tipping_year"] == 2038 and items["A04"]["decide_by"] == 2038 - 12
    assert items["A04"]["simulated"] == "assumption" and "more than 3 hot days" in items["A04"]["signpost"]


def test_no_tipping_means_no_decide_by_and_indicative_flag():
    cube = pd.DataFrame({"region": "FI_SW", "crop": "pea", "year": range(2026, 2041), "bad_year": False,
                         "eur_loss": 10.0, "driver": "st_drought_sens"})
    it = W.items(cube, "ssp245", ensemble_odds={("FI_SW", "pea"): 0.3})
    assert it and all(i["tipping_year"] is None and i["decide_by"] is None for i in it)
    assert all("indicative" in i["threshold"] for i in it)


@pytest.fixture(scope="module")
def warm():
    from src import p_engine as P
    if not P.serve_db_path().exists() or not (W.V2 / "cube" / "current_plan_ssp585.parquet").exists():
        pytest.skip("needs out/serve.duckdb and the presets (python -m src.p_presets)")
    return P.warm()


def test_api_shapes_validate(warm):
    from api import schemas
    h = schemas.Hedge.model_validate(H.hedge("ssp245"))
    assert sum(p.is_now for p in h.points) == 1 and sum(p.is_best for p in h.points) == 1 and len(h.points) == 21
    items = [schemas.PathwayItem.model_validate(i) for i in W.pathways("current_plan_ssp585")]
    assert {(i.crop, i.region) for i in items} >= {("pea", "SE_SKANE"), ("pea", "FI_SW")}
