"""Tests for LLM triage: parsing/validation and the offline stub run without data or keys."""
import os

import pandas as pd
import pytest

from src import a_triage as T


def test_parse_valid_json_inside_text():
    out = T.parse('Sure: {"decision": "legitimate", "issue_type": "meter_spike", "confidence": 0.82, '
                  '"explanation": "harvest-season peak"} ok', "meter_spike")
    assert out == {"decision": "legitimate", "issue_type": "meter_spike", "confidence": 0.82,
                   "explanation": "harvest-season peak"}


@pytest.mark.parametrize("bad", ["no json here", '{"decision": "maybe", "confidence": 0.5}',
                                 '{"decision": "issue", "confidence": 7}', '{"decision": "issue"}'])
def test_parse_rejects_bad_replies(bad):
    out = T.parse(bad, "unit_error")
    assert out["decision"] == "unsure" and out["confidence"] == 0.0


def test_parse_unknown_type_falls_back():
    out = T.parse('{"decision": "issue", "issue_type": "made_up", "confidence": 0.6, "explanation": "x"}', "soil_misreport")
    assert out["issue_type"] == "soil_misreport"


def test_offline_stub_keeps_rule_decision(monkeypatch):
    monkeypatch.setattr(T.e_llm, "available", lambda: False)
    issue = pd.Series({"issue_type": "soil_misreport", "confidence": 0.6, "explanation": "map says organic"})
    out = T.triage_one(None, issue)
    assert out["decision"] == "issue" and out["model"] == "offline-stub" and out["confidence"] == 0.6


def test_run_on_pack(tmp_path):
    from src import a_clean, load
    from src import lineage as L
    from src.db import connect
    if not (load.pack_dir() / "data").is_dir():
        pytest.skip("data pack not available (set DATA_DIR)")
    os.environ["NAVIGATOR_DEV_ASSUME"] = "1"
    con = connect(tmp_path / "t.duckdb")
    load.load_all(con)
    L.init_schema(con)
    a_clean.propose_and_assume(con)
    df = T.run(con)
    assert len(df) > 0 and set(df.decision) <= T.DECISIONS
    assert df.rule_confidence.between(T.GREY_LO, T.GREY_HI - 1e-9).all()
