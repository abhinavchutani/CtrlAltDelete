"""r_report: .xlsx with a Data and a Sources sheet, rows straight from the read-only query (#92, V2-10)."""
import duckdb
import pytest
from openpyxl import load_workbook

from src import r_report as R
from src import serve_db


@pytest.fixture()
def con(tmp_path):
    p = tmp_path / "serve.duckdb"
    c = duckdb.connect(str(p))
    c.execute("CREATE TABLE raw_erp_purchase_lines AS SELECT 'erp:1' AS record_key, 2024 AS year, 10.0 AS qty "
              "UNION ALL SELECT 'erp:2', 2025, 5.0")
    c.close()
    ro = duckdb.connect(str(p), read_only=True)
    yield ro
    ro.close()


@pytest.fixture(autouse=True)
def report_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(R, "REPORT_DIR", tmp_path / "reports")


def _sheets(ref):
    wb = load_workbook(R.path_for(ref["report_id"]))
    data = [[c.value for c in r] for r in wb["Data"].iter_rows()]
    src = {r[0].value: r[1].value for r in wb["Sources"].iter_rows(min_row=2)}
    return wb.sheetnames, data, src


def test_export_query_writes_data_and_sources(con):
    ref = R.make_report(con, "export_query", {"year": 2024},
                        sql="SELECT record_key, qty FROM raw_erp_purchase_lines WHERE year = ?", params_list=[2024])
    names, data, src = _sheets(ref)
    assert names == ["Data", "Sources"]
    assert data == [["record_key", "qty"], ["erp:1", 10.0]]
    assert "raw_erp_purchase_lines" in src["tables"] and "erp:1" in src["record_keys"]
    assert "Synthetic" in src["note"] and src["query"].startswith("SELECT")
    assert ref["url"] == f"/api/report/{ref['report_id']}"


def test_same_request_same_id():
    assert R.report_id("energy_by_site_month", {"year": 2024}) == R.report_id("energy_by_site_month", {"year": 2024})
    assert R.report_id("energy_by_site_month", {"year": 2024}) != R.report_id("energy_by_site_month", {"year": 2023})


def test_write_sql_is_refused(con):
    with pytest.raises(Exception):
        R.make_report(con, "export_query", {}, sql="DELETE FROM raw_erp_purchase_lines")


def test_path_for_rejects_tricks():
    assert R.path_for("../../.env") is None and R.path_for("energy_by_site_month-zzzz") is None


def test_unknown_template():
    with pytest.raises(ValueError):
        R.make_report(None, "nope", {})


needs_snapshot = pytest.mark.skipif(not serve_db.exists(), reason="out/serve.duckdb missing (run make snapshot)")


@needs_snapshot
def test_energy_report_question_returns_a_report_with_both_sheets():
    from src.r_agent import ask
    out = ask("Build me the 2024 energy report by site and month")
    assert out["status"] == "answered" and out["report"]
    names, data, src = _sheets(out["report"])
    assert names == ["Data", "Sources"] and data[0][:3] == ["site_id", "month", "carrier"] and len(data) > 50


@needs_snapshot
def test_make_that_a_report_uses_the_previous_question_and_matches_the_answer():
    from src.r_agent import ask
    prev = "How did pea deliveries from Swedish farms in 2026 compare with 2021?"
    out = ask("make that a report", [{"question": prev}])
    _, data, _ = _sheets(out["report"])
    cols = data[0]
    t2026 = sum(r[cols.index("delivered_t")] for r in data[1:] if r[cols.index("year")] == 2026)
    assert round(t2026, 1) == ask(prev)["table"]["rows"][-1][1]   # same tonnes as the answer's table


def test_no_history_report_request_is_not_in_data(monkeypatch):
    from src import r_agent
    if not serve_db.exists():
        pytest.skip("needs snapshot")
    assert r_agent.ask("make that a report")["status"] == "not_in_data"
