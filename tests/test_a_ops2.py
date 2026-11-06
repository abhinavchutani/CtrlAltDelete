"""Tests for detectors part 2 (src/a_detect/ops2.py). Data tests skip without the pack."""
import os

import pytest

from src import load
from src.a_detect import farm, ops, ops2
from src.a_score import dev_labels, score_a1
from src.db import connect

import pandas as pd


@pytest.fixture(scope="module")
def con(tmp_path_factory):
    if not (load.pack_dir() / "data").is_dir():
        pytest.skip("data pack not available (set DATA_DIR)")
    os.environ["NAVIGATOR_DEV_ASSUME"] = "1"
    c = connect(tmp_path_factory.mktemp("db") / "t.duckdb")
    load.load_all(c)
    return c


def test_mode_codes_and_map():
    assert "henkilöauto" not in ops2.MODE_CODES and ops2.MODE_MAP["linja-auto"] == "bus"


def test_ops2_dev_score(con):
    c = ops2.detect_all(con)
    tables = ["travel_bookings", "shipments", "waste_transfer_notes", "supplier_pcfs", "draft_report_summary", "commuting_survey"]
    s = score_a1(c, dev_labels(con), restrict_tables=tables)
    assert s["score"] >= 95, s


def test_hidden_year_checks_fire(con):
    c = ops2.detect_all(con)
    types = set(c.issue_type)
    assert {"pcf_unit_error", "pcf_stale_period", "total_mismatch", "mode_mislabel"} <= types
    assert c[c.issue_type == "missing_leg"].record_key.str.match(r"ship:\d+:EF-TKM-(SHIP-(BULK|REEFER)|ROPAX)$").all()


def test_all_dev_labels_meet_end_goal_bar(con):
    allc = pd.concat([farm.detect_all(con), ops.detect_all(con), ops2.detect_all(con)], ignore_index=True)
    allc["status"] = allc["status"].fillna("proposed")
    s = score_a1(allc[allc.status == "proposed"], dev_labels(con))
    assert s["score"] >= 90, s  # END_GOAL G2: A1 ≥ 80
