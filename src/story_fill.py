"""Fill the pitch / method-note {{placeholders}} from results, issues and out/scores (task #49, G4).

Run:  python -m src.story_fill        (after `make a` and `make c`)

Every value is computed here by deterministic code and carries its source; nothing is typed by hand.
Values whose producer has not run yet stay as `{{NAME}}` and are listed as pending with the reason.
Writes out/pitch/<file> (filled copies) and out/pitch/values.json (value + source for every placeholder).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import duckdb
import pandas as pd

from src import a_inventory as A
from src.a_score import dev_labels, score_a1
from src.db import REPO_ROOT, connect

SOURCES = [Path("METHOD_NOTE.md"), Path("docs/pitch/SUBMISSION_TEXT.md"), Path("docs/pitch/DECK_AND_SCRIPTS.md")]
OUT = Path(REPO_ROOT) / "out" / "pitch"
SCORES = Path(REPO_ROOT) / "out" / "scores"


def fmt(x: float, digits: int = 0) -> str:
    return f"{x:,.{digits}f}"


def _json(name: str) -> dict | None:
    p = SCORES / name
    return json.loads(p.read_text()) if p.exists() else None


def _results(con: duckdb.DuckDBPyConnection, where: str, params=()) -> pd.DataFrame:
    return con.execute(f"SELECT * FROM results WHERE {where}", list(params)).df()


def compute_values(con: duckdb.DuckDBPyConnection) -> dict[str, dict]:
    v: dict[str, dict] = {}

    def put(name: str, value: str | None, source: str, pending: str = "") -> None:
        v[name] = {"value": value, "source": source, "pending": pending if value is None else ""}

    # A1: live re-score of the proposed issues against the public dev labels
    iss = con.execute("SELECT table_name, record_key, issue_type, confidence, year, status FROM issues").df()
    prop = iss[iss.status == "proposed"]
    put("A1_DEV_SCORE", fmt(score_a1(prop, dev_labels(con))["score"], 1), "issues (proposed) vs task_dev_A1 labels, src/a_score.py")
    put("ISSUES_FOUND", fmt(len(prop)), "issues WHERE status='proposed' (all years)")
    put("LEGIT_SUPPRESSED", fmt((iss.status == "legitimate").sum()), "issues WHERE status='legitimate' (allow-list R01–R04)")

    a2 = _json("A2_dev.json")
    for y in ("2023", "2024"):
        s = (a2 or {}).get("scores", {}).get(y)
        put(f"A2_DEV_{y}", fmt(s["score"], 1) if s else None, "out/scores/A2_dev.json", "run python -m src.a_inventory")

    r = con.execute("SELECT value FROM results WHERE result_id = 'C1:backtest:production_mape_pct'").fetchall()
    mape, c1_src = (r[0][0], "results C1:backtest:production_mape_pct") if r else (None, "")
    if mape is None:  # fallback: the scores file written by make c
        c1 = _json("C1_backtest.json") or _json("C1_backtest_monthly.json")
        m = (c1 or {}).get("production_mape_pct")
        mape, c1_src = (m.get("model") if isinstance(m, dict) else m), "out/scores/C1_backtest.json"
    put("C1_BACKTEST_MAPE", f"{mape:.1f} %" if mape is not None else None, c1_src or "C1 backtest", "run make c")

    peat = _json("peat_reveal_2025.json")
    if peat:
        put("PEAT_BEFORE", f"{fmt(peat['mineral_only_t'])} t CO2e", "out/scores/peat_reveal_2025.json (mineral_only)")
        put("PEAT_AFTER", f"{fmt(peat['with_organic_soils_t'])} t CO2e", "out/scores/peat_reveal_2025.json (with_organic_soils)")
        put("PEAT_EXTRA_TCO2E", fmt(peat["extra_from_peat_t"]), "out/scores/peat_reveal_2025.json")
        put("PEAT_SHARE_PCT", fmt(peat["peat_share_of_farm_emissions_pct"], 0), "out/scores/peat_reveal_2025.json")
        per = _results(con, "metric='farm_tco2e' AND year=2025 AND category<>'all_farms'")
        if len(per):
            p = per.pivot_table(index="category", columns="scenario", values="value", aggfunc="sum").fillna(0)
            extra = (p.get("with_organic_soils", 0) - p.get("mineral_only", 0)).sort_values(ascending=False)
            n_half = int((extra.cumsum() < 0.5 * extra.sum()).sum() + 1)
            put("PEAT_TOP_FARMS", str(n_half), "results farm_tco2e: fewest farms carrying ≥50 % of the peat emissions")
    for k in ("PEAT_BEFORE", "PEAT_AFTER", "PEAT_EXTRA_TCO2E", "PEAT_SHARE_PCT", "PEAT_TOP_FARMS"):
        v.setdefault(k, {"value": None, "source": "peat reveal", "pending": "run python -m src.a_export"})

    c = A.clean_tables(con)
    before = A.flag_share(A.canonical(con, c, with_organic=False), 2025)
    after = A.flag_share(A.canonical(con, c, with_organic=True), 2025)
    put("FLAG_SHARE_BEFORE", f"{before['flag_share_pct']:.1f} %", "a_inventory.flag_share(2025, mineral soils only)")
    put("FLAG_SHARE_AFTER", f"{after['flag_share_pct']:.1f} %", "a_inventory.flag_share(2025, with organic soils)")

    # Track C: C2 mean yield change at SSP5-8.5, 2041–60 (signed; peas gain, potato and turnip rape lose)
    c2 = _results(con, "metric='yield_change_pct' AND scenario='ssp585'").set_index("category").value
    for name, cat in [("C2_POTATO_FI_585_PCT", "FI_SW:potato"), ("C2_RAPE_FI_585_PCT", "FI_SW:turnip_rape"),
                      ("C2_PEA_SE_585_PCT", "SE_SKANE:pea")]:
        put(name, f"{c2[cat]:+.1f}" if cat in c2.index else None,
            f"results C2:ssp585:{cat}:yield_change_pct", "C2 (#18) not published yet: run make c")
    for name, metric in [("C3_EUR_AT_RISK", "eur_at_risk"), ("C3_HEDGE_EUR", "eur_hedge"), ("C3_IRRIGATION_EUR", "eur_irrigation")]:
        r = _results(con, "metric = ? AND (scenario LIKE 'ssp245%' OR scenario='today')", [metric])
        put(name, f"€{fmt(r.value.sum())}" if len(r) else None, f"results metric={metric}", "C3 (#19) not published yet")
    put("C3_REBALANCE_PCT", None, "results C3 sourcing split", "C3 (#19) not published yet")
    return v


def render(values: dict[str, dict]) -> dict[str, list[str]]:
    OUT.mkdir(parents=True, exist_ok=True)
    pending: dict[str, list[str]] = {}
    for src in SOURCES:
        text = (Path(REPO_ROOT) / src).read_text()

        def sub(m: re.Match) -> str:
            val = values.get(m.group(1), {}).get("value")
            if val is None:
                pending.setdefault(src.name, []).append(m.group(1))
                return m.group(0)
            return val
        (OUT / src.name).write_text(re.sub(r"\{\{([A-Z0-9_]+)\}\}", sub, text))
    (OUT / "values.json").write_text(json.dumps(values, indent=1, ensure_ascii=False))
    return pending


def main() -> None:
    con = connect()
    values = compute_values(con)
    pending = render(values)
    filled = sum(1 for x in values.values() if x["value"] is not None)
    print(f"filled {filled}/{len(values)} placeholders → out/pitch/")
    for k, x in values.items():
        print(f"  {k:22} {x['value'] or 'PENDING: ' + x['pending']}")
    if pending:
        print("still pending in:", {k: sorted(set(v)) for k, v in pending.items()})


if __name__ == "__main__":
    main()
