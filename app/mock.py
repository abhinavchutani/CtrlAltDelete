"""Seeded MOCK rows in the four shared tables, so the app renders before real outputs exist.

Written to a separate file (out/mock.duckdb) through the normal lineage API. Every value is fake,
tagged `MOCK` in `method`, and stays `draft`. Nothing here is a result, real or synthetic.

    python -m app.mock          # (re)build out/mock.duckdb
"""
from __future__ import annotations

import numpy as np

from src import lineage as L
from src.db import REPO_ROOT, connect

MOCK_DB = REPO_ROOT / "out" / "mock.duckdb"
METHOD = "MOCK placeholder (app/mock.py)"
BY = "app.mock"

ISSUE_TYPES = ["unit_error", "duplicate_record", "meter_spike", "soil_misreport", "certificate_mismatch",
               "missing_leg", "pcf_stale_period", "wrong_gas_code"]
LEGIT = [("erp_purchase_lines", "credit note (movement 122)"), ("erp_purchase_lines", "vessel lot in tonnes (uom TO)"),
         ("energy_meter_readings", "seasonal harvest peak"), ("refrigerant_service_log", "R717 ammonia system (GWP 0)")]
SCOPES = [("scope1", "stationary_and_mobile_combustion"), ("scope1", "fugitive_refrigerants"), ("scope2_location", "purchased_electricity"),
          ("scope2_market", "purchased_electricity"), ("scope3", "cat01_purchased_goods_services"), ("scope3", "cat04_upstream_transport"), ("scope3", "cat05_waste"), ("scope3", "cat06_business_travel"), ("scope3", "cat07_employee_commuting")]
CROPS = ["pea", "potato", "turnip_rape", "wheat"]
REGIONS = ["FI_southwest", "SE_skane"]
SSPS = ["ssp126", "ssp245", "ssp585"]


def seed(path=MOCK_DB) -> None:
    rng = np.random.default_rng(7)
    path.unlink(missing_ok=True)
    con = connect(path)
    L.init_schema(con)

    for i in range(40):
        t = ISSUE_TYPES[i % len(ISSUE_TYPES)]
        key = f"erp:MOCK{i:04d}:1" if t != "soil_misreport" else f"farm_survey:MOCK{i:04d}"
        L.propose_issue(con, table_name="mock", record_key=key, year=2025, issue_type=t,
                        confidence=round(float(rng.uniform(0.5, 0.89)), 2), rule_id=f"mock_{t}",
                        explanation=f"MOCK {t.replace('_', ' ')} example (display only)",
                        evidence={"mock": True, "ratio": round(float(rng.uniform(2, 1000)), 1)},
                        proposed_fix=None, created_by=BY)  # no fix: the correctable MOCK errors are the lines below
    for i, (table, why) in enumerate(LEGIT):
        L.propose_issue(con, table_name=table, record_key=f"mock:legit:{i}", year=2025, issue_type="observation",
                        confidence=1.0, rule_id="allow_list", explanation=f"checked, legitimate: {why}",
                        evidence={"mock": True}, proposed_fix=None, created_by=BY, status="legitimate")

    # Same shape as Track A's inventory (#44): line items (tco2e_line) → category rows → scope totals
    totals: dict[str, float] = {}
    for scope, cat in SCOPES:
        line_ids = []
        for j in range(2):
            lid = f"MOCK:A2:2025:actual:{scope}:{cat}:line{j}"
            v = round(float(rng.uniform(25, 2500)))
            L.write_result(con, lid, metric="tco2e_line", value=v, unit="t CO2e", scope=scope, category=cat,
                           year=2025, method=METHOD, produced_by=BY,
                           lineage=[L.src("record", f"mockline:{scope}:{cat}:{j}"), L.src("factor", f"EF-MOCK-{cat}")])
            line_ids.append((lid, v))
            if j == 0 and len(line_ids) and scope in ("scope1", "scope3"):  # a correctable MOCK error per category
                L.propose_issue(con, table_name="mock", record_key=f"mockline:{scope}:{cat}:{j}", year=2025,
                                issue_type="unit_error", confidence=0.95, rule_id="mock_line_x10",
                                explanation=f"MOCK: {cat} line keyed ×10", evidence={"mock": True, "value": v},
                                proposed_fix={"field": "tco2e", "old_value": v, "new_value": round(v / 10, 1)},
                                created_by=BY)
        value = sum(v for _, v in line_ids)
        totals[scope] = totals.get(scope, 0.0) + value
        L.write_result(con, f"MOCK:A2:2025:actual:{scope}:{cat}", metric="tco2e", value=value, unit="t CO2e",
                       scope=scope, category=cat, year=2025, method=METHOD, produced_by=BY,
                       lineage=[L.src("doc", lid) for lid, _ in line_ids])
    for scope, value in totals.items():
        L.write_result(con, f"MOCK:A2:2025:actual:{scope}_total", metric="tco2e", value=value, unit="t CO2e",
                       scope="total", category=f"{scope}_total", year=2025, method=METHOD, produced_by=BY,
                       lineage=[L.src("doc", "sum of category rows (mock)")])
    L.write_result(con, "MOCK:A2:2025:actual:biogenic_co2_scope1", metric="tco2e", value=round(float(rng.uniform(100, 900))),
                   unit="t CO2e", scope="memo", category="biogenic_co2_scope1", year=2025, method=METHOD,
                   produced_by=BY, lineage=[L.src("doc", "METHODOLOGY.md#3")])

    for farm in [f"F{n:04d}" for n in range(1, 13)]:
        mineral = round(float(rng.uniform(100, 400)))
        peat = round(float(rng.choice([0, 0, 0, rng.uniform(50, 600)])))
        for variant, val in [("mineral_only", mineral), ("with_organic_soils", mineral + peat)]:
            L.write_result(con, f"MOCK:farm:{farm}:{variant}", metric="farm_tco2e", value=val, unit="t CO2e",
                           category=farm, year=2025, scenario=variant, method=METHOD, produced_by=BY,
                           lineage=[L.src("record", f"farm_survey:MOCK-{farm}"), L.src("doc", "METHODOLOGY.md#5")])

    for ssp_i, ssp in enumerate(SSPS):
        for region in REGIONS:
            for crop in CROPS:
                cat = f"{region}:{crop}"
                d = -float(rng.uniform(0, 4)) * (ssp_i + 1)
                for metric, val, unit in [("yield_change_pct", round(d, 1), "%"),
                                          ("p_bad_year", round(min(0.6, 0.1 + abs(d) / 40), 2), "share"),
                                          ("eur_at_risk", round(abs(d) * float(rng.uniform(1e4, 5e4)), -3), "EUR/yr")]:
                    L.write_result(con, f"MOCK:C2:{ssp}:{cat}:{metric}", metric=metric, value=val, unit=unit,
                                   category=cat, year=2050, scenario=ssp, method=METHOD, produced_by=BY,
                                   lineage=[L.src("model", "mock_yield_model"), L.src("doc", "climate_change_signals.csv")])
    for i, (action, owner) in enumerate([("Irrigation on drought-exposed fields", "contract farming"),
                                         ("Earlier sowing window", "field advisors"),
                                         ("Two-region pea sourcing", "procurement")]):
        L.write_result(con, f"MOCK:C3:adapt:{i}", metric="eur_saved", value=round(float(rng.uniform(5e4, 3e5)), -3),
                       unit="EUR/yr", category=f"{action} | owner: {owner}", year=2050, scenario="ssp245",
                       method=METHOD, produced_by=BY, lineage=[L.src("model", "mock_euro_model")])
    con.close()


