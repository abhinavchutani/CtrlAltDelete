"""Every app page renders without exceptions on the seeded mock data (no pack needed)."""
import pytest
from streamlit.testing.v1 import AppTest

PAGES = ["views/data_quality.py", "views/inventory.py", "views/farm_peat.py", "views/climate_risk.py",
         "views/review.py"]


@pytest.fixture(autouse=True)
def _mock(monkeypatch):
    monkeypatch.setenv("APP_MOCK", "1")


def test_mock_seed_has_lineage_for_every_result(tmp_path):
    from app import mock
    from src import lineage as L
    from src.db import connect

    mock.seed(tmp_path / "m.duckdb")  # not out/mock.duckdb: an in-process app may hold it open
    con = connect(tmp_path / "m.duckdb", read_only=True)
    n_orphans = con.execute("SELECT count(*) FROM results r WHERE NOT EXISTS "
                            "(SELECT 1 FROM lineage l WHERE l.result_id = r.result_id)").fetchone()[0]
    assert n_orphans == 0 and L.orphan_published(con) == []
    assert con.execute("SELECT count(*) FROM results WHERE status <> 'draft'").fetchone()[0] == 0


@pytest.mark.parametrize("page", PAGES)
def test_page_renders(page):
    at = AppTest.from_file("../app/Home.py", default_timeout=60)
    at.run()
    if page != PAGES[0]:
        at.switch_page(page).run()
    assert not at.exception, at.exception
    assert any("MOCK DATA" in w.value for w in at.warning)


def test_legitimate_rows_are_not_counted_as_issues():
    import pandas as pd
    from app import data
    df = pd.DataFrame({"issue_type": ["unit_error", "unit_error", "observation", "meter_spike"],
                       "status": ["proposed", "legitimate", "proposed", "approved"]})
    assert data.flagged(df).issue_type.tolist() == ["unit_error", "meter_spike"]


def test_farm_page_does_not_count_the_all_farms_total(monkeypatch, tmp_path):
    """On Track A's real shape (#48) the all_farms row must not be added to the per-farm sum."""
    from app import mock
    from src.db import connect
    db = tmp_path / "m.duckdb"
    mock.seed(db)
    con = connect(db, read_only=True)
    per_farm = con.execute("SELECT sum(value) FROM results WHERE metric='farm_tco2e' AND category <> 'all_farms' "
                           "AND scenario='with_organic_soils'").fetchone()[0]
    total = con.execute("SELECT value FROM results WHERE metric='farm_tco2e' AND category = 'all_farms' "
                        "AND scenario='with_organic_soils'").fetchone()[0]
    con.close()
    assert per_farm == total
    monkeypatch.setenv("APP_MOCK", "1")
    at = AppTest.from_file("../app/Home.py", default_timeout=60)
    at.run()
    at.switch_page("views/farm_peat.py").run()
    assert not at.exception
    shown = [m.value for m in at.metric if "organic" in m.label.lower()][0]
    assert shown == f"{total:,.0f} t CO2e"
