"""SBTi targets + pathway (#130): target arithmetic, lever classes, monotone pathway, base-year guardrails."""
import pytest

from src import b_sbti as B
from src import e_resolve
from src import lineage as L
from src.db import connect
from src.load import pack_dir

needs_pack = pytest.mark.skipif(not (pack_dir() / "data/05_scenarios/decarbonisation_levers.csv").is_file(),
                                reason="DATA_DIR pack missing")
BASE = {"scope1_total": 4400.0, "scope2_market_total": 60.0, "scope3_total": 220000.0}
FLAG = 150000.0


@pytest.fixture
def con(tmp_path):
    c = connect(tmp_path / "b.duckdb")
    L.init_schema(c)
    for cat, v in BASE.items():
        L.write_result(c, f"A2:2025:actual:total:{cat}", metric="tco2e", value=v, unit="t CO2e", scope="total",
                       category=cat, year=2025, method="fixture", produced_by="test", lineage=[L.src("doc", "x")])
    L.write_result(c, "A2:2025:actual:flag:flag_total", metric="tco2e", value=FLAG, unit="t CO2e", scope="flag",
                   category="flag_total", year=2025, method="fixture", produced_by="test", lineage=[L.src("doc", "x")])
    return c


def test_linear_target_formula():
    assert B.linear_target(1000.0, 4.2, 2025, 2030) == pytest.approx(790.0)
    assert B.linear_target(1000.0, 3.03, 2025, 2032) == pytest.approx(1000 * (1 - 0.0303 * 7))


@needs_pack
def test_target_matches_copilot_rule(con):
    q = ("illustrative: with 2025 as base year and the sbti minimum 4.2 %/yr linear rate for scope 1+2 "
         "(market-based), what is a 2030 target?")
    r = e_resolve.linear_target(con, q, 2025)
    t = B.targets(B.base_year(con), 2030)["by_bucket"]["s12"]["target_t"]
    assert r is not None and r.value == pytest.approx(t, abs=1e-3)


def test_base_year_buckets(con):
    b = B.base_year(con)
    assert b["by_bucket"] == {"s12": 4460.0, "s3": 70000.0, "flag": FLAG}  # FLAG sits inside Scope 3
    assert b["flag_share_pct"] == pytest.approx(100 * FLAG / (4460 + 220000))
    assert B.targets(b)["flag_target_required"]


def test_base_year_missing_raises(tmp_path):
    c = connect(tmp_path / "e.duckdb")
    L.init_schema(c)
    with pytest.raises(LookupError):
        B.base_year(c)


def test_ramp():
    lv = {"start": 2027, "ramp_years": 4}
    assert [B.ramp(lv, y) for y in (2026, 2027, 2028, 2030, 2035)] == [0.0, 0.25, 0.5, 1.0, 1.0]


@needs_pack
def test_lever_classes():
    by = {lv["id"]: lv for lv in B.levers()}
    assert by["L27"]["class"] == "measurement" and by["L27"]["abatement_t_design"] == 0
    assert by["L05"]["class"] == "structural" and by["L26"]["class"] == "structural"
    assert by["L10"]["class"] == "removal"
    assert by["L01"]["bucket"] == "s12" and by["L11"]["bucket"] == "flag" and by["L20"]["bucket"] == "s3"
    red = [lv["eur_per_t"] for lv in B.levers() if lv["class"] == "reduction"]
    assert red == sorted(red)  # MACC order


@needs_pack
def test_non_reductions_change_nothing(con):
    base = B.pathway(con, lever_ids=[])
    p = B.pathway(con, lever_ids=["L27", "L05", "L26", "L10"])
    assert p["counted_lever_ids"] == [] and set(p["ignored_lever_ids"]) == {"L27", "L05", "L26", "L10"}
    assert p["gap"]["total"]["gap_t"] == pytest.approx(base["gap"]["total"]["gap_t"])


@needs_pack
def test_more_levers_never_raise_emissions(con):
    ids = [lv["id"] for lv in B.levers() if lv["class"] == "reduction"]
    prev = None
    for k in range(0, len(ids) + 1, 4):
        end = next(r for r in B.pathway(con, lever_ids=ids[:k])["years"] if r["year"] == 2030)
        assert end["with_levers_t"] <= end["bau_t"] + 1e-6
        if prev is not None:
            assert end["with_levers_t"] <= prev + 1e-6
        prev = end["with_levers_t"]


@needs_pack
def test_pathway_shape_and_validation(con):
    p = B.pathway(con, scenario="net_zero_2050", target_year=2032)
    assert [r["year"] for r in p["years"]] == list(range(2025, 2036))
    assert p["years"][0]["bau_t"] == pytest.approx(4460 + 70000 + FLAG)
    assert p["years"][-1]["target_t"] is None and p["synthetic"]
    assert any(w["id"].startswith("event:2025-11") for w in p["warnings"])  # Foodhills recalculation
    with pytest.raises(ValueError):
        B.pathway(con, target_year=2045)
    with pytest.raises(ValueError):
        B.pathway(con, lever_ids=["L99"])


def _client(monkeypatch, mock: str):
    from fastapi.testclient import TestClient
    monkeypatch.setenv("API_MOCK", mock)
    monkeypatch.setenv("API_WARM", "0")
    from api.main import app
    return TestClient(app)


def test_api_mock_serves_fixture(monkeypatch):
    r = _client(monkeypatch, "1").post("/api/sbti/pathway", json={})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["synthetic"] and d["targets"]["base_year"] == 2025 and {lv["class"] for lv in d["levers"]} >= {"measurement"}


@needs_pack
def test_api_real(monkeypatch):
    from src import serve_db
    if not serve_db.exists():
        pytest.skip("out/serve.duckdb missing (make snapshot)")
    c = _client(monkeypatch, "0")
    d = c.post("/api/sbti/pathway", json={"levers": ["L11", "L27"], "target_year": 2032}).json()
    assert d["counted_lever_ids"] == ["L11"] and d["ignored_lever_ids"] == ["L27"]
    assert c.post("/api/sbti/pathway", json={"levers": ["L99"]}).status_code == 422
    assert c.post("/api/sbti/pathway", json={"target_year": 2045}).status_code == 422
