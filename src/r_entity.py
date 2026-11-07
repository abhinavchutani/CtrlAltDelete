"""Retrieval layer (v2): entity view and lineage trace, answered inside AskOut (task #111).

    from src.r_entity import entity_view, lineage_trace
    entity_view(con, "S-SAK")                     # everything linked to one ID, per table
    lineage_trace(con, year=2024, scope="scope1") # a reported number → lines → records, factors, corrections

Run:  python -m src.r_entity S-SAK
      python -m src.r_entity --lineage 2024 scope1

From docs/DATA_INGESTION_AND_RETRIEVAL.md §3 ("the IDs do the linking") and §5.3 (entity and lineage views).
The pack shares stable IDs across files (site, supplier, material, farm, parcel, catchment, emission factor),
so the links are plain SQL joins on ID columns: no model, no guessing. Read-only on out/serve.duckdb
through src.r_sql; v1's tables are never written.
"""
from __future__ import annotations

import re
import sys

import duckdb

from src import r_sql as S

# ID pattern → (kind, ID column, master table, master name column)
ID_KINDS = (
    (re.compile(r"^F\d{4}-P\d{2}$"), "parcel", "parcel_id", "raw_parcels", None),
    (re.compile(r"^S-[A-Z]{2,4}$"), "site", "site_id", "raw_sites", "name"),
    (re.compile(r"^SUP\d{3}$"), "supplier", "supplier_id", "raw_suppliers", "supplier_name"),
    (re.compile(r"^M\d{3}$"), "material", "material_id", "raw_materials", "name_en"),
    (re.compile(r"^F\d{4}$"), "farm", "farm_id", "raw_farm_registry", "region"),
    (re.compile(r"^S\d{4}$"), "farm", "odlar_id", None, None),          # Swedish (Foodhills) grower
    (re.compile(r"^CA\d{1,3}$"), "catchment", "catchment_id", "raw_catchments", "region"),
    (re.compile(r"^EF-[A-Z0-9-]+$"), "emission factor", "ef_id", "raw_emission_factor_library", "name"),
)
ID_IN_TEXT = re.compile(r"\b(F\d{4}-P\d{2}|S-[A-Z]{2,4}|SUP\d{3}|M\d{3}|F\d{4}|S\d{4}|CA\d{1,3}|EF-[A-Z0-9-]+)\b", re.I)


def classify(entity_id: str) -> tuple[str, str, str | None, str | None] | None:
    eid = entity_id.upper()
    for pat, kind, col, master, name_col in ID_KINDS:
        if pat.match(eid):
            return kind, col, master, name_col
    return None


def tables_with(con: duckdb.DuckDBPyConnection, col: str) -> list[tuple[str, bool, bool]]:
    """(table, has_year, has_record_key) for every allow-listed table that has the ID column."""
    rows = con.execute("""SELECT table_name, bool_or(column_name = 'year'), bool_or(column_name = 'record_key'),
                                 bool_or(column_name = ?)
                          FROM information_schema.columns GROUP BY 1 ORDER BY 1""", [col]).fetchall()
    return [(t, y, k) for t, y, k, has in rows if has and S.allowed_table(t)]


def entity_view(con: duckdb.DuckDBPyConnection, entity_id: str) -> dict | None:
    """Rows, years, data-quality issues and corrections per table for one ID; None when the ID is unknown."""
    cls = classify(entity_id)
    if cls is None:
        return None
    kind, col, master, name_col = cls
    eid = entity_id.upper()
    name, rows, results = None, [], []
    if master and name_col:
        r = S.run_sql(f"SELECT {name_col} FROM {master} WHERE {col} = ?", [eid], con=con, max_rows=1)
        name = r["rows"][0][0] if r["rows"] else None
        results.append(r)   # the name is a tool result too (it can contain digits, e.g. "Supplier 073")
    for t, has_year, has_key in tables_with(con, col):
        yr = "min(year), max(year)" if has_year else "NULL, NULL"
        keyed = has_key
        sql = (f"SELECT count(*) AS n, {yr}"
               + (", (SELECT count(*) FROM issues i WHERE i.status = 'proposed' AND i.record_key IN (SELECT record_key FROM {t} WHERE {c} = ?))"
                  ", (SELECT count(*) FROM corrections k WHERE k.record_key IN (SELECT record_key FROM {t} WHERE {c} = ?))"
                  ", min(record_key)".format(t=t, c=col) if keyed else ", NULL, NULL, NULL")
               + f" FROM {t} WHERE {col} = ?")
        res = S.run_sql(sql, [eid, eid, eid] if keyed else [eid], con=con, max_rows=1)
        n, y0, y1, n_iss, n_corr, example = res["rows"][0]
        if n:
            results.append(res)
            rows.append([t, col, n, f"{y0}–{y1}" if y0 is not None else "", n_iss, n_corr, example])
    if not rows:
        return {"id": eid, "kind": kind, "name": name, "rows": [], "results": results}
    issues = S.run_sql(f"""SELECT issue_type, status, count(*) AS n FROM issues WHERE record_key IN (
                               {' UNION ALL '.join(f'SELECT record_key FROM {r[0]} WHERE {col} = ?' for r in rows if r[6])} )
                           GROUP BY 1, 2 ORDER BY 3 DESC, 1""",
                       [eid] * sum(1 for r in rows if r[6]), con=con) if any(r[6] for r in rows) else None
    if issues:
        results.append(issues)
    return {"id": eid, "kind": kind, "name": name, "rows": rows, "results": results,
            "issue_types": [[t, n] for t, st, n in (issues["rows"] if issues else []) if st == "proposed"],
            # checked and ruled legitimate by the allow-list (credit notes, TO lots, ammonia systems): not errors
            "legitimate": [[t, n] for t, st, n in (issues["rows"] if issues else []) if st == "legitimate"]}


