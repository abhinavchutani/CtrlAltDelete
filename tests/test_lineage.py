"""The shared contract: tables, writer rules, and 'a published number without lineage is a bug'."""
import pytest

from src import lineage as L
from src.db import connect, db_path


@pytest.fixture
def con(tmp_path, monkeypatch):
    monkeypatch.setenv("NAVIGATOR_DEV_ASSUME", "1")
    c = connect(tmp_path / "t.duckdb")
    L.init_schema(c)
    L.init_schema(c)  # idempotent
    return c


def _issue(con, **kw):
    args = dict(table_name="erp_purchase_lines", record_key="erp:0042:3", year=2024, issue_type="unit_error",
                confidence=0.9, rule_id="price_ratio", explanation="x", evidence={"ratio": 1000},
                proposed_fix={"field": "quantity", "old_value": 5, "new_value": 5000},
                created_by="agent:test")
    args.update(kw)
    return L.propose_issue(con, **args)


def _result(con, rid="A2:2025:scope1:total", lineage=(("record", "erp:0042:3"),)):
    L.write_result(con, rid, metric="tco2e", value=1.5, unit="t CO2e", method="m", produced_by="test",
                   scope="1", year=2025, lineage=list(lineage))


def test_tables_match_contract(con):
    cols = {t: [r[0] for r in con.execute(f"DESCRIBE {t}").fetchall()]
            for t in ["issues", "corrections", "results", "lineage"]}
    assert cols["corrections"] == ["correction_id", "issue_id", "record_key", "field", "old_value",
                                   "new_value", "reason", "approved_by", "approved_at"]
    assert cols["lineage"] == ["result_id", "source_kind", "source_ref", "contribution", "note"]
    assert len(cols["issues"]) == 13 and len(cols["results"]) == 12


def test_issue_id_stable_and_rerun_keeps_human_decision(con):
    iid = _issue(con)
    assert iid == "price_ratio:erp:0042:3"
    L.set_issue_status(con, iid, "rejected")
    _issue(con, confidence=0.5)
    assert con.execute("SELECT status, confidence FROM issues").fetchall() == [("rejected", 0.5)]


def test_correction_defaults_to_proposed_fix(con):
    iid = _issue(con)
    cid = L.apply_correction(con, iid, approved_by="DEV-ASSUMED", reason="dev")
    row = con.execute("SELECT record_key, field, old_value, new_value FROM corrections").fetchone()
    assert cid == f"corr:{iid}" and row == ("erp:0042:3", "quantity", "5", "5000")
    assert con.execute("SELECT status FROM issues").fetchone()[0] == "proposed"  # still needs a human
    L.apply_correction(con, iid, approved_by="Expert Reviewer", reason="checked invoice")
    assert con.execute("SELECT status FROM issues").fetchone()[0] == "approved"
    assert con.execute("SELECT count(*) FROM corrections").fetchone()[0] == 1


@pytest.mark.parametrize("who", ["", "agent:noa-claude", "noa-claude"])
def test_agents_cannot_approve(con, who):
    iid = _issue(con)
    with pytest.raises(ValueError):
        L.apply_correction(con, iid, approved_by=who, reason="r")


def test_dev_assumed_needs_dev_mode(con, monkeypatch):
    monkeypatch.setenv("NAVIGATOR_DEV_ASSUME", "0")
    with pytest.raises(ValueError):
        L.apply_correction(con, _issue(con), approved_by="DEV-ASSUMED", reason="r")


def test_result_requires_lineage_and_valid_kind(con):
    with pytest.raises(ValueError):
        _result(con, lineage=())
    with pytest.raises(ValueError):
        _result(con, lineage=(("guess", "x"),))


def test_rewrite_resets_to_draft_and_replaces_lineage(con):
    _result(con)
    L.publish(con, ["A2:2025:scope1:total"], by="Expert Reviewer")
    _result(con, lineage=(("factor", "EF-1"), ("correction", "corr:x")))
    assert con.execute("SELECT status FROM results").fetchone()[0] == "draft"
    assert con.execute("SELECT count(*) FROM lineage").fetchone()[0] == 2


def test_publish_is_human_only(con):
    _result(con)
    for who in ["DEV-ASSUMED", "agent:x"]:
        with pytest.raises(ValueError):
            L.publish(con, ["A2:2025:scope1:total"], by=who)


def test_orphan_published_is_detected(con):
    con.execute("INSERT INTO results (result_id, status) VALUES ('X:orphan', 'published')")
    assert L.orphan_published(con) == ["X:orphan"]
    with pytest.raises(ValueError):
        L.publish(con, ["X:orphan"], by="Expert Reviewer")


def test_export_corrections(con, tmp_path):
    L.apply_correction(con, _issue(con), approved_by="DEV-ASSUMED", reason="dev")
    p = L.export_corrections(con, tmp_path / "corrections.csv")
    assert p.read_text().splitlines()[0].startswith("correction_id,issue_id,record_key")


def test_no_published_result_without_lineage_in_real_db():
    """The build-breaking check on the team database (skips when it does not exist, e.g. in CI)."""
    if not db_path().exists():
        pytest.skip("no navigator.duckdb yet")
    con = connect(read_only=True)
    if not con.execute("SELECT 1 FROM information_schema.tables WHERE table_name = 'results'").fetchone():
        pytest.skip("results table not created yet")
    assert L.orphan_published(con) == []
