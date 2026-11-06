"""Tests for src/load.py. Key builders run everywhere; full-load tests skip when the pack is missing."""
from pathlib import Path

import pandas as pd
import pytest

from src import load


def test_record_keys_match_official_formats():
    erp = pd.DataFrame({"doc_no": ["0042"], "line_no": [3]})
    assert load.KEY_BUILDERS["erp_purchase_lines"](erp).tolist() == ["erp:0042:3"]
    em = pd.DataFrame({"site_id": ["S01"], "year": [2025], "month": [3], "carrier": ["electricity"]})
    assert load.KEY_BUILDERS["energy_meter_readings"](em).tolist() == ["energy:S01:2025-03:electricity"]
    ship = pd.DataFrame({"ref_doc": ["D9"], "ef_id": ["EF-SEA"]})
    assert load.KEY_BUILDERS["shipments"](ship).tolist() == ["ship:D9:EF-SEA"]
    pcf = pd.DataFrame({"supplier_id": ["SUP002"], "material_id": ["M101"], "year": [2024]})
    assert load.KEY_BUILDERS["supplier_pcfs"](pcf).tolist() == ["pcf:SUP002:M101:2024"]
    rep = pd.DataFrame({"year": [2025], "line": ["scope1"]})
    assert load.KEY_BUILDERS["draft_report_summary"](rep).tolist() == ["report:2025:scope1"]


def test_table_names_drop_year_suffixes():
    assert load.table_name("erp_purchase_lines_2021_2025") == "erp_purchase_lines"
    assert load.table_name("shipments") == "shipments"


@pytest.fixture(scope="module")
def loaded(tmp_path_factory):
    if not (load.pack_dir() / "data").is_dir():
        pytest.skip("data pack not available (set DATA_DIR)")
    con = load.connect(Path(tmp_path_factory.mktemp("db")) / "t.duckdb")
    return con, load.load_all(con)


def test_full_load_has_core_tables(loaded):
    con, counts = loaded
    for t in ["raw_erp_purchase_lines", "raw_farm_survey_fi", "raw_parcels", "raw_supplier_pcfs",
              "raw_foodhills_odlingsdata_se", "task_E_questions"]:
        assert counts[t] > 0, t
    assert counts["raw_weather_daily (view)"] > 4_000_000


def test_record_keys_present_and_foodhills_parsed(loaded):
    con, _ = loaded
    assert con.execute("SELECT count(*) FROM raw_erp_purchase_lines WHERE record_key IS NULL").fetchall()[0][0] == 0
    assert con.execute("SELECT min(record_key) FROM raw_farm_survey_fi").fetchall()[0][0].startswith("farm_survey:")
    # decimal commas parsed to numbers
    assert con.execute("SELECT typeof(areal_ha) FROM raw_foodhills_odlingsdata_se LIMIT 1").fetchall()[0][0] == "DOUBLE"