def lineage_trace(con: duckdb.DuckDBPyConnection, *, result_id: str | None = None, year: int | None = None,
                  scope: str | None = None, limit_lines: int = 12) -> dict | None:
    """A reported total → its line results → the source records and factors, with corrections on those records."""
    if result_id:
        top = S.run_sql("SELECT result_id, metric, scope, category, year, value, unit, status FROM results "
                        "WHERE result_id = ?", [result_id], con=con)
    else:
        top = S.run_sql("""SELECT result_id, metric, scope, category, year, value, unit, status FROM results
                           WHERE metric = 'tco2e' AND year = ? AND scope = ? ORDER BY value DESC""", [year, scope], con=con)
    if not top["rows"]:
        return None
    ids = [r[0] for r in top["rows"]]
    ph = ",".join("?" * len(ids))
    lines = S.run_sql(f"""SELECT r.result_id, round(r.value, 3) AS t_co2e, r.status
                          FROM lineage l JOIN results r ON r.result_id = l.source_ref
                          WHERE l.result_id IN ({ph}) AND l.source_kind = 'doc' ORDER BY r.value DESC""", ids, con=con)
    line_ids = [r[0] for r in lines["rows"]] or ids
    lph = ",".join("?" * len(line_ids))
    sources = S.run_sql(f"""SELECT l.result_id, l.source_kind, l.source_ref, l.note FROM lineage l
                            WHERE l.result_id IN ({lph}) AND l.source_kind IN ('record', 'factor', 'model')
                            ORDER BY l.result_id, l.source_kind, l.source_ref""", line_ids, con=con, max_rows=2000)
    rec = [r[2] for r in sources["rows"] if r[1] == "record"]
    corr = S.run_sql(f"""SELECT record_key, field, old_value, new_value, reason, approved_by FROM corrections
                         WHERE record_key IN ({','.join('?' * len(rec))}) ORDER BY record_key""", rec, con=con) \
        if rec else {"rows": [], "columns": [], "tables": ["corrections"], "source_files": {}, "record_keys": [],
                     "sql": "", "params": [], "n_rows": 0, "truncated": False}
    by_line: dict[str, dict] = {}
    for rid, kind, ref, _ in sources["rows"]:
        d = by_line.setdefault(rid, {"record": 0, "factor": [], "model": 0})
        if kind == "factor":
            d["factor"].append(ref)
        else:
            d[kind] += 1
    corrected = {r[0] for r in corr["rows"]}
    table_rows = []
    for rid, t, status in (lines["rows"] or [[r[0], round(r[5], 3), r[7]] for r in top["rows"]])[:limit_lines]:
        d = by_line.get(rid, {"record": 0, "factor": [], "model": 0})
        n_corr = sum(1 for r in sources["rows"] if r[0] == rid and r[1] == "record" and r[2] in corrected)
        table_rows.append([rid, t, status, d["record"], ", ".join(d["factor"][:3]), n_corr])
    return {"top": top, "lines": lines, "sources": sources, "corrections": corr, "table_rows": table_rows,
            "n_records": len(set(rec)), "n_corrected": len(corrected)}


def main() -> None:
    import json
    con = S.connect()
    if len(sys.argv) > 1 and sys.argv[1] == "--lineage":
        out = lineage_trace(con, year=int(sys.argv[2]), scope=sys.argv[3])
        print(json.dumps(out["table_rows"] if out else None, default=str, indent=1))
    else:
        out = entity_view(con, sys.argv[1] if len(sys.argv) > 1 else "S-SAK")
        print(json.dumps({k: v for k, v in (out or {}).items() if k != "results"}, default=str, indent=1))


if __name__ == "__main__":
    main()
