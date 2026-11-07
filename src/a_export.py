"""2025 submission files + peat reveal (task #12).

Run:  python -m src.a_export        (after detectors + inventory; part of `make a`)

Writes:
* out/A1_issues_submission.csv          2025 records only; status `proposed` (allow-listed `legitimate` rows and
                                        `observation`s are excluded); one row per record_key, highest confidence.
* out/A2_inventory_2025_submission.csv  template rows from the 2025 inventory summary + method notes.
* out/corrections.csv                   the full correction log (expert-review trail).
* results: the peat reveal, per contract farm, metric `farm_tco2e`, scenario `mineral_only` vs
  `with_organic_soils` (app Farm & peat page), plus `all_farms` totals and the current-calculator comparison.
"""
from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pandas as pd

from src import a_inventory as A
from src import lineage as L
from src.a_detect import ISSUE_TYPES
from src.db import REPO_ROOT, connect, git_sha
from src.load import pack_dir

OUT = Path(REPO_ROOT) / "out"
YEAR = 2025
METHOD_NOTES = {
    "fugitive_refrigerants": "kg top-up × AR6 GWP100; ammonia GWP 0",
    "stationary_and_mobile_combustion": "fuel MWh (deliveries − stock change) × fossil EF; biogenic CO2 as memo",
    "purchased_electricity": "location: grid average; market: (MWh − same-vintage GoO from registry) × residual mix",
    "cat01_purchased_goods_services": "kg × valid PCF or library EF; contract farms incl. drained organic soils; services spend × EEIO",
    "cat02_capital_goods": "capex spend × EEIO",
    "cat03_fuel_energy": "WTT for fuels, upstream + T&D for electricity and heat",
    "cat04_upstream_transport": "inbound tkm × WTW EF; missing sea legs added",
    "cat05_waste": "t × treatment EF; third-party wastewater m3 × EF",
    "cat06_business_travel": "pkm × EF + hotel nights; re-imported bookings removed",
    "cat07_employee_commuting": "2025 survey mean × site headcount; Bjuv from Dec 2025 only",
    "cat09_downstream_transport": "outbound tkm × WTW EF + frozen warehousing pallet-days",
    "cat11_use_of_sold_products": "method choice: storage + cooking kWh × market grid (location-based)",
    "cat12_end_of_life": "method choice: packaging × Finnish treatment mix",
    "biogenic_co2_scope1": "memo item, not in Scope 1",
}


def export_a1(con: duckdb.DuckDBPyConnection, year: int = YEAR) -> pd.DataFrame:
    iss = con.execute("""SELECT table_name AS "table", record_key, issue_type, confidence, explanation, year
                         FROM issues WHERE status = 'proposed' AND (year = ? OR year IS NULL)""", [year]).df()
    iss = iss[iss.issue_type.isin(ISSUE_TYPES)]
    iss = iss.sort_values("confidence", ascending=False).drop_duplicates("record_key").sort_values(["table", "record_key"])
    out = iss[["table", "record_key", "issue_type", "confidence", "explanation"]]
    out.to_csv(OUT / "A1_issues_submission.csv", index=False)
    return out


def export_a2(summary: pd.DataFrame) -> pd.DataFrame:
    tmpl = pd.read_csv(pack_dir() / "tasks" / "templates" / "A2_inventory_2025_submission.csv")
    s = summary.set_index(["scope", "category"]).tco2e
    tmpl["tco2e"] = [round(float(s.get((sc, ca), 0.0)), 2) for sc, ca in zip(tmpl.scope, tmpl.category)]
    tmpl["method_note"] = tmpl.category.map(METHOD_NOTES).fillna(
        tmpl.category.str.replace("_total", "").map(lambda c: f"sum of {c} lines"))
    tmpl.to_csv(OUT / "A2_inventory_2025_submission.csv", index=False)
    return tmpl


