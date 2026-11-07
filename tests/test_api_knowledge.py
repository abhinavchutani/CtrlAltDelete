"""API: knowledge (human review) + gaps endpoints (#123). Knowledge needs no data; gaps skip without serve.duckdb."""
import pytest
from fastapi.testclient import TestClient

from api.main import app
from src import r_knowledge as K
from src import serve_db

STMT = {"statement": "Old freezer line at Säkylä decommissioned March 2025", "linked_refs": ["S-SAK"],
        "contributed_by": "Matti", "role": "energy manager"}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(K, "STORE", tmp_path / "knowledge.jsonl")
    monkeypatch.setenv("API_MOCK", "1")
    return TestClient(app)


def test_add_list_approve_round_trip(client):
    r = client.post("/api/knowledge", json=STMT)
    assert r.status_code == 201 and r.json()["status"] == "pending_review"
    kid = r.json()["knowledge_id"]
    assert [k["knowledge_id"] for k in client.get("/api/knowledge?status=pending_review").json()] == [kid]
    r = client.post(f"/api/knowledge/{kid}/decision", json={"decision": "approve", "reviewer": "Anna", "note": "ok"})
    assert r.status_code == 200 and (r.json()["status"], r.json()["reviewer"]) == ("approved", "Anna")
    assert client.get("/api/knowledge?status=pending_review").json() == []


@pytest.mark.parametrize("name", ["", "   "])
def test_blank_contributor_is_422(client, name):
    assert client.post("/api/knowledge", json=STMT | {"contributed_by": name}).status_code == 422
    assert client.get("/api/knowledge").json() == []


@pytest.mark.parametrize("reviewer,why", [("   ", "reviewer"), (" matti ", "four-eyes")])
def test_blank_reviewer_or_self_review_is_422(client, reviewer, why):
    kid = client.post("/api/knowledge", json=STMT).json()["knowledge_id"]
    r = client.post(f"/api/knowledge/{kid}/decision", json={"decision": "approve", "reviewer": reviewer})
    assert r.status_code == 422 and why in r.json()["detail"]


def test_unknown_item_is_404_and_bad_status_is_422(client):
    assert client.post("/api/knowledge/K-9999/decision", json={"decision": "reject", "reviewer": "Anna"}).status_code == 404
    assert client.get("/api/knowledge?status=maybe").status_code == 422


def test_gaps_need_real_mode(client):
    assert client.get("/api/gaps").status_code == 503


@pytest.mark.skipif(not serve_db.exists(), reason="needs out/serve.duckdb (make snapshot)")
def test_gaps_2025_real(monkeypatch):
    monkeypatch.setenv("API_MOCK", "0")
    monkeypatch.setenv("API_WARM", "0")
    gaps = TestClient(app).get("/api/gaps?year=2025").json()
    assert len(gaps) == 3 and all(g["owner"] and g["draft_message"] and g["evidence"] for g in gaps)


@pytest.mark.skipif(not serve_db.exists(), reason="needs out/serve.duckdb (make snapshot)")
def test_conflict_check_runs_in_real_mode(tmp_path, monkeypatch):
    monkeypatch.setattr(K, "STORE", tmp_path / "knowledge.jsonl")
    monkeypatch.setenv("API_MOCK", "0")
    monkeypatch.setenv("API_WARM", "0")
    k = TestClient(app).post("/api/knowledge", json=STMT | {"valid_from": "2025-03-01"}).json()
    assert k["conflicts"], "S-SAK readings continue after March 2025, so the reviewer should see a conflict"
