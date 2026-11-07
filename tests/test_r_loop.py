"""r_loop: the LLM tool loop, driven by a scripted fake model (no key, no pack needed) (#93, V2-11)."""
import json

import duckdb
import pytest

from api.schemas import AskOut
from src import e_llm, r_loop
from src import r_eval as V


@pytest.fixture()
def con(tmp_path):
    p = tmp_path / "serve.duckdb"
    c = duckdb.connect(str(p))
    c.execute("CREATE TABLE raw_refrigerant_service_log AS SELECT * FROM (VALUES "
              "('refrigerant:RS1', 'S-SAK', 2024, 1.5::DECIMAL(6,2)), ('refrigerant:RS2', 'S-SAK', 2024, 2.0), "
              "('refrigerant:RS3', 'S-KAN', 2024, 0.5)) t(record_key, site_id, year, kg_added)")
    c.close()
    ro = duckdb.connect(str(p), read_only=True)
    yield ro
    ro.close()


def script(monkeypatch, steps):
    """Fake e_llm.chat: returns the scripted assistant messages in order and records what it was sent."""
    seen = []

    def chat(messages, tools=None, **_):
        seen.append([m.get("role") for m in messages])
        return steps[len(seen) - 1]
    monkeypatch.setattr(e_llm, "chat", chat)
    return seen


def call(name, args, i="c1"):
    return {"role": "assistant", "content": "", "tool_calls": [
        {"id": i, "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}]}


def say(text):
    return {"role": "assistant", "content": text, "tool_calls": []}


SQL = "SELECT count(*) AS n, sum(kg_added) AS kg FROM raw_refrigerant_service_log WHERE site_id = ? AND year = ?"


def test_answer_with_tool_numbers_passes_and_carries_evidence(monkeypatch, con):
    seen = script(monkeypatch, [call("run_sql", {"sql": SQL, "params": ["S-SAK", 2024]}),
                                say("2 refrigerant service events were logged at S-SAK in 2024, adding 3.5 kg.")])
    out = AskOut.model_validate(r_loop.llm_ask(con, "How many service events at S-SAK in 2024?"))
    assert out.status == "answered" and "raw_refrigerant_service_log" in [e.ref for e in out.evidence]
    assert out.table["rows"] == [[2, 3.5]]                              # DECIMAL came back as a number
    assert seen[1][-1] == "tool"                                         # the tool result went back to the model


def test_a_number_no_tool_returned_is_blocked(monkeypatch, con):
    script(monkeypatch, [call("run_sql", {"sql": SQL, "params": ["S-SAK", 2024]}),
                         say("7 events were logged at S-SAK in 2024.")])
    out = r_loop.llm_ask(con, "How many service events at S-SAK in 2024?")
    assert out["status"] == "not_in_data" and "Blocked" in out["answer_md"]


def test_writes_are_refused_and_the_model_sees_the_error(monkeypatch, con):
    script(monkeypatch, [call("run_sql", {"sql": "DELETE FROM raw_refrigerant_service_log"}),
                         say("Not in the data. I could not query it.")])
    assert r_loop.run_tool(con, "run_sql", {"sql": "DROP TABLE raw_refrigerant_service_log"})["error"].startswith("refused")
    assert r_loop.llm_ask(con, "delete it")["status"] == "not_in_data"


def test_unknown_tool_and_bad_json_do_not_crash(monkeypatch, con):
    bad = {"role": "assistant", "content": "", "tool_calls": [
        {"id": "x", "type": "function", "function": {"name": "rm_rf", "arguments": "{not json"}}]}
    script(monkeypatch, [bad, say("Not in the data.")])
    assert r_loop.llm_ask(con, "anything")["status"] == "not_in_data"


def test_step_limit(monkeypatch, con):
    script(monkeypatch, [call("run_sql", {"sql": SQL, "params": ["S-SAK", 2024]}, i=str(i)) for i in range(10)])
    out = r_loop.llm_ask(con, "loop forever", max_steps=3)
    assert out["status"] == "not_in_data" and "3 tool steps" in out["answer_md"]


def test_eval_has_15_cases_and_two_honest_refusals():
    assert len(V.CASES) == 15 and len({c.qid for c in V.CASES}) == 15
    assert sum(c.check == "not_in_data" for c in V.CASES) == 2 and sum(c.needs_llm for c in V.CASES) == 3


def test_eval_check_logic():
    case = V.Case("X", "q", "number")
    assert V.passes(case, {"status": "answered", "answer_md": "It was 6,399.9 t.", "evidence": []}, 6399.9)[0]
    assert not V.passes(case, {"status": "answered", "answer_md": "It was 6,500 t.", "evidence": []}, 6399.9)[0]
    nid = V.Case("Y", "q", "not_in_data")
    assert V.passes(nid, {"status": "not_in_data", "answer_md": "", "evidence": []}, None)[0]


@pytest.mark.skipif(not __import__("src.serve_db", fromlist=["exists"]).exists(), reason="needs out/serve.duckdb")
def test_offline_routes_pass_their_eval_questions(tmp_path, monkeypatch):
    monkeypatch.setattr(e_llm, "available", lambda: False)
    s = V.run(out_path=tmp_path / "ask_eval.json")
    assert s["offline_passed"] == s["offline_total"] == 12            # done-when: the offline routes still pass
    assert all(r["status"] == "not_in_data" for r in s["rows"] if r["needs_llm"])   # honest without a key
