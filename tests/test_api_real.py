"""Real mode (API_MOCK=0): the adapters over src/p_* (task #95). Unit tests run in CI; the end-to-end ones
need `make v2` output (out/v2/) and skip without it."""
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from api import geo
from api import prediction as P
from api import schemas as S

HAVE_V2 = (P.V2 / "scenarios" / "index.json").exists() and (P.V2 / "weather").exists()


@pytest.fixture()
def real(monkeypatch):
    monkeypatch.setenv("API_MOCK", "0")
    monkeypatch.setenv("API_WARM", "0")
    from api.main import app
    return TestClient(app)


def test_simplify_keeps_three_props_and_rounds():
    g = {"features": [{"geometry": {"type": "Polygon", "coordinates": [[[22.1234567, 60.9876543], [22.2, 60.1]]]},
                       "properties": {"parcel_id": "P1", "farm_id": "F1", "area_ha": 2.5, "soil": "clay"}}]}
    f = geo.simplify(g)["features"][0]
    assert f["properties"] == {"parcel_id": "P1", "farm_id": "F1", "area_ha": 2.5}
    assert f["geometry"]["coordinates"][0][0] == [22.12346, 60.98765]


def test_simulate_before_warm_is_503(monkeypatch):
    monkeypatch.setitem(P._state, "ctx", None)
    with pytest.raises(HTTPException) as e:
        P.simulate(S.ScenarioSpec())
    assert e.value.status_code == 503


def test_ids_cannot_escape_out_v2():
    assert P.scenario("../../etc/passwd") is None
    with pytest.raises(HTTPException):
        P.farms("../x", 2030)


def test_hedge_and_pathways_wait_for_the_warm_model(real, monkeypatch):
    monkeypatch.setitem(P._state, "ctx", None)
    assert real.get("/api/hedge?climate=ssp245").status_code == 503  # real mode never falls back to fixtures
    assert real.get("/api/pathways/current_plan_ssp585").status_code == 503


@pytest.mark.skipif(not HAVE_V2, reason="needs `make v2` output in out/v2/")
def test_real_presets_weather_farms(real):
    ids = [p["scenario_id"] for p in real.get("/api/scenarios").json()]
    assert "current_plan_ssp245" in ids and len(ids) == 6
    sim = S.SimResult(**real.get("/api/scenario/current_plan_ssp245").json())
    assert sim.synthetic and sim.years[0] == 2026
    assert real.get("/api/scenario/nope").status_code == 404
    w = S.WeatherFrame(**real.get("/api/weather?climate=ssp585&year=2026").json())
    assert w.climate == "historical" and len(w.cells) == 84  # SSP paths start in 2027
    farms = real.get("/api/cube/current_plan_ssp245/farms?year=2030").json()
    assert farms and all(f["year"] == 2030 for f in farms)
    assert real.get("/api/health").json()["mock"] is False


@pytest.mark.skipif(not HAVE_V2, reason="needs `make v2` output and the snapshot")
def test_real_simulate_end_to_end(monkeypatch):
    """Warm the engine, run a custom spec, then read its farm cube from memory."""
    P.warm()
    if P.context_error():
        pytest.skip(P.context_error())
    sim = P.simulate(S.ScenarioSpec(climate="ssp245", horizon_end=2031, levers=[{"type": "irrigate", "crop": "pea"}]))
    assert sim.scenario_id and len(sim.alerts) <= 12 and sim.meters.vs_current_plan in ("better", "same", "worse")
    assert P.farms(sim.scenario_id, 2030)


def test_retrieval_live_per_module(monkeypatch):
    monkeypatch.setenv("API_MOCK", "0")
    from api import layers
    live = layers.live()
    assert live["live:ask"] == layers._imports("src.r_agent")
    assert live["live:board"] == layers._imports("src.r_board")


def test_intent_follow_up_builds_on_base(real):
    from api import layers
    if not layers._imports("src.p_parse"):
        pytest.skip("p_parse not built")
    base = {"climate": "ssp585", "horizon_end": 2060, "levers": [{"type": "irrigate", "crop": "pea"}]}
    r = real.post("/api/intent", json={"text": "What if we add a heat-tolerant pea from 2030?", "base": base}).json()
    assert r["door"] == "simulate" and r["spec"]["climate"] == "ssp585" and r["spec"]["horizon_end"] == 2060
    assert {lv["type"] for lv in r["spec"]["levers"]} == {"irrigate", "heat_tolerant_variety"}
    assert real.post("/api/intent", json={"text": "How did pea deliveries change since 2021?"}).json()["door"] == "ask"


@pytest.mark.skipif(not HAVE_V2, reason="needs `make v2` output and the snapshot")
def test_real_hedge_and_pathways():
    P.warm()
    if P.context_error():
        pytest.skip(P.context_error())
    h = P.hedge("ssp585")
    assert len(h.points) == 21 and sum(p.is_now for p in h.points) == 1 and any(p.is_best for p in h.points)
    assert all(p.crop in ("pea", "potato") for p in P.pathways("current_plan_ssp585"))


def test_report_download_round_trip(real):
    from api import layers
    if not (layers._imports("src.r_report") and layers._imports("openpyxl")):
        pytest.skip("r_report/openpyxl missing")
    from src import serve_db
    if not serve_db.exists():
        pytest.skip("needs out/serve.duckdb")
    q = "How did pea deliveries from Swedish farms in 2026 compare with 2021?"
    a = real.post("/api/ask", json={"question": "Make that a report", "history": [{"question": q}]}).json()
    assert a["report"], a
    r = real.get(a["report"]["url"])
    assert r.status_code == 200 and r.content[:2] == b"PK"  # an .xlsx is a zip
    assert real.get("/api/report/nope").status_code == 404
