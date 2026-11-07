"""Inventory (task #11): formula unit test in CI; dev-truth scores with the pack."""
import os

import pandas as pd
import pytest

from src import a_clean, a_inventory as A, load
from src import lineage as L
from src.db import connect


def test_score_a2_full_and_zero_credit():
    key = pd.DataFrame({"category": ["scope1_total", "scope3_total"], "tco2e": [100.0, 1000.0]})
    assert A.score_a2(key, key)["error_pct"]["scope1_total"] == 0.0
    off = pd.DataFrame({"category": ["scope1_total", "scope3_total"], "tco2e": [110.0, 1000.0]})
    assert A.score_a2(off, key)["error_pct"]["scope1_total"] == 10.0


def test_apply_corrections_drops_and_sets():
    raw = pd.DataFrame({"record_key": ["a", "b"], "quantity": [1.0, 2.0]})
    corr = pd.DataFrame([{"table_name": "t", "correction_id": "c1", "record_key": "a", "field": "quantity", "new_value": "1000"},
                         {"table_name": "t", "correction_id": "c2", "record_key": "b", "field": "*", "new_value": "DELETE"},
                         {"table_name": "t", "correction_id": "c3", "record_key": "z", "field": "value", "new_value": "5"}])
    clean, missing = A.apply_corrections(raw, corr)
    assert clean.quantity.tolist() == [1000.0] and missing.record_key.tolist() == ["z"]


@pytest.fixture(scope="module")
def con(tmp_path_factory):
    if not (load.pack_dir() / "data").is_dir():
        pytest.skip("data pack not available (set DATA_DIR)")
    os.environ["NAVIGATOR_DEV_ASSUME"] = "1"
    c = connect(tmp_path_factory.mktemp("db") / "t.duckdb")
    load.load_all(c)
    L.init_schema(c)
    a_clean.propose_and_assume(c)
    a_clean.build_clean(c)
    return c


def test_dev_inventories_meet_end_goal_bar(con):
    res = A.run(con, years=(2023, 2024), write=False)
    s = {y: A.score_a2(res[y], con.execute(f"SELECT * FROM task_dev_A2_dev_inventory_{y}").df()) for y in (2023, 2024)}
    assert all(v["score"] >= 70 for v in s.values()), s          # END_GOAL bar per year
    assert sum(v["score"] for v in s.values()) / 2 >= 85, s      # and no regression on the mean


def test_results_have_lineage(con):
    A.run(con, years=(2024,), write=True)
    orphans = con.execute("""SELECT count(*) FROM results r WHERE r.result_id LIKE 'A2:2024:%'
                             AND NOT EXISTS (SELECT 1 FROM lineage l WHERE l.result_id = r.result_id)""").fetchall()[0][0]
    assert orphans == 0
    assert con.execute("SELECT count(DISTINCT status) FROM results WHERE result_id LIKE 'A2:%'").fetchall()[0][0] == 1  # all draft


def test_flag_results_written_with_lineage(con):
    A.run(con, years=(2025,), write=True)
    rows = dict(con.execute("""SELECT category, value FROM results
                               WHERE result_id LIKE 'A2:2025:actual:flag:%'""").fetchall())
    assert rows["flag_total"] > 0 and 50 < rows["flag_share_pct"] < 90
    assert con.execute("""SELECT count(*) FROM lineage WHERE result_id = 'A2:2025:actual:flag:flag_total'""").fetchall()[0][0] >= 2
