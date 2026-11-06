"""Copilot behaviour: offline stub routing, evidence, badges, and the LLM-mode number guard."""
import json

import pytest

from src import e_agent, e_llm, e_tools
from src import lineage as L
from src.db import connect

# The three public dev questions (tasks/dev/E_dev_answers.csv) with their dev answers, seeded as test
# fixture rows. They test routing and tolerance only; they are not our results.
DEV = [("What were total Scope 1 emissions in 2024 (tCO2e)?", "1", None, 6399.9, 0.03),
       ("What were market-based Scope 2 emissions in 2024 (tCO2e)?", "2_market", None, 62.9, 0.10),
       ("What were Scope 3 category 1 emissions in 2024 (tCO2e)?", "3", "cat1", 172085.0, 0.03)]


@pytest.fixture
def con(tmp_path, monkeypatch):
    monkeypatch.setenv("NAVIGATOR_DEV_ASSUME", "1")
    monkeypatch.setattr(e_llm, "available", lambda: False)
    c = connect(tmp_path / "e.duckdb")
    L.init_schema(c)
    # scope 1 as two lines (code must sum), scope 2 market as one, scope 3 cat1 plus a cat4 decoy
    lines = [("1", "stationary", 4000.0), ("1", "refrigerants", 2399.9), ("2_market", "electricity", 62.9),
             ("3", "cat1", 172085.0), ("3", "cat4", 9999.0)]
    for scope, cat, v in lines:
        L.write_result(c, f"TEST:A2:2024:{scope}:{cat}", metric="tco2e", value=v, unit="t CO2e", scope=scope,
                       category=cat, year=2024, method="test fixture", produced_by="test",
                       lineage=[L.src("record", f"erp:T{cat}:1"), L.src("factor", f"EF-{cat}")])
    return c


@pytest.mark.parametrize("q,scope,cat,expected,tol", DEV)
def test_stub_answers_dev_questions_within_tolerance(con, q, scope, cat, expected, tol):
    a = e_agent.answer(q, kind="numeric", con=con)
    assert not a.blocked and a.value is not None
    assert abs(a.value - expected) / expected <= tol
    assert a.evidence and "**Evidence**" in a.markdown
    assert a.pending and "pending expert approval" in a.markdown  # fixture rows are drafts


def test_drafts_hidden_outside_dev_mode(con, monkeypatch):
    monkeypatch.setenv("NAVIGATOR_DEV_ASSUME", "0")
    a = e_agent.answer(DEV[0][0], kind="numeric", con=con)
    assert a.markdown.startswith(e_agent.NOT_IN_DATA)


def test_qualified_numeric_question_is_not_guessed(con):
    a = e_agent.answer("What were Scope 1 emissions from LNG and LPG combustion at the Säkylä plant in 2025 (tCO2e)?",
                       kind="numeric", con=con)
    assert a.markdown.startswith(e_agent.NOT_IN_DATA) and a.value is None


def test_missing_year_is_not_in_the_data(con):
    assert e_agent.answer("What were total Scope 1 emissions in 2025 (tCO2e)?", kind="numeric",
                          con=con).markdown.startswith(e_agent.NOT_IN_DATA)


def _fake_llm(monkeypatch, final_text):
    calls = iter([{"role": "assistant", "content": "", "tool_calls": [{"id": "c1", "type": "function", "function": {
        "name": "query_results", "arguments": json.dumps({"metric": "tco2e", "scope": "1", "year": 2024, "aggregate": "sum"})}}]},
                  {"role": "assistant", "content": final_text, "tool_calls": []}])
    monkeypatch.setattr(e_llm, "available", lambda: True)
    monkeypatch.setattr(e_llm, "chat", lambda msgs, tools=None: next(calls))


def test_llm_answer_with_tool_number_passes(con, monkeypatch):
    _fake_llm(monkeypatch, "Total Scope 1 emissions in 2024 were 6,399.9 t CO2e.")
    a = e_agent.answer(DEV[0][0], con=con)
    assert a.mode == "llm" and not a.blocked and a.value == pytest.approx(6399.9)
    assert "TEST:A2:2024:1:stationary" in a.markdown


def test_llm_hallucinated_number_is_blocked(con, monkeypatch):
    _fake_llm(monkeypatch, "Total Scope 1 emissions in 2024 were 6,812 t CO2e, up 6.4 % on 2023.")
    a = e_agent.answer(DEV[0][0], con=con)
    assert a.blocked and "6,812" in a.markdown and "**Evidence**" not in a.markdown


def test_llm_cache_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(e_llm, "available", lambda: False)
    payload = {"model": e_llm.env("LLM_MODEL"), "messages": [{"role": "user", "content": "hi"}], "tools": [], "temperature": 0}
    (tmp_path / f"{e_llm._key(payload)}.json").write_text(json.dumps({"role": "assistant", "content": "cached"}))
    assert e_llm.chat([{"role": "user", "content": "hi"}], cache_dir=tmp_path)["content"] == "cached"
    with pytest.raises(RuntimeError):
        e_llm.chat([{"role": "user", "content": "uncached"}], cache_dir=tmp_path)


def test_search_frameworks_finds_flag_rules():
    if not (e_tools.pack_dir() / "data" / "07_frameworks" / "framework_digest.md").exists():
        pytest.skip("data pack not available")
    hits = e_tools.search_frameworks("separate SBTi FLAG target required", k=3)["passages"]
    assert hits and any("FLAG" in p["text"] for p in hits)
    assert all(p["file"] and p["section"] for p in hits)


def test_rubric_stub_quotes_pack_with_sources(con):
    if not (e_tools.pack_dir() / "data" / "07_frameworks" / "framework_digest.md").exists():
        pytest.skip("data pack not available")
    a = e_agent.answer("Does cancelling wind-power guarantees of origin reduce location-based Scope 2?",
                       kind="rubric", con=con)
    assert not a.blocked and a.markdown.startswith("From the pack") and any("§" in e for e in a.evidence)
