"""p_alerts / p_compare rules on a fake cube (CI), plus the ssp585 preset on the snapshot (skips without it)."""
import re

import pandas as pd
import pytest

from src import p_alerts as A, p_compare as PC


def test_thresholds_are_pinned():
    assert (A.CRIT_EUR, A.NOTABLE_EUR, A.CRIT_SUPPLY, A.TIP_ODDS, A.TIP_WINDOW, A.PER_YEAR, A.MAX_ALERTS) == \
        (250_000.0, 100_000.0, 0.70, 0.25, 10, 2, 12)


def cube(rows):
    d = pd.DataFrame(rows, columns=["region", "crop", "year", "t", "contracted_t", "eur_loss", "bad_year", "driver", "driver_pct"])
    d["change_pct"] = 100 * (d.t / d.contracted_t - 1)
    d["eur_band"] = "€250k–1M"
    d["import_tco2e"] = 0.0
    return d


def test_rules_severity_hazard_and_skip_without_driver():
    c = cube([("SE_SKANE", "pea", 2030, 9000, 10000, 300_000, False, "st_drought_sens", -12.0),   # € → critical, H1
              ("FI_SW", "pea", 2031, 6500, 10000, 50_000, True, "st_hot_sens", -20.0),            # < 70 % → critical, H2
              ("FI_SW", "potato", 2032, 9500, 10000, 120_000, False, "st_blight_days", -4.0),     # notable, H6
              ("FI_SW", "carrot", 2033, 9900, 10000, 10_000, False, "st_drought_sens", -1.0),     # below notable → dropped
              ("FI_SW", "spinach", 2034, 7000, 10000, 200_000, True, None, 0.0)])                 # no stress driver → dropped
    out = A.alerts("t", {"climate": "ssp245"}, c)
    got = {(a["region"], a["crop"]): (a["severity"], a["hazard"], a["kind"]) for a in out}
    assert got == {("SE_SKANE", "pea"): ("critical", "H1", "drought_flowering"),
                   ("FI_SW", "pea"): ("critical", "H2", "heat_flowering"),
                   ("FI_SW", "potato"): ("notable", "H6", "blight_weather")}
    a = next(x for x in out if x["crop"] == "pea" and x["region"] == "SE_SKANE")
    assert "will" not in a["why"] and a["why"].startswith("On this weather path")
    for n in re.findall(r"[-+]?\d[\d,]*", a["why"]):                     # every number comes from the cube
        assert float(n.replace(",", "")) in {9000.0, 2030.0, -10.0, 10000.0, -12.0, 1991.0, 2020.0}, n


def test_cap_per_year_and_total():
    rows = [("SE_SKANE", "pea", 2030 + i // 3, 5000, 10000, 400_000 + i, True, "st_drought_sens", -30.0) for i in range(40)]
    for i, r in enumerate(rows):                                          # distinct cells
        rows[i] = (r[0], f"pea{i}", *r[2:])
    out = A.alerts("t", {"climate": "ssp585"}, cube(rows))
    assert len(out) == A.MAX_ALERTS
    assert max(pd.Series([a["year"] for a in out]).value_counts()) <= A.PER_YEAR


def test_tipping_marker_needs_three_bad_years_in_ten():
    rows = [("FI_SW", "pea", y, 7500 if y in (2031, 2034, 2038) else 10000, 10000, 0.0, y in (2031, 2034, 2038),
             "st_hot_sens", -25.0) for y in range(2026, 2041)]
    tip = A.tipping_years(cube(rows))
    assert tip.to_dict("records") == [{"region": "FI_SW", "crop": "pea", "year": 2038, "bad_years": 3}]


def test_better_option_needs_a_real_gain():
    base = cube([("SE_SKANE", "pea", 2030, 9000, 10000, 300_000, False, "st_drought_sens", -12.0)])
    grid = {cid: base.assign(eur_loss=290_000.0) for cid in PC.GRID}      # only 3 % better → no card
    assert PC.better({"climate": "ssp245", "horizon_end": 2040}, base, grid) is None
    grid["split_70_30"] = base.assign(eur_loss=100_000.0)
    b = PC.better({"climate": "ssp245", "horizon_end": 2040}, base, grid)
    assert b["spec"]["levers"] == PC.GRID["split_70_30"] and b["saves"] == "€100–250k"


@pytest.fixture(scope="module")
def ctx():
    from src import p_engine as P
    if not P.serve_db_path().exists():
        pytest.skip("out/serve.duckdb missing")
    return P.warm()


def test_ssp585_preset_alerts_validate_against_the_contract(ctx):
    from api import schemas
    from src import p_engine as P
    sim, _ = P.run_sim(ctx, {"climate": "ssp585", "horizon_end": 2060, "levers": []}, sid="current_plan_ssp585",
                       grid=P.grid_for(ctx, "ssp585", 2060))
    schemas.SimResult.model_validate(sim)
    assert 4 <= len(sim["alerts"]) <= 12 and any(a["severity"] == "critical" for a in sim["alerts"])
    assert all(a["hazard"] in {"H1", "H2", "H3", "H4", "H5", "H6", "H7"} for a in sim["alerts"])
