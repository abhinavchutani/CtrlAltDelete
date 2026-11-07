"""Review & publish (#21): approve one item → total changes → publish, on mock data."""
import pytest

from app import mock, review
from src import lineage as L
from src.db import connect

WHO = "Test Reviewer"  # a stand-in typed by the test, the way a human types their name in the app


@pytest.fixture
def con(tmp_path, monkeypatch):
    monkeypatch.setenv("NAVIGATOR_DEV_ASSUME", "1")
    mock.seed(tmp_path / "m.duckdb")
    return connect(tmp_path / "m.duckdb")


def _total(con, scope="scope1"):
    return con.execute(f"SELECT value, status FROM results WHERE result_id = 'MOCK:A2:2025:actual:{scope}_total'").fetchone()


@pytest.mark.parametrize("who", ["", "agent:noa-claude", "noa-claude", "climate-agent", "DEV-ASSUMED"])
def test_agents_and_placeholders_cannot_review(who):
    assert review.reviewer_error(who) is not None


def test_accept_recalculate_publish_end_to_end(con):
    q = review.queue(con)
    iid = q[q["rule_id"] == "mock_line_x10"]["issue_id"].iloc[0]
    before, _ = _total(con)
    cid = review.accept(con, iid, WHO, "checked the invoice")
    row = con.execute("SELECT approved_by, reason FROM corrections WHERE correction_id = ?", [cid]).fetchone()
    assert row == (WHO, "checked the invoice")
    assert con.execute("SELECT status FROM issues WHERE issue_id = ?", [iid]).fetchone()[0] == "approved"

    changed = review.recalculate(con, mock=True)
    after, status = _total(con)
    assert after < before and status == "draft"
    assert "MOCK:A2:2025:actual:scope1_total" in set(changed["result_id"])

    review.publish(con, ["MOCK:A2:2025:actual:scope1_total"], WHO)
    assert _total(con)[1] == "published"
    with pytest.raises(ValueError):
        review.publish(con, ["MOCK:A2:2025:actual:scope3_total"], "abhinav-claude")


def test_recalculate_keeps_status_of_unchanged_results(con):
    review.publish(con, ["MOCK:A2:2025:actual:scope3_total"], WHO)
    iid = review.queue(con).query("rule_id == 'mock_line_x10' and record_key.str.startswith('mockline:scope1')")["issue_id"].iloc[0]
    review.accept(con, iid, WHO)
    review.recalculate(con, mock=True)
    assert _total(con, "scope3")[1] == "published"   # scope 3 untouched by a scope 1 fix
    assert _total(con, "scope1")[1] == "draft"


def test_reject_and_dev_assumed_corrections_do_not_change_numbers(con):
    q = review.queue(con)
    ids = q[q["rule_id"] == "mock_line_x10"]["issue_id"].tolist()
    review.reject(con, ids[0], WHO, "not an error")
    L.apply_correction(con, ids[1], approved_by="DEV-ASSUMED", reason="dev")
    before = _total(con)[0] + _total(con, "scope3")[0]
    review.recalculate(con, mock=True)
    assert _total(con)[0] + _total(con, "scope3")[0] == before
    assert con.execute("SELECT status FROM issues WHERE issue_id = ?", [ids[0]]).fetchone()[0] == "rejected"


def test_bulk_accept_excludes_soil_misreports(con):
    q = review.queue(con)
    bulk = review.bulk_candidates(q)
    assert len(bulk) and not (bulk["issue_type"] == "soil_misreport").any()
    soil = q[q["issue_type"] == "soil_misreport"]["issue_id"].tolist()
    with pytest.raises(ValueError):
        review.bulk_accept(con, soil[:1], WHO)
    ids = bulk["issue_id"].tolist()[:3]
    assert len(review.bulk_accept(con, ids, WHO)) == len(ids)
    assert con.execute("SELECT count(*) FROM corrections WHERE approved_by = ?", [WHO]).fetchone()[0] == len(ids)


def test_review_page_flow_in_the_app(monkeypatch):
    from streamlit.testing.v1 import AppTest
    monkeypatch.setenv("APP_MOCK", "1")
    at = AppTest.from_file("../app/Home.py", default_timeout=60)
    at.run()
    at.switch_page("views/review.py").run()
    assert not at.exception
    assert at.button(key="rq_accept").disabled          # read-only until a human types a name
    at.text_input(key="reviewer").input(WHO).run()
    at.multiselect(key="rq_types").select("unit_error").run()
    pick = [o for o in at.selectbox(key="rq_pick").options if "mock_line_x10" in o][0]
    at.selectbox(key="rq_pick").select(pick).run()
    at.button(key="rq_accept").click().run()
    at.button(key="recalc").click().run()
    assert not at.exception
    assert any("results changed" in m.value for m in at.markdown)
