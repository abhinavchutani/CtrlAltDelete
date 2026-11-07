"""The v2 contract: every fixture validates against api/schemas.py, and API_MOCK=1 serves every endpoint."""
import json

import pytest
from fastapi.testclient import TestClient

from api import mock
from api import schemas as S

FIXTURE_MODEL = {"scenarios": list[S.ScenarioPreset], "scenario_current_plan_ssp245": S.SimResult,
                 "scenario_current_plan_ssp585": S.SimResult, "farms": list[S.FarmYear],
                 "weather": list[S.WeatherFrame], "hedge": S.Hedge, "pathways": list[S.PathwayItem],
                 "options": list[S.AdaptationOption], "board": list[S.BoardRow], "ask": list[S.AskOut],
                 "intent": dict[str, S.IntentOut]}


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("API_MOCK", "1")
    from api.main import app
    return TestClient(app)


def test_every_fixture_file_is_covered():
    names = {p.stem for p in mock.FIXTURES.glob("*.json")}
    assert names == set(FIXTURE_MODEL) | {"geo_farms", "geo_parcels"}


@pytest.mark.parametrize("name", sorted(FIXTURE_MODEL))
def test_fixture_validates(name):
    from pydantic import TypeAdapter
    TypeAdapter(FIXTURE_MODEL[name]).validate_python(json.loads((mock.FIXTURES / f"{name}.json").read_text()))


def test_fixture_content_rules():
    for sid in ("current_plan_ssp245", "current_plan_ssp585"):
        r = S.SimResult(**mock.load(f"scenario_{sid}"))
        assert r.synthetic and 1 <= len(r.alerts) <= 12
        assert {a.severity for a in r.alerts} <= {"critical", "notable"} and any(a.severity == "critical" for a in r.alerts)
        assert r.years[0] == 2026 and r.years[-1] == r.spec.horizon_end
    for a in mock.load("ask"):
        out = S.AskOut(**a)
        if out.table:
            S.TableOut(**out.table)
        if out.report:
            S.ReportRef(**out.report)
    w = [S.WeatherFrame(**f) for f in mock.load("weather")]
    assert all(len(f.cells) == 84 for f in w)
    assert len(S.Hedge(**mock.load("hedge")).points) == 21


def test_eur_band_edges():
    assert [S.eur_band(x) for x in (0, 49_999, 50_000, 100_000, 250_000, 999_999, 1_000_000)] == \
        ["< €50k", "< €50k", "€50–100k", "€100–250k", "€250k–1M", "€250k–1M", "> €1M"]


def test_lever_discriminator_and_bounds_shape():
    spec = S.ScenarioSpec(levers=[{"type": "irrigate", "crop": "pea"}, {"type": "region_split", "fi_share": 0.7}])
    assert isinstance(spec.levers[0], S.Irrigate) and isinstance(spec.levers[1], S.RegionSplit)
    with pytest.raises(ValueError):
        S.ScenarioSpec(levers=[{"type": "rain_dance"}])


def test_decision_needs_a_name():
    with pytest.raises(ValueError):
        S.Decision(status="approved", decided_by="", reason="ok")


GETS = ["/api/health", "/api/scenarios", "/api/scenario/current_plan_ssp245", "/api/scenario/heat_tolerant_pea_ssp585",
        "/api/cube/current_plan_ssp245/farms?year=2035", "/api/weather?climate=ssp245&year=2035",
        "/api/weather?climate=historical&year=2026", "/api/hedge?climate=ssp585", "/api/pathways/current_plan_ssp585",
        "/api/options?hazard=H2&crop=pea", "/api/board/current_plan_ssp245", "/api/geo/farms", "/api/geo/parcels"]


@pytest.mark.parametrize("path", GETS)
def test_mock_get_endpoints(client, path):
    r = client.get(path)
    assert r.status_code == 200, r.text


def test_mock_flow(client):
    assert client.get("/api/health").json()["mock"] is True
    assert client.get("/api/scenario/nope").status_code == 404
    i = client.post("/api/intent", json={"text": "What if we irrigate the driest pea fields?"}).json()
    assert i["door"] == "simulate" and i["spec"]["levers"]
    sim = client.post("/api/simulate", json=i["spec"]).json()
    assert sim["scenario_id"].startswith("custom_") and sim["meters"]["vs_current_plan"] == "better"
    assert client.post("/api/intent", json={"text": "How did pea deliveries compare with 2021?"}).json()["door"] == "ask"
    a = client.post("/api/ask", json={"question": "pea deliveries from Swedish farms 2021 vs 2026"}).json()
    assert a["status"] == "answered" and a["evidence"] and a["table"]["rows"]
    y = client.get("/api/cube/current_plan_ssp245/farms?year=2033").json()
    assert y and all(f["year"] == 2033 for f in y)
    opts = client.get("/api/options?hazard=H2&crop=pea").json()
    assert [o["option_id"] for o in opts][:2] == ["A04", "A06"]


def test_mock_decision_round_trip(client):
    row = client.get("/api/board/current_plan_ssp245").json()[0]["row_id"]
    assert client.post(f"/api/board/{row}/decision", json={"status": "approved", "decided_by": "", "reason": "x"}
                       ).status_code == 422
    r = client.post(f"/api/board/{row}/decision", json={"status": "approved", "decided_by": "A. Expert", "reason": "ok"})
    assert r.status_code == 200 and r.json()["status"] == "approved" and r.json()["decided_by"] == "A. Expert"


def test_real_mode_reports_unbuilt_layers(monkeypatch):
    monkeypatch.setenv("API_MOCK", "0")
    from api import layers
    from api.main import app
    c = TestClient(app)
    if not layers.available()["src.p_hedge"]:
        assert c.get("/api/hedge").status_code == 503
    assert c.get("/api/options?hazard=H1").status_code == 200  # retrieval on hold → fixtures
