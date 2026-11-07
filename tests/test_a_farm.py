"""Tests for the farm detectors, A1 scoring and clean_* build. Unit tests run in CI; data tests skip."""
import pandas as pd
import pytest

from src import a_clean, load
from src.a_detect import farm
from src.a_score import score_a1
from src.db import connect


def _survey(**over):
    base = dict(record_key=["farm_survey:FS1", "farm_survey:FS2", "farm_survey:FS3", "farm_survey:FS4"],
                farm_id=["F1", "F2", "F3", "F4"], crop=["pea"] * 4, year=[2024] * 4,
                area_ha=[10.0, 10.0, 10.0, 16.0], parcel_ha=[10.0, 10.0, 10.0, 10.0],
                n_mineral_kg_ha=[30.0, 30.0, 300.0, 30.0], yield_t_ha=[3.0, 3.1, 3.0, 30.0],
                soil_type_reported=["Mineral soil"] * 4,
                crop_organic_share=[0.0, 0.6, 0.0, 0.0], farm_organic_share=[0.0, 0.4, 0.0, 0.0])
    base.update(over)
    return pd.DataFrame(base)


def test_rules_fire_on_planted_errors_only():
    d = _survey()
    assert farm.area_mismatch(d).record_key.tolist() == ["farm_survey:FS4"]
    ds = farm.decimal_shift(d)
    assert ds.record_key.tolist() == ["farm_survey:FS3"] and ds.proposed_fix[0]["new_value"] == 30.0
    yo = farm.yield_outlier(d)
    assert yo.record_key.tolist() == ["farm_survey:FS4"] and yo.proposed_fix[0]["new_value"] == 3.0
    assert farm.soil_misreport(d).record_key.tolist() == ["farm_survey:FS2"]


def test_soil_map_alone_needs_farm_agreement_or_history():
    d = _survey(crop_organic_share=[0.6, 0.6, 0.0, 0.0], farm_organic_share=[0.1, 0.1, 0.6, 0.0],
                crop_organic_reports=[0, 2, 0, 0])
    # FS1: crop map only → no; FS2: crop map + own organic reports → yes; FS3: farm map without history → no
    assert farm.soil_misreport(d).record_key.tolist() == ["farm_survey:FS2"]


def test_zero_nitrogen_is_not_a_decimal_shift():
    d = _survey(n_mineral_kg_ha=[0.0, 30.0, 30.0, 30.0])  # peas often get no mineral N
    assert farm.decimal_shift(d).empty


def test_score_formula():
    labels = pd.DataFrame({"table_name": ["farm_survey"] * 2, "record_key": ["a", "b"],
                           "issue_type": ["area_mismatch", "soil_misreport"], "year": [2024, 2024]})
    pred = pd.DataFrame({"table_name": ["farm_survey"] * 2, "record_key": ["a", "c"],
                         "issue_type": ["area_mismatch", "area_mismatch"], "confidence": [0.9, 0.9], "year": [2024, 2024]})
    s = score_a1(pred, labels)
    assert s["f1"] == 0.5 and s["type_accuracy"] == 1.0 and s["score"] == 50.0


@pytest.fixture(scope="module")
def con(tmp_path_factory, monkeypatch_module=None):
    if not (load.pack_dir() / "data").is_dir():
        pytest.skip("data pack not available (set DATA_DIR)")
    import os
    os.environ["NAVIGATOR_DEV_ASSUME"] = "1"
    c = connect(tmp_path_factory.mktemp("db") / "t.duckdb")
    load.load_all(c)
    from src import lineage as L
    L.init_schema(c)
    return c


def test_dev_score_and_clean_tables(con):
    from src.a_score import dev_labels
    cands = a_clean.propose_and_assume(con)
    s = score_a1(cands, dev_labels(con), restrict_tables=["farm_survey", "farm_registry"])
    assert s["score"] >= 85, s
    stats = a_clean.build_clean(con)
    assert stats["clean_farm_survey"] == 3437 and stats["survey_rows_corrected"] > 300
    assert con.execute("SELECT count(*) FROM corrections WHERE approved_by NOT IN ('DEV-ASSUMED')").fetchall()[0][0] == 0


def test_rerun_retires_issues_a_rule_no_longer_raises(tmp_path):
    from src import lineage as L
    con = connect(tmp_path / "t.duckdb")
    L.init_schema(con)
    keep = L.propose_issue(con, table_name="farm_survey", record_key="farm_survey:A", year=2024, issue_type="soil_misreport",
                           confidence=0.85, rule_id="r", explanation="", evidence={}, proposed_fix={}, created_by=a_clean.CREATED_BY)
    old = L.propose_issue(con, table_name="farm_survey", record_key="farm_survey:B", year=2024, issue_type="soil_misreport",
                          confidence=0.6, rule_id="r", explanation="", evidence={}, proposed_fix={}, created_by=a_clean.CREATED_BY)
    assert a_clean.retire_stale(con, [keep]) == 1
    assert [r[0] for r in con.execute("SELECT issue_id FROM issues").fetchall()] == [keep] and old != keep
