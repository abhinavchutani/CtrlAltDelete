"""Season-so-far for the daily Overview widgets (src/p_today.py, task #127)."""
from __future__ import annotations

import numpy as np
import pytest

from src import c_features as F
from src import p_today as T
from src import serve_db


# ── pure rules ──────────────────────────────────────────────────────
def test_percentile_mid_rank():
    assert T.percentile(5, np.arange(10)) == 55.0  # 5 below, 1 tie → (5 + 0.5) / 10
    assert T.percentile(0, np.zeros(30)) == 50.0  # all ties sit in the middle, not at an edge
    assert T.percentile(99, np.arange(30)) == 100.0
    assert T.percentile(1, np.array([])) == 50.0


def test_status_rule_edges():
    assert T.status_of(90, 0, flowering=True) == "risk"
    assert T.status_of(89, 0, flowering=True) == "watch"
    assert T.status_of(75, 0, flowering=True) == "watch"
    assert T.status_of(74, 10, flowering=True) == "ok"
    assert T.status_of(95, 0, flowering=False) == "watch"  # before flowering it can't be a bad year yet
    assert T.status_of(89, 0, flowering=False) == "ok"
    assert T.status_of(0, 92, flowering=True) == "risk"  # heat counts as much as dryness


def _row(status="ok", stage="sown", dry=50, heat=50, region="SE_SKANE", crop="pea"):
    return {"region": region, "crop": crop, "status": status, "stage": stage, "dryness_pct": dry, "heat_pct": heat}


def test_changes_diff():
    prev = [_row("watch", "flowering", 80, 48), _row(region="FI_SW")]
    cur = [_row("risk", "flowering", 82, 100), _row(region="FI_SW", stage="flowering")]
    ch = T.changes(prev, cur)
    assert [c["kind"] for c in ch] == ["escalated", "jump", "stage"]
    assert ch[0]["text"] == "Skåne pea: watch → bad year"
    assert ch[1]["text"] == "Skåne pea: heat 48th → 100th percentile"
    assert ch[2]["text"] == "SW Finland pea: now flowering"
    assert T.changes(cur, cur) == []


def test_stage_days_follow_degree_days():
    t = np.full((1, 60), 15.0)  # 10 degree-days a day from the first day the 5-day mean is known
    sow, sens, fill, mat = T.stage_days(t, F.Crop(6.0, 100, 200, 300))
    assert sow[0] == 4  # the 5-day rolling mean exists from day 4
    assert (sens[0], fill[0], mat[0]) == (13, 23, 33)  # cumulative GDD includes the sowing day


def test_ordinal():
    assert [T._ordinal(n) for n in (1, 2, 3, 4, 11, 12, 13, 21, 100)] == \
        ["1st", "2nd", "3rd", "4th", "11th", "12th", "13th", "21st", "100th"]


# ── on the pack ─────────────────────────────────────────────────────
needs_data = pytest.mark.skipif(not serve_db.exists(), reason="needs out/serve.duckdb (DATA_DIR pack)")


@pytest.fixture(scope="module")
def inp():
    return T.inputs("historical", 2026)


@needs_data
def test_season_end_matches_stage_features(inp):
    """On 31 Oct the season-so-far equals the yield model's own stage features (c_stage_features)."""
    _, now = inp.series("pea", "cells")
    with serve_db.connect() as con:
        ref = con.execute("""SELECT cell_id, soil, sow_doy, season_len, hot_sens + hot_fill AS hot
                             FROM c_stage_features WHERE crop = 'pea' AND scenario = 'historical' AND year = 2026""").df()
    k = now.keys.assign(sow_doy=now.sow + 91.0, season_len=np.minimum(now.mat, now.cpet.shape[1]) - now.sow,
                        hot=now.hot(now.cpet.shape[1] - 1))
    m = k.merge(ref, on=["cell_id", "soil"], suffixes=("", "_ref"))
    assert len(m) == len(k) > 50
    assert np.allclose(m.sow_doy, m.sow_doy_ref)
    assert np.allclose(m.season_len, m.season_len_ref)
    assert np.allclose(m.hot, m.hot_ref)


@needs_data
def test_no_peeking_past_today(inp):
    """Reading the season at day d equals running c_features on weather cut at d."""
    _, now = inp.series("pea", "cells")
    d = T.day_index(T.date(2026, 6, 16))
    cut = {k: v[:, : d + 1] for k, v in inp.now.arr.items()}
    rows = inp.now.keys.reset_index().merge(inp.cell_soil[["cell_id", "soil"]], on="cell_id")
    for soil in ("clay", "silt"):
        sel = rows[rows.soil == soil]
        if sel.empty:
            continue
        r = sel["index"].to_numpy()
        f = F.crop_features({k: v[r] for k, v in cut.items()}, F.CROPS["pea"], inp.now.aet[soil][r, : d + 1])
        mine = now.hot(d)[now.keys.reset_index().merge(sel[["cell_id"]], on="cell_id")["index"].to_numpy()]
        assert np.allclose(np.sort(mine), np.sort(f["hot_sens"] + f["hot_fill"]))


@needs_data
def test_day_shapes_and_edges():
    first = T.today("2026-04-01")
    assert first["changes"] == []  # no yesterday on the first day
    assert all(r["stage"] == "not_sown" and r["status"] == "ok" for r in first["all"])
    end = T.today("2026-10-31")
    assert {r["stage"] for r in end["regions"]} == {"harvest"}
    t = T.today("2026-06-16")
    assert t["path"] == "historical" and sum(t["counts"].values()) == len(T.pairs())
    for r in t["regions"]:
        assert len(r["dryness_normal"]) == 30 and 0 <= r["dryness_pct"] <= 100
        assert [s["name"] for s in r["stages"]] == list(T.STAGES)
    for f in t["farms"]:
        assert f["farms"] > 0 and f["p10"] <= f["p50"] <= f["p90"] and 0 <= f["share_ge_90"] <= 1
    with pytest.raises(ValueError):
        T.today("2025-06-16")  # before the outlook starts
    with pytest.raises(ValueError):
        T.today("2026-12-01")  # outside the season


@needs_data
def test_future_years_follow_the_climate_path():
    a, b = T.today("2030-06-20", "ssp126"), T.today("2030-06-20", "ssp585")
    assert a["path"] == "ssp126" and b["path"] == "ssp585"
    assert [r["dryness"] for r in a["regions"]] != [r["dryness"] for r in b["regions"]]
