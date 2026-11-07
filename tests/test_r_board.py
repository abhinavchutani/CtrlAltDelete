"""r_board: decision board rows and the human approval log (#94, V2-14). No data needed (alerts are faked)."""
import json

import pytest
from pydantic import ValidationError

from api.schemas import BoardRow, Decision
from src import r_board as B

ALERTS = [
    {"id": "a1", "year": 2026, "region": "SE_SKANE", "crop": "pea", "severity": "critical", "kind": "drought_flowering",
     "hazard": "H1", "title": "Pea flowering drought, SE_SKANE", "why": "drought index 0.67 vs 0.49 normal",
     "eur_at_risk": "€250k–1M", "suggested_lever": {"type": "region_split", "crop": "pea", "fi_share": 0.45},
     "evidence": [{"kind": "weather", "ref": "weather:historical:2026", "label": "weather frame 2026"}]},
    {"id": "a2", "year": 2030, "region": "SE_SKANE", "crop": "pea", "severity": "critical", "kind": "drought_flowering",
     "hazard": "H1", "title": "t", "why": "w", "eur_at_risk": "€250k–1M", "suggested_lever": None, "evidence": []},
    {"id": "a3", "year": 2034, "region": "FI_SW", "crop": "pea", "severity": "notable", "kind": "heat_flowering",
     "hazard": "H2", "title": "t", "why": "w", "eur_at_risk": "€100–250k", "suggested_lever": None, "evidence": []},
    {"id": "a4", "year": 2031, "region": "FI_SW", "crop": None, "severity": "critical", "kind": "assumption",
     "hazard": None, "title": "t", "why": "w", "eur_at_risk": None, "suggested_lever": None, "evidence": []},
]


@pytest.fixture()
def log(tmp_path, monkeypatch):
    path = tmp_path / "decisions.jsonl"
    monkeypatch.setattr(B, "DECISIONS_PATH", path)
    monkeypatch.setattr(B, "_alerts", lambda sid: ALERTS if sid == "demo" else [])
    monkeypatch.setattr(B, "_pathways", lambda sid: [
        {"crop": "pea", "region": "FI_SW", "option_id": "A04", "decide_by": 2029, "signpost": "3 hot flowering seasons"}])
    return path


def test_rows_group_recurring_risks_critical_first(log):
    rows = B.board("demo")
    assert all(isinstance(r, BoardRow) for r in rows)
    assert [(r.region, r.hazard) for r in rows] == [("SE_SKANE", "H1"), ("FI_SW", "H2")]   # a4 lacks crop/hazard
    assert rows[0].row_id == "demo-1" and "2026" in rows[0].risk and "2 alerts" in rows[0].trigger


def test_suggested_lever_option_comes_first_and_kb_evidence_is_attached(log):
    r = B.board("demo")[0]
    assert r.option_ids[0] == "A07"                                    # region_split was the alert's suggestion
    assert any(e.ref == "kb/adaptation_options.csv#A07" for e in r.evidence)
    assert any(e.kind == "weather" for e in r.evidence)                 # the alert's own evidence is kept


def test_decide_by_and_signpost_come_from_pathways(log):
    r = B.board("demo")[1]
    assert r.decide_by == 2029 and r.trigger == "3 hot flowering seasons"


def test_unknown_scenario_is_empty(log):
    assert B.board("nope") == [] and B.board("../x") == []


def test_decision_round_trips_and_survives_a_restart(log):
    out = B.decide("demo-1", Decision(status="approved", decided_by="Anna Agronomist", reason="robust under all SSPs"))
    assert out.status == "approved" and out.decided_by == "Anna Agronomist" and out.decided_at
    # a "restart": read the board again from the log file only
    again = {r.row_id: r for r in B.board("demo")}
    assert again["demo-1"].status == "approved" and again["demo-2"].status == "pending"
    entry = json.loads(log.read_text().splitlines()[0])
    assert entry["decided_by"] == "Anna Agronomist" and entry["option_ids"][0] == "A07"


def test_latest_decision_wins(log):
    B.decide("demo-2", Decision(status="approved", decided_by="A", reason="ok"))
    B.decide("demo-2", Decision(status="rejected", decided_by="B", reason="lead time too long"))
    assert {r.row_id: r for r in B.board("demo")}["demo-2"].status == "rejected"


def test_decision_without_a_name_is_refused(log):
    with pytest.raises(ValidationError):
        Decision(status="approved", decided_by="", reason="x")           # the contract refuses an empty name
    with pytest.raises(ValueError):
        B.decide("demo-1", Decision.model_construct(status="approved", decided_by="   ", reason="x"))
    assert not log.exists()                                             # nothing logged


def test_unknown_row_is_none(log):
    assert B.decide("demo-99", Decision(status="approved", decided_by="A", reason="x")) is None
