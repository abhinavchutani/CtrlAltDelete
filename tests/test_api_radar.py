"""Field Radar v4 endpoints: outlook rules, graph, Teach filing (api/radar.py, api/kgraph.py)."""
from __future__ import annotations

import pytest

from api import kgraph as G
from api import radar as R
from src import r_knowledge as K
from src import serve_db


def test_status_and_bucket_edges():
    assert R.status_of(249_999) == "watch" and R.status_of(250_000) == "risk" and R.status_of(99_999) == "ok"
    assert R.bucket_of(100_000) == "100k_250k" and R.bucket_of(250_000) == "250k_plus" and R.bucket_of(0) == "lt100k"


def test_topic_rules():
    assert G._topic("The lower field waterlogs most Aprils") == "Sowing & drainage"
    assert G._topic("pollen beetle came early") == "Pests & disease"
    assert G._topic("the paper log at the plant") == "Notes"  # "plant" is not sowing


def test_ask_evidence_maps_to_nodes():
    assert G._node_for({"kind": "table_row", "ref": "raw_foodhills_odlingsdata_se"}) == "data:raw_foodhills_odlingsdata_se"
    assert G._node_for({"kind": "doc", "ref": "knowledge:K-0003"}) == "tacit:K-0003"
    assert G._node_for({"kind": "doc", "ref": "REASONING_LOG.md#R06"}) == "doc:reasoning"
    assert G._node_for({"kind": "table_row", "ref": "energy:S-SAK:2025-10:biogas"}) == "data:raw_energy_meter_readings"


needs_data = pytest.mark.skipif(not serve_db.exists(), reason="needs out/serve.duckdb (DATA_DIR pack)")


@needs_data
def test_teach_files_unverified_and_four_eyes(tmp_path, monkeypatch):
    monkeypatch.setattr(K, "STORE", tmp_path / "k.jsonl")
    f = G.file_note(G.NoteIn(text="F0112's lower field waterlogs most Aprils, so they sow peas two weeks later.",
                             contributed_by="Liisa"))
    assert f.verified is False and f.item.status == "pending_review"
    assert f.path[0] == "Pea" and "F0112" in f.path and f.path[-1] == "Sowing & drainage"
    assert "data:raw_weather_daily" in f.linked_node_ids
    with pytest.raises(Exception):
        G.confirm(f.note_id, G.ConfirmIn(reviewer=" liisa "))  # the contributor cannot confirm their own note
    assert G.confirm(f.note_id, G.ConfirmIn(reviewer="Anna")).status == "approved"
    assert G.refile(f.note_id, G.RefileIn(topic="Soil")).path[-1] == "Soil"
    tacit = [n for n in G.graph().nodes if n.kind == "tacit"]
    assert len(tacit) == 1 and tacit[0].verified is True


@needs_data
def test_gap_answer_is_filed_under_its_record(tmp_path, monkeypatch):
    monkeypatch.setattr(K, "STORE", tmp_path / "k.jsonl")
    gaps = [n for n in G.graph().nodes if n.kind == "gap"]
    if not gaps:
        pytest.skip("no open gaps in this snapshot")
    f = G.file_note(G.NoteIn(text="The meter was swapped; the reading is on the paper log at the plant.",
                             contributed_by="X", gap_id=gaps[0].id))
    assert f.path[0] == "Energy" and "crop:pea" not in f.item.tags


@needs_data
def test_today_endpoint():
    from fastapi.testclient import TestClient

    from api.main import app

    c = TestClient(app)
    r = c.get("/api/radar/today")
    assert r.status_code == 200
    t = r.json()
    assert t["date"] == t["default_date"] and t["path"] == "historical" and t["synthetic"] is True
    assert sum(t["counts"].values()) == len(t["all"]) and t["sources"]
    assert c.get("/api/radar/today", params={"date": "2025-06-01"}).status_code == 422
    assert c.get("/api/radar/today", params={"crop": "wheat"}).status_code == 422
