"""Tests for src/r_catalog.py. Unit tests use a tiny in-memory DuckDB; one test skips without the real db."""
from __future__ import annotations

import json
import os
from pathlib import Path

import duckdb
import pytest

from src import r_catalog as rc

DICT = """# Data dictionary

## `02_raw_feeds/erp_purchase_lines_2021_2025.csv`

ERP purchase lines (goods receipts / invoices). Raw.

Rows: 3

| Column | Type | Example | Description |
|---|---|---|---|
| `doc_no` | int64 | 45 | Document number |
| `supplier_id` | str | SUP002 | Supplier or contract farm |
| `quantity` | float64 | 1.0 | Quantity in `uom` |

## `02_raw_feeds/energy_meter_readings.csv`

Monthly meter readings (electricity, purchased steam) per site.

| Column | Type | Example | Description |
|---|---|---|---|
| `site_id` | str | S-SAK | Site |
| `month` | int64 | 1 | Month |

## `03_farming/foodhills_odlingsdata_se.csv`

Foodhills (SE) grower data 2018-2026 in the acquired company's format: Swedish headers.

| Column | Type | Example | Description |
|---|---|---|---|
| `odlar_id` | str | S0381 | Grower id |
| `skördeår` | int64 | 2018 | Harvest year |
| `gröda` | str | Ärt (frysärt) | Crop |
| `levererad_mängd_ton` | str | 14,91 | Delivered (t) |

## Other files

| File | Format | Content |
|---|---|---|
| `04_climate/weather_daily_1991_2060.parquet` | Parquet | Daily weather per cell |
"""


@pytest.fixture()
def con() -> duckdb.DuckDBPyConnection:
    c = duckdb.connect(":memory:")
    c.execute("CREATE TABLE raw_erp_purchase_lines AS SELECT * FROM (VALUES "
              "('erp:1:10', '1', 'SUP1', 2.0, 2021), ('erp:2:10', '2', 'SUP2', 3.0, 2024)) "
              "t(record_key, doc_no, supplier_id, quantity, year)")
    c.execute("CREATE TABLE raw_energy_meter_readings AS SELECT * FROM (VALUES "
              "('S-SAK', 2019, 1, 10.0), ('S-SAK', 2020, 2, 11.0)) t(site_id, year, month, value)")
    c.execute("CREATE TABLE raw_foodhills_odlingsdata_se AS SELECT * FROM (VALUES "
              "('S0381', 2018, 'Ärt (frysärt)', '14,91'), ('S0382', 2025, 'Ärt (frysärt)', '9,10')) "
              "t(odlar_id, skördeår, gröda, levererad_mängd_ton)")
    c.execute("CREATE TABLE results AS SELECT 'r1' AS result_id, 'scope1' AS metric, 2025 AS year, 1.0 AS value")
    c.execute("CREATE VIEW raw_weather_daily AS SELECT 'GF0' AS cell_id, DATE '2020-01-01' AS date")
    c.execute("CREATE TABLE task_E_questions AS SELECT 1 AS q")  # not in the allow-list
    return c


@pytest.fixture()
def cards(con: duckdb.DuckDBPyConnection, tmp_path: Path) -> list[dict]:
    path = tmp_path / "DATA_DICTIONARY.md"
    path.write_text(DICT, encoding="utf-8")
    return rc.build_cards(con, path)


def by_table(cards: list[dict]) -> dict[str, dict]:
    return {c["table"]: c for c in cards}


def test_allow_list_and_kinds(cards: list[dict]) -> None:
    t = by_table(cards)
    assert set(t) == {"raw_erp_purchase_lines", "raw_energy_meter_readings", "results", "raw_weather_daily",
                      "raw_foodhills_odlingsdata_se"}
    assert t["raw_erp_purchase_lines"]["kind"] == "raw" and t["results"]["kind"] == "results"


def test_raw_card_fields(cards: list[dict]) -> None:
    erp = by_table(cards)["raw_erp_purchase_lines"]
    assert erp["source_file"] == "02_raw_feeds/erp_purchase_lines_2021_2025.csv"
    assert erp["description"].startswith("ERP purchase lines")
    cols = {c["name"]: c for c in erp["columns"]}
    assert cols["supplier_id"]["description"] == "Supplier or contract farm"
    assert cols["record_key"]["description"] is None
    assert erp["row_count"] == 2 and erp["years"] == [2021, 2024]
    assert erp["key_columns"] == ["record_key", "doc_no", "supplier_id"]


def test_derived_and_view_cards(cards: list[dict]) -> None:
    t = by_table(cards)
    assert t["results"]["source_file"] is None and "draft" in t["results"]["description"]
    assert t["results"]["years"] == [2025, 2025] and t["results"]["key_columns"] == ["result_id"]
    w = t["raw_weather_daily"]
    assert w["row_count"] is None and w["years"] is None
    assert w["source_file"] == "04_climate/weather_daily_1991_2060.parquet"


def test_search_ranks_expected_table_first(cards: list[dict]) -> None:
    res = rc.catalog_search("energy meter readings per site per month", cards=cards)
    assert res["query"].startswith("energy") and res["tables"][0]["table"] == "raw_energy_meter_readings"
    top = rc.catalog_search("supplier purchase lines", k=1, cards=cards)["tables"]
    assert len(top) == 1 and top[0]["table"] == "raw_erp_purchase_lines"
    assert {"table", "description", "columns", "years", "source_file", "score"} <= set(top[0])
    assert rc.catalog_search("zzzz", cards=cards)["tables"] == []


def test_swedish_foodhills_found_via_tags_and_synonyms(cards: list[dict]) -> None:
    fh = by_table(cards)["raw_foodhills_odlingsdata_se"]
    assert "foodhills" in fh["tags"] and fh["years"] == [2018, 2025] and fh["key_columns"] == ["odlar_id"]
    assert by_table(cards)["results"]["tags"] == []
    hits = rc.catalog_search("pea deliveries from Swedish farms", cards=cards)["tables"]
    assert hits[0]["table"] == "raw_foodhills_odlingsdata_se"
    assert "ärt" in rc.expand(rc.tokens("pea")) and "levererad" in rc.expand(rc.tokens("deliveries"))


def test_search_is_deterministic(cards: list[dict]) -> None:
    assert rc.catalog_search("site year", cards=cards) == rc.catalog_search("site year", cards=list(cards))


def test_write_catalog(cards: list[dict], tmp_path: Path) -> None:
    path = rc.write_catalog(cards, tmp_path / "v2" / "catalog.json")
    assert json.loads(path.read_text(encoding="utf-8")) == cards


def test_real_db() -> None:
    found = [p for p in (os.environ.get("SERVE_DB"), rc.REPO_ROOT / "out" / "serve.duckdb", "/tmp/w80.duckdb")
             if p and Path(p).is_file()]
    if not found:
        pytest.skip("serve database not available (set SERVE_DB)")
    with duckdb.connect(str(found[0]), read_only=True) as c:
        cards = rc.build_cards(c)
    t = by_table(cards)
    assert "raw_erp_purchase_lines" in t and "results" in t
    if t["raw_erp_purchase_lines"]["description"] is None:
        pytest.skip("data dictionary not available (set DATA_DIR)")
    hit = rc.catalog_search("energy per site per month", cards=cards)["tables"][0]
    assert hit["table"] == "raw_energy_meter_readings"
    if "raw_foodhills_odlingsdata_se" in t:
        pea = rc.catalog_search("pea deliveries from Swedish farms", cards=cards)["tables"][0]
        assert pea["table"] == "raw_foodhills_odlingsdata_se"
