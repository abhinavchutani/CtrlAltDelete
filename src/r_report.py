"""Retrieval layer (v2): Excel reports with a Sources sheet (task #92, V2-10).

    from src.r_report import make_report
    make_report(con, "energy_by_site_month", {"year": 2024})
    # → {"report_id": "energy_by_site_month-1a2b3c4d5e", "filename": "...xlsx", "url": "/api/report/<id>"}

Run:  python -m src.r_report energy_by_site_month year=2024

Every report is one read-only query (src.r_sql: SELECT only, allow-listed tables) written to
out/v2/reports/{report_id}.xlsx with two sheets:
* "Data": the rows, as the query returned them (no number is typed by hand or by an LLM);
* "Sources": the query, its parameters, tables, pack files, record keys, generated-at, the git SHA and the
  synthetic-data note, so anyone can rerun the query and get the same rows.
The report id is a hash of the template and its parameters, so the same request always gets the same id.
Templates: deliveries_by_farm_year, energy_by_site_month, farm_yield_history, inventory_summary, export_query.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import duckdb
from openpyxl import Workbook
from openpyxl.styles import Font

from src import r_sql as S
from src.db import REPO_ROOT, git_sha

REPORT_DIR = REPO_ROOT / "out" / "v2" / "reports"
REPORT_MAX_ROWS = 50_000
ID_RE = re.compile(r"^[a-z_]+-[0-9a-f]{10}$")
SYNTHETIC_NOTE = ("Synthetic data from the hackathon twin (Apetit × SinceAI 2026). Not Apetit's real figures and "
                  "not facts about real farms.")


@dataclass(frozen=True)
class Template:
    title: str
    build: Callable[[dict], tuple[str, list]]   # params → (sql, sql params)


def _deliveries(p: dict) -> tuple[str, list]:
    """Finnish survey production (area × yield after the data review) and Swedish delivered tonnes, per farm × year."""
    crop = p.get("crop", "pea")
    years = [int(y) for y in p.get("years", [])]
    yr = f"AND year IN ({','.join('?' * len(years))})" if years else ""
    yr_se = f"AND skördeår IN ({','.join('?' * len(years))})" if years else ""
    sv = {"pea": "Ärt%", "potato": "Potatis%", "carrot": "Morot%", "spinach": "Spenat%"}.get(crop, f"{crop}%")
    region = p.get("region", "all")
    parts, args = [], []
    if region in ("all", "FI_SW"):
        parts.append(f"""SELECT 'FI_SW' AS region, farm_id, year, crop, round(area_ha, 2) AS area_ha,
                                round(yield_t_ha, 3) AS yield_t_ha, round(area_ha * yield_t_ha, 2) AS delivered_t,
                                corrected_fields IS NOT NULL AND corrected_fields <> '' AS corrected, record_key
                         FROM clean_farm_survey WHERE crop = ? {yr}""")
        args += [crop, *years]
    if region in ("all", "SE_SKANE"):
        parts.append(f"""SELECT 'SE_SKANE' AS region, odlar_id AS farm_id, skördeår AS year, ? AS crop,
                                round(areal_ha, 2) AS area_ha, round(levererad_mängd_ton / areal_ha, 3) AS yield_t_ha,
                                round(levererad_mängd_ton, 2) AS delivered_t, FALSE AS corrected,
                                'foodhills:' || odlar_id || ':' || skördeår AS record_key
                         FROM raw_foodhills_odlingsdata_se WHERE gröda LIKE ? {yr_se}""")
        args += [crop, sv, *years]
    return " UNION ALL ".join(parts) + " ORDER BY region, year, farm_id", args


def _energy(p: dict) -> tuple[str, list]:
    from src.r_agent import ENERGY_SQL
    y = int(p.get("year", 2024))
    return ENERGY_SQL, [y, y]


def _farm_yield(p: dict) -> tuple[str, list]:
    return ("""SELECT farm_id, year, crop, area_ha, yield_t_ha, corrected_fields, record_key FROM clean_farm_survey
               WHERE farm_id = ? ORDER BY year, crop""", [str(p["farm_id"]).upper()])


def _inventory(p: dict) -> tuple[str, list]:
    years = [int(y) for y in p.get("years", [2023, 2024, 2025])]
    return (f"""SELECT year, scope, category, round(value, 3) AS t_co2e, unit, status, result_id FROM results
                WHERE metric = 'tco2e' AND year IN ({','.join('?' * len(years))}) ORDER BY year, scope, category""", years)


TEMPLATES: dict[str, Template] = {
    "deliveries_by_farm_year": Template("Deliveries by farm and year", _deliveries),
    "energy_by_site_month": Template("Energy use by site and month (MWh)", _energy),
    "farm_yield_history": Template("Farm yield history", _farm_yield),
    "inventory_summary": Template("Emissions inventory summary (t CO2e)", _inventory),
}


def report_id(template: str, params: dict, sql: str | None = None) -> str:
    key = json.dumps({"t": template, "p": params, "sql": sql}, sort_keys=True, default=str)
    return f"{template}-{hashlib.sha1(key.encode()).hexdigest()[:10]}"


def path_for(rid: str) -> Path | None:
    """The file for a report id, or None (ids are validated, so no path tricks)."""
    if not ID_RE.match(rid):
        return None
    p = REPORT_DIR / f"{rid}.xlsx"
    return p if p.is_file() else None


def _slug(params: dict) -> str:
    vals = [str(v) if not isinstance(v, list) else "-".join(map(str, v)) for _, v in sorted(params.items())]
    return re.sub(r"[^A-Za-z0-9-]+", "_", "_".join(vals))[:40].strip("_")


def _plain(v):
    """Excel-native cell values: DuckDB DECIMAL → float (stays a number), dates stay dates, the rest as text."""
    from datetime import date
    from decimal import Decimal
    if isinstance(v, Decimal):
        return float(v)
    return v if isinstance(v, (int, float, str, bool, date)) or v is None else str(v)


def write_xlsx(path: Path, title: str, res: dict, meta: list[tuple[str, str]]) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Data"
    ws.append(res["columns"])
    for c in ws[1]:
        c.font = Font(bold=True)
    for r in res["rows"]:
        ws.append([_plain(v) for v in r])
    ws.freeze_panes = "A2"
    src = wb.create_sheet("Sources")
    src.append(["field", "value"])
    for c in src[1]:
        c.font = Font(bold=True)
    for k, v in [("report", title), *meta]:
        src.append([k, v])
    src.column_dimensions["A"].width = 18
    src.column_dimensions["B"].width = 110
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)


def make_report(con: duckdb.DuckDBPyConnection | None, template: str, params: dict | None = None, *,
                sql: str | None = None, tables: list[str] | None = None, params_list: list | None = None) -> dict:
    """Run the template's query (or, for export_query, the given SELECT) and write the .xlsx. Returns the ReportRef."""
    params = dict(params or {})
    if template == "export_query":
        if not sql:
            raise ValueError("export_query needs sql")
        title, q, args = "Query export", sql, list(params_list or [])
    elif template in TEMPLATES:
        t = TEMPLATES[template]
        title, (q, args) = t.title, t.build(params)
    else:
        raise ValueError(f"unknown report template {template!r}; known: {', '.join([*TEMPLATES, 'export_query'])}")
    res = S.run_sql(q, args, con=con, max_rows=REPORT_MAX_ROWS)
    rid = report_id(template, params, sql if template == "export_query" else None)
    keys = [str(r[res["columns"].index("record_key")]) for r in res["rows"]] if "record_key" in res["columns"] else []
    meta = [
        ("report_id", rid), ("template", template), ("parameters", json.dumps(params, default=str)),
        ("generated_at", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")), ("code_version", git_sha()),
        ("query", res["sql"]), ("query_parameters", json.dumps(res["params"], default=str)),
        ("tables", ", ".join(res["tables"])),
        ("pack_files", "; ".join(f"{t} ← {f}" for t, f in res["source_files"].items()) or "derived tables only"),
        ("rows", str(res["n_rows"]) + (" (truncated)" if res["truncated"] else "")),
        ("record_keys", ", ".join(keys[:500]) + (" …" if len(keys) > 500 else "") if keys else "n/a"),
        ("how_to_rerun", "python -m src.r_report " + template + " " + " ".join(f"{k}={v}" for k, v in params.items())),
        ("approval", "Draft: numbers use proposed corrections pending expert approval where marked."),
        ("note", SYNTHETIC_NOTE),
    ]
    filename = f"{template}_{_slug(params)}.xlsx" if params else f"{template}.xlsx"
    write_xlsx(REPORT_DIR / f"{rid}.xlsx", title, res, meta)
    return {"report_id": rid, "filename": filename, "url": f"/api/report/{rid}"}


def main(argv: list[str] | None = None) -> None:
    args = argv if argv is not None else sys.argv[1:]
    template = args[0] if args else "energy_by_site_month"
    params: dict = {}
    for a in args[1:]:
        k, _, v = a.partition("=")
        params[k] = [x for x in v.split(",")] if "," in v else v
    ref = make_report(S.connect(), template, params)
    print(json.dumps(ref), "→", REPORT_DIR / f"{ref['report_id']}.xlsx")


if __name__ == "__main__":
    main()
