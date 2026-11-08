"""The three-problem brief behind the Overview: GET /api/brief, GET /api/issues, POST /api/report/inventory.

Apetit's three problems, and what answers each one:
1. Data is scattered and messy      → one checked dataset: feeds unified, issues found, fixes waiting for sign-off.
2. Reports are built by hand        → the inventory is rebuilt from source records, every number traced, scored on
                                      the public 2023/2024 truths, and the hand-made draft is checked against it.
3. "Never another Sweden 2026"      → a replay of the 2026 Skåne pea failure: what the weather said by flowering,
                                      what a model trained only on ≤2023 predicted, and when Apetit actually knew.

Every number is computed here from out/serve.duckdb and out/scores/*.json (deterministic code, no LLM). The only
typed-in facts are the public profit-warning date and its source, kept in PUBLIC_EVENT.
"""
from __future__ import annotations

import json
from datetime import date

from fastapi import HTTPException

from src import serve_db
from src.db import REPO_ROOT

SCORES = REPO_ROOT / "out" / "scores"
# Public, dated event (docs/APETIT_CONTEXT.md): the profit warning that the Swedish pea failure caused.
PUBLIC_EVENT = {"date": "2026-08-12", "label": "Apetit profit warning: hot, dry weather cut Swedish pea yields",
                "source": "Apetit inside information, 12 Aug 2026 (via Inderes; Just Food)"}
FLOWERING_MONTH = 6  # pea flowering stage month used by src.p_alerts (H1 drought at flowering)
TYPE_LABEL = {
    "unit_error": "Wrong unit", "soil_misreport": "Soil misreported", "duplicate_record": "Duplicate",
    "area_mismatch": "Area mismatch", "decimal_shift": "Decimal shift", "currency_error": "Wrong currency",
    "material_mismatch": "Wrong material", "missing_record": "Missing record", "wrong_gas_code": "Wrong gas code",
    "missing_leg": "Missing trip leg", "outlier_implausible": "Implausible value", "meter_spike": "Meter spike",
    "mode_mislabel": "Wrong transport mode", "pcf_stale_period": "Stale supplier PCF", "certificate_mismatch":
    "Certificate mismatch", "pcf_unit_error": "Supplier PCF unit", "coordinate_swap": "Swapped coordinates",
    "total_mismatch": "Total ≠ parts",
}
SOURCE_LABEL = {
    "erp_purchase_lines": "ERP purchases", "farm_survey": "Farm survey (FI)", "commuting_survey": "Commuting survey",
    "supplier_pcfs": "Supplier PCFs", "energy_meter_readings": "Energy meters", "travel_bookings": "Travel bookings",
    "refrigerant_service_log": "Refrigerant log", "shipments": "Shipments", "waste_transfer_notes": "Waste notes",
    "fuel_deliveries": "Fuel deliveries", "goo_cancellations": "Guarantees of origin",
    "draft_report_summary": "Draft report", "foodhills_odlingsdata_se": "Grower file (SE)", "parcels": "Parcels",
}


def _con():
    if not serve_db.exists():
        raise HTTPException(503, "out/serve.duckdb missing: run `make snapshot`")
    return serve_db.connect()


def _json(name: str) -> dict | None:
    p = SCORES / name
    return json.loads(p.read_text()) if p.exists() else None


def _data(con) -> dict:
    raw = [t for (t,) in con.execute("SELECT table_name FROM information_schema.tables WHERE table_name LIKE 'raw_%'")
           .fetchall()]
    rows = {t: con.execute(f'SELECT count(*) FROM "{t}"').fetchone()[0] for t in raw}
    iss = con.execute("SELECT table_name, record_key, issue_type, confidence, year, status FROM issues").df()
    prop = iss[iss.status == "proposed"]
    checked_tables = {t for t in iss.table_name.unique()}
    checked = sum(n for t, n in rows.items() if any(t == f"raw_{c}" or t.startswith(f"raw_{c}_") for c in checked_tables))
    by_source = (prop.groupby("table_name").size().sort_values(ascending=False).head(6))
    by_type = (prop.groupby("issue_type").size().sort_values(ascending=False).head(5))
    approved = con.execute("SELECT count(*) FROM corrections WHERE approved_by IS NOT NULL "
                           "AND approved_by NOT LIKE 'DEV-%'").fetchone()[0]
    a1 = None
    try:
        from src.a_score import dev_labels, score_a1
        s = score_a1(prop, dev_labels(con))
        a1 = {"score": round(s["score"], 1), "precision_pct": round(100 * s["precision"], 1),
              "recall_pct": round(100 * s["recall"], 1)}
    except Exception:  # noqa: BLE001 (score is optional; the brief still renders)
        a1 = None
    return {
        "feeds": len(raw), "records": int(sum(rows.values())), "records_checked": int(checked),
        "issues_found": int(len(prop)), "legit_left_alone": int((iss.status == "legitimate").sum()),
        "issues_2025": int((prop.year == 2025).sum()), "awaiting_signoff": int(len(prop) - approved),
        "approved": int(approved),
        "by_source": [{"key": k, "label": SOURCE_LABEL.get(k, k.replace("_", " ")), "n": int(n)} for k, n in by_source.items()],
        "by_type": [{"key": k, "label": TYPE_LABEL.get(k, k), "n": int(n)} for k, n in by_type.items()],
        "accuracy": a1,
    }