def peat_reveal(con: duckdb.DuckDBPyConnection, c: dict, year: int = YEAR) -> dict:
    erp = A.canonical(con, c)["purchases"]
    sv = c["farm_survey"]
    both = {}
    for scen, org in [("mineral_only", False), ("with_organic_soils", True)]:
        ff = A.farm_footprints(con, sv, erp, with_organic=org)
        both[scen] = ff[ff.year == year]
    sha = f"a_export@{git_sha()}"
    for scen, ff in both.items():
        for r in ff.itertuples(index=False):
            L.write_result(con, f"PEAT:{year}:{scen}:{r.farm_id}:{r.crop}", metric="farm_tco2e", value=float(r.tco2e),
                           unit="t CO2e", scope="3", category=r.farm_id, year=year, scenario=scen,
                           method=f"{r.crop}: farm footprint × delivered kg ({scen.replace('_', ' ')})", produced_by=sha,
                           lineage=[L.src("record", k) for k in r.keys[:20]] +
                                   ([L.src("record", r.survey_key)] if isinstance(r.survey_key, str) else []) +
                                   [L.src("doc", "pack docs/METHODOLOGY.md §5")])
        L.write_result(con, f"PEAT:{year}:{scen}:all_farms", metric="farm_tco2e", value=float(ff.tco2e.sum()),
                       unit="t CO2e", scope="3", category="all_farms", year=year, scenario=scen,
                       method="sum over Finnish contract farms", produced_by=sha,
                       lineage=[L.src("doc", f"PEAT:{year}:{scen}:<farm>")])
    m, o = both["mineral_only"].tco2e.sum(), both["with_organic_soils"].tco2e.sum()
    per_farm = both["with_organic_soils"].groupby("farm_id").tco2e.sum() - both["mineral_only"].groupby("farm_id").tco2e.sum()
    head = {"year": year, "mineral_only_t": round(m, 1), "with_organic_soils_t": round(o, 1),
            "extra_from_peat_t": round(o - m, 1), "peat_share_of_farm_emissions_pct": round(100 * (o - m) / o, 1),
            "farms_with_peat_emissions": int((per_farm > 0.5).sum()),
            "top10_farms_share_of_peat_pct": round(100 * per_farm.nlargest(10).sum() / max(per_farm.sum(), 1e-9), 1)}
    L.write_result(con, f"PEAT:{year}:extra_from_peat", metric="tco2e", value=head["extra_from_peat_t"], unit="t CO2e",
                   scope="3", category="peat_reveal", year=year, scenario="with_organic_soils", method="with − mineral only",
                   produced_by=sha, lineage=[L.src("doc", f"PEAT:{year}:mineral_only:all_farms"),
                                             L.src("doc", f"PEAT:{year}:with_organic_soils:all_farms")])
    (OUT / "scores").mkdir(parents=True, exist_ok=True)
    (OUT / "scores" / "peat_reveal_2025.json").write_text(json.dumps(head, indent=1))
    return head


def export_corrections_stable(con: duckdb.DuckDBPyConnection) -> Path:
    """corrections.csv without run-time churn: DEV-ASSUMED rows carry no timestamp (they are re-assumed on every
    run); human approvals keep theirs. Sorted, so git diffs show only real changes."""
    df = con.execute("SELECT * FROM corrections ORDER BY correction_id").df()
    df.loc[df.approved_by == L.DEV_ASSUMED, "approved_at"] = pd.NaT
    path = OUT / "corrections.csv"
    df.to_csv(path, index=False)
    return path


def main() -> None:
    con = connect()
    L.init_schema(con)
    c = A.clean_tables(con)
    T = A.canonical(con, c)
    summ = A.summarise(A.compute(T, YEAR))
    a1, a2 = export_a1(con), export_a2(summ)
    export_corrections_stable(con)
    head = peat_reveal(con, c)
    print(f"A1 2025: {len(a1)} issues → out/A1_issues_submission.csv")
    print(a1.issue_type.value_counts().to_string())
    print("A2 2025 →", a2[a2.scope.isin(["total", "memo"])][["category", "tco2e"]].to_dict("records"))
    print("peat reveal:", json.dumps(head))


if __name__ == "__main__":
    main()
