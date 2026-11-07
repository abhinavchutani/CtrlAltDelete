"""E answers CSV (#23): template shape, grounded answers only, deterministic."""
import pandas as pd
import pytest

from src import e_answers, e_llm, e_tools
from src import lineage as L
from src.db import connect


@pytest.fixture
def con(tmp_path, monkeypatch):
    if not (e_tools.pack_dir() / "tasks" / "E_questions.csv").exists():
        pytest.skip("data pack not available")
    monkeypatch.setenv("NAVIGATOR_DEV_ASSUME", "1")
    monkeypatch.setattr(e_llm, "available", lambda: False)
    c = connect(tmp_path / "e.duckdb")
    L.init_schema(c)
    for cat, scope, v in [("scope1_total", "total", 6399.9), ("scope2_market_total", "total", 62.9),
                          ("cat01_purchased_goods_services", "scope3", 172085.0)]:
        L.write_result(c, f"TEST:A2:2024:actual:{cat}", metric="tco2e", value=v, unit="t CO2e", scope=scope,
                       category=cat, year=2024, method="test fixture", produced_by="test",
                       lineage=[L.src("record", f"erp:T{cat}:1")])
    return c


def test_csv_matches_template_and_dev_answers(con):
    out = e_answers.build(con)
    tmpl = pd.read_csv(e_tools.pack_dir() / "tasks" / "templates" / "E_answers_submission.csv")
    assert list(out.columns) == list(tmpl.columns) and out["question_id"].tolist() == tmpl["question_id"].tolist()
    assert e_answers.dev_check(out)["ok"].all()


def test_unanswered_numeric_rows_are_empty_with_a_reason(con):
    out = e_answers.build(con).set_index("question_id")
    assert out.at["E01", "answer"] == "" and out.at["E01", "evidence"].startswith("not in the data")


def test_rubric_answers_cite_pack_sources(con):
    out = e_answers.build(con).set_index("question_id")
    rubric = [f"E{i}" for i in range(30, 40)]
    assert all("§" in out.at[q, "evidence"] for q in rubric)
    assert all(e_answers.e_check.EVIDENCE_MARK not in str(out.at[q, "answer"]) for q in rubric)


def test_rerun_is_deterministic(con):
    assert e_answers.build(con).equals(e_answers.build(con))
