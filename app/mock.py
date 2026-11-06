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
SCOPES = [("1", "stationary_combustion"), ("1", "refrigerants"), ("2_location", "electricity"),
          ("2_market", "electricity"), ("3", "cat1"), ("3", "cat4"), ("3", "cat5"), ("3", "cat6"), ("3", "cat7")]
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
                        confidence=round(float(rng.uniform(0.5, 0.99)), 2), rule_id=f"mock_{t}",
                        explanation=f"MOCK {t.replace('_', ' ')} example", evidence={"mock": True, "ratio": round(float(rng.uniform(2, 1000)), 1)},
                        proposed_fix={"field": "quantity", "old_value": 1, "new_value": 1000}, created_by=BY)
    for i, (table, why) in enumerate(LEGIT):
        L.propose_issue(con, table_name=table, record_key=f"mock:legit:{i}", year=2025, issue_type="observation",
                        confidence=1.0, rule_id="allow_list", explanation=f"checked, legitimate: {why}",
                        evidence={"mock": True}, proposed_fix=None, created_by=BY, status="legitimate")

    for scope, cat in SCOPES:
        rid = f"MOCK:A2:2025:{scope}:{cat}"
        L.write_result(con, rid, metric="tco2e", value=round(float(rng.uniform(50, 5000))), unit="t CO2e",
                       scope=scope, category=cat, year=2025, method=METHOD, produced_by=BY,
                       lineage=[L.src("record", f"erp:MOCK{j:04d}:1", round(float(rng.uniform(1, 50)), 1)) for j in range(3)]
                       + [L.src("factor", f"EF-MOCK-{cat}"), L.src("doc", "METHODOLOGY.md#mock")])

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


if __name__ == "__main__":
    seed()
    print(f"mock tables → {MOCK_DB}")
