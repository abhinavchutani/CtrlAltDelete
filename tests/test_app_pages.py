"""Every app page renders without exceptions on the seeded mock data (no pack needed)."""
import pytest
from streamlit.testing.v1 import AppTest

PAGES = ["views/data_quality.py", "views/inventory.py", "views/farm_peat.py", "views/climate_risk.py"]


@pytest.fixture(autouse=True)
def _mock(monkeypatch):
    monkeypatch.setenv("APP_MOCK", "1")


def test_mock_seed_has_lineage_for_every_result():
    from app import mock
    from src import lineage as L
    from src.db import connect

    mock.seed()
    con = connect(mock.MOCK_DB, read_only=True)
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
