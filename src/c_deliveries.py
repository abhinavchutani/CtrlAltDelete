"""Climate lane: contract pea delivery change year on year, per region (task #65; copilot E18/E19).

Run:  python -m src.c_deliveries     (needs `make a` for clean_farm_survey; `make c` runs it)

* SE_SKANE (Foodhills): Σ levererad_mängd_ton per harvest year. The file covers all Swedish growers,
  so the change is total deliveries Y vs Y−1.
* FI_SW: the farm survey covers ~70 % of pea growers each year and the sample changes, so a raw total
  mixes weather with sample composition. Deliveries = Σ area × yield over the farms that report pea in
  **both** years (same-farm matching). The raw-total change is kept in the note for transparency.

Writes results metric='delivery_change_pct', category='{region}:pea', year=Y (change from Y−1 to Y),
with the record keys of every contributing row as lineage. Deterministic.
"""
from __future__ import annotations

import duckdb
import pandas as pd

from src import c_model as M
from src import lineage as L
from src.db import connect, git_sha

YEARS = range(2019, 2027)   # change into each of these years from the year before


def fi_rows(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    t = M.survey_table(con)
    return con.execute(f"""SELECT farm_id, year, record_key, area_ha * yield_t_ha AS t
                           FROM {t} WHERE crop = 'pea'""").df()


def se_rows(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return con.execute("""SELECT odlar_id AS farm_id, skördeår AS year,
                                 'foodhills:' || odlar_id || ':' || skördeår AS record_key,
                                 levererad_mängd_ton AS t FROM raw_foodhills_odlingsdata_se""").df()


def change(rows: pd.DataFrame, year: int, matched: bool) -> dict:
    a, b = rows[rows.year == year - 1], rows[rows.year == year]
    raw = b.t.sum() / a.t.sum() - 1
    if matched:
        farms = set(a.farm_id) & set(b.farm_id)
        a, b = a[a.farm_id.isin(farms)], b[b.farm_id.isin(farms)]
    return {"pct": 100 * (b.t.sum() / a.t.sum() - 1), "raw_pct": 100 * raw, "n_farms": int(b.farm_id.nunique()),
            "t_prev": float(a.t.sum()), "t_now": float(b.t.sum()), "keys": sorted(a.record_key) + sorted(b.record_key)}


def compute(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    out = []
    for region, rows, matched in (("FI_SW", fi_rows(con), True), ("SE_SKANE", se_rows(con), False)):
        for y in YEARS:
            if {y - 1, y} <= set(rows.year):
                out.append({"region": region, "year": y, "matched": matched, **change(rows, y, matched)})
    return pd.DataFrame(out)


def write_results(con: duckdb.DuckDBPyConnection, df: pd.DataFrame) -> None:
    L.init_schema(con)
    by = f"c_deliveries@{git_sha()}"
    for r in df.itertuples(index=False):
        how = (f"same-farm matched ({r.n_farms} farms; raw sample total {r.raw_pct:+.1f} %)" if r.matched
               else f"all growers ({r.n_farms})")
        L.write_result(con, f"C:deliveries:{r.region}:pea:{r.year}", metric="delivery_change_pct",
                       value=round(float(r.pct), 2), unit="%", category=f"{r.region}:pea", year=int(r.year),
                       scenario="actual", produced_by=by,
                       method=f"pea deliveries {r.year - 1}→{r.year}: {r.t_prev:,.0f} → {r.t_now:,.0f} t, {how}",
                       lineage=[L.src("record", k) for k in r.keys])


def main() -> None:
    con = connect()
    df = compute(con)
    write_results(con, df)
    print(df[["region", "year", "pct", "raw_pct", "n_farms", "t_prev", "t_now"]].round(1).to_string(index=False))


if __name__ == "__main__":
    main()