def _reports(con) -> dict:
    tot = dict(con.execute("SELECT category, value FROM results WHERE metric = 'tco2e' AND year = 2025 "
                           "AND scope = 'total'").fetchall())
    s3 = con.execute("SELECT category, value FROM results WHERE metric = 'tco2e' AND year = 2025 AND scope = 'scope3' "
                     "ORDER BY value DESC").fetchall()
    traced = con.execute("SELECT count(DISTINCT source_ref), count(*) FROM lineage WHERE result_id LIKE 'A2:2025:%' "
                         "AND source_kind = 'record'").fetchone()
    factors = con.execute("SELECT count(DISTINCT source_ref) FROM lineage WHERE result_id LIKE 'A2:2025:%' "
                          "AND source_kind = 'factor'").fetchone()[0]
    draft = dict(con.execute("SELECT line, tco2e FROM raw_draft_report_summary WHERE year = 2025").fetchall())
    a2 = (_json("A2_dev.json") or {}).get("scores", {})
    ours = {"scope1": tot.get("scope1_total"), "scope2_market": tot.get("scope2_market_total"),
            "scope3": tot.get("scope3_total")}
    checks = []
    for line, label in (("scope1", "Scope 1"), ("scope2_market", "Scope 2 (market)"), ("scope3", "Scope 3")):
        d, o = draft.get(line), ours.get(line)
        if d is not None and o:
            checks.append({"line": label, "draft": round(d), "rebuilt": round(o), "ratio": round(d / o, 1)})
    sum_parts = sum(v for k, v in draft.items() if k in ("scope1", "scope2_market", "scope3"))
    return {
        "year": 2025,
        "scope1": round(ours["scope1"] or 0), "scope2_market": round(ours["scope2_market"] or 0),
        "scope2_location": round(tot.get("scope2_location_total") or 0), "scope3": round(ours["scope3"] or 0),
        "total_market": round(sum(v or 0 for v in ours.values())),
        "scope3_top": [{"key": k, "t": round(v)} for k, v in s3[:4]],
        "records_traced": int(traced[0] or 0), "trace_links": int(traced[1] or 0), "factors_used": int(factors or 0),
        "dev_scores": [{"year": int(y), "score": round(s["score"], 1)} for y, s in sorted(a2.items())],
        "draft_checks": checks,
        "draft_total": round(draft.get("total_market_based", 0)), "draft_sum_of_parts": round(sum_parts),
    }


def _sweden(con) -> dict:
    from src import p_season
    m = p_season.months(con, "ssp245", 2026, "SE_SKANE")["months"]
    r = lambda rid: (con.execute("SELECT value FROM results WHERE result_id = ?", [rid]).fetchone() or [None])[0]  # noqa: E731
    pred = r("C1:backtest:2026:SE_SKANE:pea:production_t")
    act = r("C1:backtest:2026:SE_SKANE:pea:production_t_actual")
    prev = r("C1:backtest:2025:SE_SKANE:pea:production_t_actual")
    fi26, fi25 = r("C1:backtest:2026:FI_SW:pea:production_t_actual"), r("C1:backtest:2025:FI_SW:pea:production_t_actual")
    p90 = r("C3:baseline:SE_SKANE:pea:eur_at_risk_p90")
    signal = date(2026, FLOWERING_MONTH, 30)
    warn = date.fromisoformat(PUBLIC_EVENT["date"])
    flower = next((x for x in m if x["month"] == FLOWERING_MONTH), None)
    spring = [x for x in m if 3 <= x["month"] <= FLOWERING_MONTH]
    return {
        "region": "SE_SKANE", "crop": "pea", "year": 2026,
        "months": [{"month": x["month"], "rain_anom_pct": x["precip_anom_pct"], "temp_anom_c": x["tmean_anom_c"],
                    "hot_days": x["hot_days"]} for x in m if x["month"] <= 9],
        "flowering_month": FLOWERING_MONTH,
        "flowering_rain_pct": flower["precip_anom_pct"] if flower else None,
        "spring_rain_pct": round(sum(x["precip_anom_pct"] for x in spring) / len(spring)) if spring else None,
        "signal_date": signal.isoformat(), "event": PUBLIC_EVENT, "lead_days": (warn - signal).days,
        "predicted_t": round(pred) if pred else None, "actual_t": round(act) if act else None,
        "model_error_pct": round(100 * abs(pred - act) / act, 1) if pred and act else None,
        "drop_vs_prev_pct": round(100 * (act - prev) / prev, 1) if act and prev else None,
        "fi_change_pct": round(100 * (fi26 - fi25) / fi25, 1) if fi26 and fi25 else None,
        "bad_year_eur_p90": round(p90) if p90 else None,
    }


def brief() -> dict:
    with _con() as con:
        return {"data": _data(con), "reports": _reports(con), "sweden": _sweden(con), "synthetic": True}


def issues(status: str = "proposed", source: str | None = None, limit: int = 40) -> list[dict]:
    with _con() as con:
        q = ("SELECT i.issue_id, i.table_name, i.record_key, i.year, i.issue_type, i.confidence, i.explanation, "
             "c.field, c.old_value, c.new_value, c.approved_by FROM issues i "
             "LEFT JOIN corrections c USING (issue_id) WHERE i.status = ?")
        args: list = [status]
        if source:
            q += " AND i.table_name = ?"
            args.append(source)
        q += " ORDER BY i.year DESC, i.confidence DESC, i.issue_id LIMIT ?"
        args.append(limit)
        df = con.execute(q, args).df()
    out = []
    for row in df.to_dict("records"):
        row = {k: (None if v != v else v) for k, v in row.items()}  # NaN → None
        row["type_label"] = TYPE_LABEL.get(row["issue_type"], row["issue_type"])
        row["source_label"] = SOURCE_LABEL.get(row["table_name"], row["table_name"])
        row["signed_off"] = bool(row["approved_by"]) and not str(row["approved_by"]).startswith("DEV-")
        out.append(row)
    return out


def inventory_report(year: int = 2025) -> dict:
    from src import r_report
    with _con() as con:
        return r_report.make_report(con, "inventory_summary", {"years": [year]})