def recalculate(con) -> None:
    """MOCK recalculation: human-approved 'tco2e' corrections replace their line's value, then categories
    and totals are re-summed (all rewritten rows go back to draft via write_result)."""
    fixes = dict(con.execute("SELECT record_key, new_value FROM corrections WHERE field = 'tco2e' "
                             "AND approved_by <> 'DEV-ASSUMED'").fetchall())
    lines = con.execute("""SELECT r.result_id, r.scope, r.category, r.value, l.source_ref AS rec FROM results r
                           JOIN lineage l USING (result_id)
                           WHERE r.metric = 'tco2e_line' AND l.source_kind = 'record'""").df()
    totals: dict[str, float] = {}
    for (scope, cat), g in lines.groupby(["scope", "category"], sort=False):
        ids = []
        for r in g.itertuples(index=False):
            v = float(fixes[r.rec]) if r.rec in fixes else r.value
            if v != r.value:
                L.write_result(con, r.result_id, metric="tco2e_line", value=v, unit="t CO2e", scope=scope,
                               category=cat, year=2025, method=METHOD + " + approved correction", produced_by=BY,
                               lineage=[L.src("record", r.rec), L.src("correction", f"corr:mock_line_x10:{r.rec}"),
                                        L.src("factor", f"EF-MOCK-{cat}")])
            ids.append((r.result_id, v))
        value = sum(v for _, v in ids)
        totals[scope] = totals.get(scope, 0.0) + value
        rid = f"MOCK:A2:2025:actual:{scope}:{cat}"
        if abs(con.execute("SELECT value FROM results WHERE result_id = ?", [rid]).fetchone()[0] - value) > 1e-9:
            L.write_result(con, rid, metric="tco2e", value=value, unit="t CO2e", scope=scope, category=cat,
                           year=2025, method=METHOD, produced_by=BY, lineage=[L.src("doc", i) for i, _ in ids])
    for scope, value in totals.items():
        rid = f"MOCK:A2:2025:actual:{scope}_total"
        if abs(con.execute("SELECT value FROM results WHERE result_id = ?", [rid]).fetchone()[0] - value) > 1e-9:
            L.write_result(con, rid, metric="tco2e", value=value, unit="t CO2e", scope="total",
                           category=f"{scope}_total", year=2025, method=METHOD, produced_by=BY,
                           lineage=[L.src("doc", "sum of category rows (mock)")])


if __name__ == "__main__":
    seed()
    print(f"mock tables → {MOCK_DB}")
