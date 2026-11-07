"""r_sql safety: write statements, file reads and non-allow-listed tables are refused (no data needed)."""
import duckdb
import pytest

from src import r_sql as R


@pytest.fixture()
def con(tmp_path):
    p = tmp_path / "serve.duckdb"
    c = duckdb.connect(str(p))
    c.execute("CREATE TABLE raw_erp_purchase_lines AS SELECT 'erp:1' AS record_key, 2024 AS year, 10.0 AS qty "
              "UNION ALL SELECT 'erp:2', 2025, 5.0")
    c.execute("CREATE TABLE results AS SELECT 'A2:2024' AS result_id, 1.5 AS value")
    c.execute("CREATE TABLE secrets AS SELECT 42 AS x")
    c.close()
    ro = duckdb.connect(str(p), read_only=True)
    yield ro
    ro.close()


def test_select_returns_rows_tables_and_record_keys(con):
    out = R.run_sql("SELECT record_key, qty FROM raw_erp_purchase_lines WHERE year = ? ORDER BY 1", [2024], con=con)
    assert out["rows"] == [["erp:1", 10.0]] and out["tables"] == ["raw_erp_purchase_lines"]
    assert out["record_keys"] == ["erp:1"] and not out["truncated"]


@pytest.mark.parametrize("sql", [
    "DELETE FROM results", "INSERT INTO results VALUES ('x', 1)", "DROP TABLE results",
    "UPDATE results SET value = 0", "CREATE TABLE t AS SELECT 1", "ATTACH 'x.db'", "COPY results TO 'x.csv'",
    "SELECT 1; DROP TABLE results", "PRAGMA database_list", "SELECT * FROM read_csv('/etc/passwd')",
    "SELECT * FROM secrets", "WITH s AS (SELECT * FROM secrets) SELECT * FROM s",
])
def test_unsafe_statements_are_refused(con, sql):
    with pytest.raises(R.SqlRefused):
        R.run_sql(sql, con=con)
    assert con.execute("SELECT count(*) FROM results").fetchall() == [(1,)]


def test_keywords_inside_strings_and_comments_are_fine(con):
    out = R.run_sql("-- delete me\nSELECT 'drop table' AS note, value FROM results", con=con)
    assert out["rows"] == [["drop table", 1.5]]


def test_row_cap(con):
    out = R.run_sql("SELECT * FROM raw_erp_purchase_lines", con=con, max_rows=1)
    assert out["n_rows"] == 1 and out["truncated"]


def test_read_only_connection_blocks_writes_even_if_check_were_bypassed(con):
    with pytest.raises(duckdb.Error):
        con.execute("DELETE FROM results")
