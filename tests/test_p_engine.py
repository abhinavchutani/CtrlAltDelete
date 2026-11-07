"""p_engine on the frozen snapshot (skips without out/serve.duckdb, as in CI)."""
import pytest

from src import p_engine as P


@pytest.fixture(scope="module")
def ctx():
    if not P.serve_db_path().exists():
        pytest.skip("out/serve.duckdb missing (run make snapshot)")
    return P.load_context()


def test_current_plan_is_a_valid_simresult_and_shows_the_2026_split(ctx):
    sim, cube = P.simulate(ctx, {"climate": "ssp245", "horizon_end": 2031, "levers": []}, sid="current_plan_ssp245")
    assert sim["years"] == list(range(2026, 2032)) and sim["synthetic"] is True
    assert {"eur_at_risk_per_year", "vs_current_plan", "co2e_direction", "confidence", "confidence_why"} <= set(sim["meters"])
    r = cube["regions"].set_index(["region", "crop", "year"])
    assert r.loc[("FI_SW", "pea", 2026), "change_pct"] > 10          # strong Finnish peas in 2026
    assert r.loc[("SE_SKANE", "pea", 2026), "change_pct"] < 0        # drought-hit Swedish peas
    assert r.loc[("SE_SKANE", "pea", 2026), "eur_loss"] > r.loc[("FI_SW", "pea", 2026), "eur_loss"]
    assert all(isinstance(x["eur_at_risk"], str) for x in sim["regions"])   # € leaves only as bands


def test_region_split_keeps_total_contracted_pea_volume(ctx):
    _, cube = P.simulate(ctx, {"climate": "ssp245", "horizon_end": 2031,
                               "levers": [{"type": "region_split", "fi_share": 0.7}]})
    r = cube["regions"]
    pea = r[(r.crop == "pea") & (r.year == 2027)].set_index("region").contracted_t
    total = ctx.base_rc[ctx.base_rc.crop == "pea"].contracted_t.sum()
    assert abs(pea.sum() - total) < 1e-6 * total and abs(pea["FI_SW"] / pea.sum() - 0.7) < 1e-9


def test_heat_tolerant_variety_lowers_low_confidence(ctx):
    sim, _ = P.simulate(ctx, {"climate": "ssp585", "horizon_end": 2031, "levers": [{"type": "heat_tolerant_variety"}]})
    assert sim["meters"]["confidence"] == "low" and any("assumption" in w for w in sim["meters"]["confidence_why"])
