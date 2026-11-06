"""Detectors part 2 (task #9): travel, shipments, waste, supplier PCFs, draft report, commuting.

* travel_bookings     duplicate_record: same traveller, date, route, distance and nights as an earlier row
                      in the file; the later row(s) are flagged (TASKS_AND_SCORING rule).
* shipments           missing_leg: an inbound lot from an origin that ships by sea on ≥90 % of its lots has no
                      sea / Ro-Pax leg. Key = ship:{ref_doc}:{expected ef_id} (the origin's usual sea leg).
* waste_transfer_notes unit_error: quantity ≤0.5 % of the stream median → tonnes keyed as kg (×1000).
* supplier_pcfs       pcf_unit_error: > 50 kg CO2e per kg (per-tonne value, ÷1000);
                      pcf_stale_period: the reference period does not start in the PCF's year (R09).
* draft_report_summary total_mismatch: the total line differs from scope 1 + scope 2 (market) + scope 3.
* commuting_survey    unit_error: one-way km > 200 (metres keyed as km, ÷1000);
                      mode_mislabel: free-text modes outside the survey's code list (Car/auto/henkilöauto → car,
                      linja-auto → bus).
"""
from __future__ import annotations

import duckdb
import numpy as np
import pandas as pd

from src.a_detect import empty
from src.a_detect.ops import _rows

SEA_MODES = {"ship-bulk", "ship-reefer", "ropax"}
MODE_CODES = {"car", "carpool", "ev_car", "bus", "train", "bike_walk"}
MODE_MAP = {"car": "car", "auto": "car", "henkilöauto": "car", "linja-auto": "bus", "bussi": "bus", "juna": "train"}


