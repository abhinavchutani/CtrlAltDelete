"""Tests for detectors part 1 (src/a_detect/ops.py). Data tests skip without the pack."""
import os

import pytest

from src import a_clean, load
from src.a_detect import ops
from src.a_score import dev_labels, score_a1
from src.db import connect


@pytest.fixture(scope="module")
def con(tmp_path_factory):
    if not (load.pack_dir() / "data").is_dir():
        pytest.skip("data pack not available (set DATA_DIR)")
    os.environ["NAVIGATOR_DEV_ASSUME"] = "1"
    c = connect(tmp_path_factory.mktemp("db") / "t.duckdb")
    load.load_all(c)
    return c


def test_fx_matches_pack_factors():
    assert ops.FX_PER_EUR == {"EUR": 1.0, "SEK": 11.4, "USD": 1.08}


def test_ops_dev_score_and_allow_list(con):
    cands = ops.detect_all(con)
    legit = cands[cands.status == "legitimate"]
    assert len(legit) > 0 and set(legit.rule_id) >= {"allow_credit_note_or_tonne_lot", "allow_real_ammonia_system"}
    flagged = cands[cands.status == "proposed"]
    # credit notes and ammonia-on-ammonia systems are never flagged
    raw = con.execute("SELECT record_key FROM raw_erp_purchase_lines WHERE movement_type = 122").df()
    assert not set(raw.record_key) & set(flagged.record_key)
    tables = ["erp_purchase_lines", "energy_meter_readings", "fuel_deliveries", "goo_cancellations", "refrigerant_service_log"]
    s = score_a1(flagged, dev_labels(con), restrict_tables=tables)
    assert s["score"] >= 95 and s["precision"] >= 0.95, s


def test_pipeline_applies_only_proposed_fixes(con):
    from src import lineage as L
    L.init_schema(con)
    a_clean.propose_and_assume(con)
    n_legit_corrected = con.execute("""SELECT count(*) FROM corrections c JOIN issues i USING (issue_id)
                                       WHERE i.status = 'legitimate'""").fetchall()[0][0]
    assert n_legit_corrected == 0
