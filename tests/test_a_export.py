"""2025 export + peat reveal (task #12). Data tests skip without the pack."""
import os

import pandas as pd
import pytest

from src import a_clean, a_export, a_inventory as A, load
from src import lineage as L
from src.db import connect


def test_method_notes_cover_template_categories():
    for cat in ["purchased_electricity", "cat01_purchased_goods_services", "cat11_use_of_sold_products", "biogenic_co2_scope1"]:
        assert cat in a_export.METHOD_NOTES


@pytest.fixture(scope="module")
def con(tmp_path_factory, monkeypatch_module=None):
    if not (load.pack_dir() / "data").is_dir():
        pytest.skip("data pack not available (set DATA_DIR)")
    os.environ["NAVIGATOR_DEV_ASSUME"] = "1"
    c = connect(tmp_path_factory.mktemp("db") / "t.duckdb")
    load.load_all(c)
    L.init_schema(c)
    a_clean.propose_and_assume(c)
    a_clean.build_clean(c)
    return c


def test_a1_and_a2_match_templates(con, tmp_path, monkeypatch):
    monkeypatch.setattr(a_export, "OUT", tmp_path)
    a1 = a_export.export_a1(con)
    tmpl = pd.read_csv(load.pack_dir() / "tasks" / "templates" / "A1_issues_submission.csv")
    assert list(a1.columns) == list(tmpl.columns) and a1.record_key.is_unique and len(a1) > 50
    legit = set(con.execute("SELECT record_key FROM issues WHERE status = 'legitimate'").df().record_key)
    assert not legit & set(a1.record_key) - set(con.execute("SELECT record_key FROM issues WHERE status='proposed'").df().record_key)
    c = A.clean_tables(con)
    a2 = a_export.export_a2(A.summarise(A.compute(A.canonical(con, c), 2025)))
    t2 = pd.read_csv(load.pack_dir() / "tasks" / "templates" / "A2_inventory_2025_submission.csv")
    assert a2[["scope", "category"]].equals(t2[["scope", "category"]]) and a2.tco2e.notna().all()


def test_peat_reveal_results(con, tmp_path, monkeypatch):
    monkeypatch.setattr(a_export, "OUT", tmp_path)
    head = a_export.peat_reveal(con, A.clean_tables(con))
    assert head["with_organic_soils_t"] > head["mineral_only_t"] > 0
    n = con.execute("SELECT count(DISTINCT scenario) FROM results WHERE metric = 'farm_tco2e'").fetchall()[0][0]
    assert n == 2