def travel_duplicates(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    t = con.execute("SELECT * FROM raw_travel_bookings").df()
    key = ["traveller_id", "travel_date", "route", "pkm", "nights"]
    d = t[t.duplicated(key, keep="first")]
    return _rows("travel_bookings", d, "duplicate_record", "travel_reimported_booking", 0.95,
                 [f"same traveller {a}, date {b}, route {c}, {p} pkm, {n} nights as an earlier row" for a, b, c, p, n in d[key].values],
                 [{"key": dict(zip(key, map(str, v)))} for v in d[key].values],
                 {"field": "*", "old_value": "row", "new_value": "DELETE"})


def shipment_missing_legs(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    s = con.execute("SELECT * FROM raw_shipments WHERE direction = 'inbound'").df()
    erp = con.execute("SELECT DISTINCT doc_no, origin_country FROM raw_erp_purchase_lines").df().drop_duplicates("doc_no")
    lots = s.groupby("ref_doc").agg(modes=("mode", set), year=("year", "first"),
                                    road_t=("t", "first"), road_km=("km", "first")).reset_index()
    lots = lots.merge(erp, left_on="ref_doc", right_on="doc_no", how="left")
    lots["sea"] = lots.modes.map(lambda m: bool(m & SEA_MODES))
    lots["reefer"] = lots.modes.map(lambda m: "truck-reefer" in m)
    share = lots.groupby("origin_country").sea.mean()
    sea_legs = s[s["mode"].isin(SEA_MODES)].merge(lots[["ref_doc", "origin_country", "reefer"]], on="ref_doc")
    usual = sea_legs.groupby(["origin_country", "reefer"]).ef_id.agg(lambda x: x.mode().iloc[0])
    km = sea_legs.groupby(["origin_country", "ef_id"]).km.median()
    x = lots[~lots.sea & lots.origin_country.map(share).ge(0.9)].copy()
    if x.empty:
        return empty()
    x["ef"] = [usual.get((o, r), "EF-TKM-SHIP-REEFER" if r else "EF-TKM-SHIP-BULK") for o, r in zip(x.origin_country, x.reefer)]
    x["est_km"] = [km.get((o, e), np.nan) for o, e in zip(x.origin_country, x.ef)]
    x["record_key"] = "ship:" + x.ref_doc.astype(str) + ":" + x.ef
    return _rows("shipments", x, "missing_leg", "ship_missing_sea_leg", 0.85,
                 [f"lot from {o} (sea leg on {share[o]:.0%} of lots) has no sea/Ro-Pax leg; expected {e}" for o, e in zip(x.origin_country, x.ef)],
                 [{"origin": o, "origin_sea_share": round(float(share[o]), 3), "modes": sorted(m)} for o, m in zip(x.origin_country, x.modes)],
                 [{"field": "tkm", "old_value": None, "new_value": round(t * k, 1) if pd.notna(k) else None}
                  for t, k in zip(x.road_t, x.est_km)])


def waste_units(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    w = con.execute("SELECT * FROM raw_waste_transfer_notes").df()
    w["med"] = w.groupby("waste_stream").quantity.transform("median")
    u = w[w.quantity <= 0.005 * w.med]
    return _rows("waste_transfer_notes", u, "unit_error", "waste_tonnes_as_kg", 0.9,
                 [f"{q} kg of {s} is {q / m:.4f}× the stream median: tonnes keyed as kg" for q, s, m in zip(u.quantity, u.waste_stream, u.med)],
                 [{"quantity": q, "stream_median": m} for q, m in zip(u.quantity, u.med)],
                 [{"field": "quantity", "old_value": q, "new_value": round(q * 1000, 3)} for q in u.quantity])


def pcf_checks(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    p = con.execute("SELECT * FROM raw_supplier_pcfs").df()
    start = p.reference_period_start.str[:4].astype(int)
    end = pd.to_datetime(p.reference_period_end).dt.year
    u = p[p.pcf_excluding_biogenic > 50]
    st = p[(start != p.year) & ~p.index.isin(u.index)]
    return pd.concat([x for x in [
        _rows("supplier_pcfs", u, "pcf_unit_error", "pcf_per_tonne", 0.9,
              [f"{v} kg CO2e per {d}: implausible for a food material, a per-tonne value" for v, d in zip(u.pcf_excluding_biogenic, u.declared_unit)],
              [{"value": v, "declared_unit": d} for v, d in zip(u.pcf_excluding_biogenic, u.declared_unit)],
              [{"field": "pcf_excluding_biogenic", "old_value": v, "new_value": round(v / 1000, 5)} for v in u.pcf_excluding_biogenic]),
        _rows("supplier_pcfs", st, "pcf_stale_period", "pcf_reference_period", 0.9,
              [f"PCF used for {y} but its reference period is {s[:10]}…{e[:10]}" for y, s, e in zip(st.year, st.reference_period_start, st.reference_period_end)],
              [{"year": y, "reference_period_start": s, "reference_period_end": e} for y, s, e in zip(st.year, st.reference_period_start, st.reference_period_end)],
              {"field": "use", "old_value": "supplier PCF", "new_value": "material default factor (R09)"}),
    ] if not x.empty] or [empty()], ignore_index=True)


def report_totals(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    r = con.execute("SELECT * FROM raw_draft_report_summary").df()
    out = []
    for y, g in r.groupby("year"):
        v = dict(zip(g.line, g.tco2e))
        need = {"scope1", "scope2_market", "scope3", "total_market_based"}
        if not need <= set(v):
            continue
        parts = v["scope1"] + v["scope2_market"] + v["scope3"]
        if abs(v["total_market_based"] - parts) > 0.005 * max(parts, 1):
            row = g[g.line == "total_market_based"]
            out.append(_rows("draft_report_summary", row, "total_mismatch", "report_total_vs_parts", 0.9,
                             f"total {v['total_market_based']:,.0f} ≠ scope 1 + 2 (market) + 3 = {parts:,.0f}",
                             {"total": v["total_market_based"], "sum_of_parts": parts},
                             {"field": "tco2e", "old_value": v["total_market_based"], "new_value": parts}))
    return pd.concat(out, ignore_index=True) if out else empty()


def commuting_checks(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    c = con.execute("SELECT * FROM raw_commuting_survey").df()
    c["year"] = 2025
    u = c[c.one_way_km > 200]
    m = c[~c["mode"].isin(MODE_CODES)]
    return pd.concat([x for x in [
        _rows("commuting_survey", u, "unit_error", "commute_metres_as_km", 0.75,
              [f"{k} km one way is implausible for a commute: metres keyed as km" for k in u.one_way_km],
              [{"one_way_km": k} for k in u.one_way_km],
              [{"field": "one_way_km", "old_value": k, "new_value": round(k / 1000, 3)} for k in u.one_way_km]),
        _rows("commuting_survey", m, "mode_mislabel", "commute_mode_code", 0.8,
              [f"mode '{v}' is not a survey code ({', '.join(sorted(MODE_CODES))})" for v in m["mode"]],
              [{"mode": v} for v in m["mode"]],
              [{"field": "mode", "old_value": v, "new_value": MODE_MAP.get(str(v).lower(), "car")} for v in m["mode"]]),
    ] if not x.empty] or [empty()], ignore_index=True)


def detect_all(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    parts = [travel_duplicates(con), shipment_missing_legs(con), waste_units(con), pcf_checks(con),
             report_totals(con), commuting_checks(con)]
    return pd.concat([p for p in parts if not p.empty], ignore_index=True)
