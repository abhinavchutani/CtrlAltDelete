"""Detectors part 1 (task #8): ERP, energy meters, fuel, GoO, refrigerants + allow-list.

Thresholds tuned on the public 2023–24 dev labels (no record-key-specific rules). Rules → REASONING_LOG:
* ERP goods lines (uom KG/TO, movement 101): price per kg vs the material median
  - ≥300×           → unit_error   (tonnes keyed as KG)         fix quantity ×1000
  - 7–14× / 0.07–0.14× (same currency as the supplier's usual) → decimal_shift   fix quantity ÷/×10
* ERP currency: a supplier that invoices ≥80 % in one currency posts a line in another → currency_error;
  spend lines (uom EUR) ≥9× the supplier's median amount → currency_error (SEK keyed as EUR, ÷11.4)
* ERP material: a supplier with ≥90 % of goods lines on one material books another → material_mismatch
* ERP duplicates: same supplier, material, quantity, amount, uom → later posting is duplicate_record
* Energy: monthly MWh vs the same month's median (seasonal profile, R03) ≥300× → unit_error (kWh, ÷1000);
  2.5–300× → meter_spike; months missing *inside* a site × carrier series → missing_record (R06)
* Fuel: litre carriers with quantity < 100 → unit_error (m³ keyed as litres, ×1000)
* GoO: internal log vs registry (authoritative, R05): vintage or MWh differs → certificate_mismatch
* Refrigerant: R717 logged on a system whose usual gas is not ammonia → wrong_gas_code;
  kg_added ≥100× the system median → unit_error (grams, ÷1000). Real ammonia systems pass (R04).
Allow-list (R01, R02, R04): credit notes (movement 122), TO lots and ammonia on ammonia systems are
logged with status `legitimate`, never flagged.
"""
from __future__ import annotations

import duckdb
import numpy as np
import pandas as pd

from src.a_detect import CANDIDATE_COLUMNS, empty

FX_PER_EUR = {"EUR": 1.0, "SEK": 11.4, "USD": 1.08}  # pack factors (ccn_tools/factors.py)
SEK_PER_EUR = FX_PER_EUR["SEK"]


def _rows(table: str, df: pd.DataFrame, issue_type: str, rule_id: str, confidence, explanation,
          evidence, proposed_fix, year_col: str = "year", status: str = "proposed") -> pd.DataFrame:
    if df.empty:
        return empty()
    n = len(df)
    as_list = lambda v: list(v) if isinstance(v, (list, pd.Series, np.ndarray)) else [v] * n
    out = pd.DataFrame({"table_name": table, "record_key": df.record_key.values,
                        "year": df[year_col].values if year_col in df else None,
                        "issue_type": issue_type, "confidence": as_list(confidence), "rule_id": rule_id,
                        "explanation": as_list(explanation), "evidence": as_list(evidence),
                        "proposed_fix": as_list(proposed_fix)})
    out["status"] = status
    return out[CANDIDATE_COLUMNS + ["status"]]


# ── ERP ───────────────────────────────────────────────────────────────
def erp_frame(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    e = con.execute("SELECT * FROM raw_erp_purchase_lines").df()
    e["year"] = e.posting_date.str[:4].astype(int)
    e["goods"] = e.uom.isin(["KG", "TO"]) & (e.movement_type == 101)
    e["kg"] = np.where(e.uom == "TO", e.quantity * 1000, e.quantity)
    e["sup_cur"] = e.groupby("supplier_id").currency.transform(lambda s: s.mode().iloc[0])
    e["sup_cur_share"] = e.groupby("supplier_id").currency.transform(lambda s: (s == s.mode().iloc[0]).mean())
    e["eur"] = e.net_amount / e.currency.map(FX_PER_EUR).fillna(1.0)
    e["ppk"] = np.where(e.goods & (e.kg > 0), e.eur / e.kg.where(e.kg > 0), np.nan)
    med = e[e.goods].groupby("material_id").ppk.median()
    e["ppk_med"] = e.material_id.map(med)
    e["r"] = e.ppk / e.ppk_med
    g = e[e.goods]
    e["sup_mat"] = e.supplier_id.map(g.groupby("supplier_id").material_id.agg(lambda s: s.mode().iloc[0]))
    e["sup_mat_share"] = e.supplier_id.map(g.groupby("supplier_id").material_id.agg(lambda s: (s == s.mode().iloc[0]).mean()))
    spend = e.uom.eq("EUR")
    e["spend_med"] = e[spend].groupby("supplier_id").net_amount.transform("median")
    e["spend_r"] = e.net_amount / e.spend_med
    return e


def erp_detect(e: pd.DataFrame) -> pd.DataFrame:
    parts = []
    key = ["supplier_id", "material_id", "quantity", "net_amount", "uom"]
    dup = e.sort_values(["posting_date", "doc_no"]).duplicated(key, keep="first").reindex(e.index) & (e.movement_type == 101)
    d = e[dup]
    parts.append(_rows("erp_purchase_lines", d, "duplicate_record", "erp_duplicate_posting", 0.9,
                       [f"same supplier, material, quantity and amount as an earlier posting ({s}, {m})" for s, m in zip(d.supplier_id, d.material_id)],
                       [{"key": dict(zip(key, map(str, v)))} for v in d[key].values],
                       {"field": "*", "old_value": "line", "new_value": "DELETE"}))
    taken = set(d.record_key)

    u = e[e.goods & (e.r >= 300) & ~e.record_key.isin(taken)]
    parts.append(_rows("erp_purchase_lines", u, "unit_error", "erp_price_ratio_1000x", 0.95,
                       [f"price/kg {r:.0f}× the {m} median: tonnes keyed with uom KG" for r, m in zip(u.r, u.material_id)],
                       [{"price_per_kg": p, "material_median": m, "ratio": round(r, 2)} for p, m, r in zip(u.ppk, u.ppk_med, u.r)],
                       [{"field": "quantity", "old_value": q, "new_value": round(q * 1000, 3)} for q in u.quantity]))
    taken |= set(u.record_key)

    ds = e[e.goods & ~e.record_key.isin(taken) & (((e.r > 7) & (e.r < 14) & (e.currency == e.sup_cur)) | ((e.r > 0.07) & (e.r < 0.14)))]
    parts.append(_rows("erp_purchase_lines", ds, "decimal_shift", "erp_price_ratio_10x", 0.85,
                       [f"price/kg {r:.2f}× the {m} median: quantity off by ×10" for r, m in zip(ds.r, ds.material_id)],
                       [{"price_per_kg": p, "material_median": m, "ratio": round(r, 3)} for p, m, r in zip(ds.ppk, ds.ppk_med, ds.r)],
                       [{"field": "quantity", "old_value": q, "new_value": round(q / 10 if r < 1 else q * 10, 3)} for q, r in zip(ds.quantity, ds.r)]))
    taken |= set(ds.record_key)

    cu = e[(e.currency != e.sup_cur) & (e.sup_cur_share >= 0.8) & ~e.record_key.isin(taken)]
    parts.append(_rows("erp_purchase_lines", cu, "currency_error", "erp_supplier_currency", 0.8,
                       [f"{s} invoices {sc} on {sh:.0%} of lines; this line says {c}" for s, sc, sh, c in zip(cu.supplier_id, cu.sup_cur, cu.sup_cur_share, cu.currency)],
                       [{"supplier_currency": sc, "share": round(sh, 3), "line_currency": c} for sc, sh, c in zip(cu.sup_cur, cu.sup_cur_share, cu.currency)],
                       [{"field": "currency", "old_value": c, "new_value": sc} for c, sc in zip(cu.currency, cu.sup_cur)]))
    taken |= set(cu.record_key)

    sp = e[e.uom.eq("EUR") & (e.spend_r > 9) & ~e.record_key.isin(taken)]
    parts.append(_rows("erp_purchase_lines", sp, "currency_error", "erp_spend_sek_as_eur", 0.8,
                       [f"amount {r:.1f}× the supplier's median spend: SEK keyed as EUR" for r in sp.spend_r],
                       [{"amount": a, "supplier_median": m, "ratio": round(r, 2), "sek_per_eur": SEK_PER_EUR} for a, m, r in zip(sp.net_amount, sp.spend_med, sp.spend_r)],
                       [{"field": "net_amount", "old_value": a, "new_value": round(a / SEK_PER_EUR, 2)} for a in sp.net_amount]))
    taken |= set(sp.record_key)

    mm = e[e.goods & (e.material_id != e.sup_mat) & (e.sup_mat_share >= 0.9) & ~e.record_key.isin(taken)]
    parts.append(_rows("erp_purchase_lines", mm, "material_mismatch", "erp_supplier_material", 0.75,
                       [f"{s} supplies {sm} on {sh:.0%} of lines; this line is {m}" for s, sm, sh, m in zip(mm.supplier_id, mm.sup_mat, mm.sup_mat_share, mm.material_id)],
                       [{"supplier_material": sm, "share": round(sh, 3)} for sm, sh in zip(mm.sup_mat, mm.sup_mat_share)],
                       [{"field": "material_id", "old_value": m, "new_value": sm} for m, sm in zip(mm.material_id, mm.sup_mat)]))

    legit = e[(e.movement_type == 122) | (e.uom == "TO")]
    parts.append(_rows("erp_purchase_lines", legit, "unit_error", "allow_credit_note_or_tonne_lot", 1.0,
                       ["checked, legitimate: credit note (movement 122)" if m == 122 else "checked, legitimate: vessel lot in tonnes (uom TO)" for m in legit.movement_type],
                       {"allow_list": ["R01", "R02"]}, None, status="legitimate"))
    return pd.concat([p for p in parts if not p.empty], ignore_index=True)


# ── energy, fuel, GoO, refrigerant ────────────────────────────────────
def energy_detect(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    em = con.execute("SELECT * FROM raw_energy_meter_readings").df()
    em["mwh"] = np.where(em.unit == "kWh", em.value / 1000, em.value)
    em["mmed"] = em.groupby(["site_id", "carrier", "month"]).mwh.transform("median")
    em["rm"] = em.mwh / em.mmed
    # year level: this site × carrier × year runs at `level` × the seasonal profile (clean months only)
    ok = em[(em.rm > 0.5) & (em.rm < 2.0)]
    level = ok.groupby(["site_id", "carrier", "year"]).rm.median()
    good = {(r.site_id, r.carrier, r.year * 12 + r.month - 1): r.mwh for r in ok.itertuples(index=False)}
    prof = em.groupby(["site_id", "carrier", "month"]).mwh.median().to_dict()

    def estimate(site: str, car: str, y: int, m: int) -> float:
        """Seasonally adjusted interpolation from the clean neighbouring months; else profile × year level."""
        i = y * 12 + m - 1
        nb = [(j, good[(site, car, j)]) for j in (i - 1, i + 1) if (site, car, j) in good]
        p_m = prof.get((site, car, m))
        if nb and p_m:
            ratios = [v / prof[(site, car, j % 12 + 1)] for j, v in nb if prof.get((site, car, j % 12 + 1))]
            if ratios:
                return float(p_m * sum(ratios) / len(ratios))
        return float((p_m or np.nan) * level.get((site, car, y), 1.0))

    em["est"] = [estimate(s, c, y, m) for s, c, y, m in zip(em.site_id, em.carrier, em.year, em.month)]
    u = em[em.rm >= 300].copy()
    u["fixed"] = np.where(u.mwh / 1000 / u.mmed >= 2.5, u.est, u.mwh / 1000)  # stacked unit error + spike
    s = em[(em.rm >= 2.5) & (em.rm < 300)]
    gaps = []
    for (site, car), g in em.groupby(["site_id", "carrier"]):
        idx = g.year * 12 + g.month - 1
        have = set(idx)
        for i in range(idx.min(), idx.max() + 1):
            if i not in have:
                y, m = i // 12, i % 12 + 1
                gaps.append({"record_key": f"energy:{site}:{y}-{m:02d}:{car}", "year": y, "est": estimate(site, car, y, m)})
    gp = pd.DataFrame(gaps, columns=["record_key", "year", "est"])
    return pd.concat([p for p in [
        _rows("energy_meter_readings", u, "unit_error", "energy_kwh_in_mwh", 0.95,
              [f"{v:.0f} is {r:.0f}× the same-month median: kWh reported in the MWh column"
               + (" (still a spike after ÷1000 → seasonal estimate)" if f != v / 1000 else "") for v, r, f in zip(u.value, u.rm, u.fixed)],
              [{"value": v, "month_median": m, "estimate": round(e, 3)} for v, m, e in zip(u.value, u.mmed, u.est)],
              [{"field": "value", "old_value": v, "new_value": round(f, 3)} for v, f in zip(u.value, u.fixed)]),
        _rows("energy_meter_readings", s, "meter_spike", "energy_seasonal_spike", 0.7,
              [f"{v:.1f} MWh is {r:.1f}× the same-month median (seasonal profile checked)" for v, r in zip(s.value, s.rm)],
              [{"value": v, "month_median": m, "ratio": round(r, 2)} for v, m, r in zip(s.value, s.mmed, s.rm)],
              [{"field": "value", "old_value": v, "new_value": round(e, 3)} for v, e in zip(s.value, s.est)]),
        _rows("energy_meter_readings", gp, "missing_record", "energy_month_gap", 0.9,
              "month missing inside the site × carrier series",
              [{"estimate_from": "neighbouring months, seasonally adjusted"}] * len(gp),
              [{"field": "value", "old_value": None, "new_value": round(e, 3)} for e in gp.est]),
    ] if not p.empty], ignore_index=True)


def fuel_detect(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    f = con.execute("SELECT * FROM raw_fuel_deliveries").df()
    u = f[(f.unit == "l") & (f.quantity < 100)]
    return _rows("fuel_deliveries", u, "unit_error", "fuel_m3_as_litres", 0.9,
                 [f"{q} l of {c} is implausibly small: m³ keyed as litres" for q, c in zip(u.quantity, u.carrier)],
                 [{"quantity": q, "unit": "l"} for q in u.quantity],
                 [{"field": "quantity", "old_value": q, "new_value": round(q * 1000, 3)} for q in u.quantity])


def goo_detect(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    g = con.execute("SELECT * FROM raw_goo_cancellations").df()
    reg = con.execute("""SELECT beneficiary_site AS site_id, consumption_year AS year, sum(mwh) AS reg_mwh,
                                max(CAST(substr(production_period_start, 1, 4) AS INTEGER)) AS reg_vintage
                         FROM raw_goo_registry_statement GROUP BY 1, 2""").df()
    m = g.merge(reg, on=["site_id", "year"], how="left")
    bad_v = m.reg_vintage.notna() & (m.vintage_year != m.reg_vintage)
    bad_q = m.reg_mwh.notna() & ((m.mwh_cancelled - m.reg_mwh).abs() > 0.01 * m.reg_mwh)
    x = m[bad_v | bad_q]
    fixes = [{"field": "vintage_year", "old_value": v, "new_value": int(rv)} if bv else
             {"field": "mwh_cancelled", "old_value": q, "new_value": round(rq, 3)}
             for v, rv, bv, q, rq in zip(x.vintage_year, x.reg_vintage, bad_v[x.index], x.mwh_cancelled, x.reg_mwh)]
    return _rows("goo_cancellations", x, "certificate_mismatch", "goo_vs_registry", 0.95,
                 [f"internal log vintage {v} / {q} MWh vs registry vintage {rv:.0f} / {rq:.0f} MWh (registry wins)" for v, q, rv, rq in zip(x.vintage_year, x.mwh_cancelled, x.reg_vintage, x.reg_mwh)],
                 [{"log_vintage": v, "registry_vintage": rv, "log_mwh": q, "registry_mwh": rq} for v, rv, q, rq in zip(x.vintage_year, x.reg_vintage, x.mwh_cancelled, x.reg_mwh)],
                 fixes)


def refrigerant_detect(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    r = con.execute("SELECT * FROM raw_refrigerant_service_log").df()
    r["sys_gas"] = r.groupby(["site_id", "system"]).refrigerant.transform(lambda s: s.mode().iloc[0])
    r["sys_med"] = r.groupby(["site_id", "system"]).kg_added.transform("median")
    w = r[(r.refrigerant == "R717_ammonia") & (r.sys_gas != "R717_ammonia")]
    u = r[r.kg_added >= 100 * r.sys_med]
    legit = r[(r.refrigerant == "R717_ammonia") & (r.sys_gas == "R717_ammonia")]
    return pd.concat([p for p in [
        _rows("refrigerant_service_log", w, "wrong_gas_code", "refrigerant_gas_vs_system", 0.85,
              [f"ammonia logged on '{s}', which runs {g}" for s, g in zip(w.system, w.sys_gas)],
              [{"system": s, "system_gas": g} for s, g in zip(w.system, w.sys_gas)],
              [{"field": "refrigerant", "old_value": "R717_ammonia", "new_value": g} for g in w.sys_gas]),
        _rows("refrigerant_service_log", u, "unit_error", "refrigerant_grams_as_kg", 0.9,
              [f"{k} kg is {k / m:.0f}× the system median: grams in the kg column" for k, m in zip(u.kg_added, u.sys_med)],
              [{"kg_added": k, "system_median": m} for k, m in zip(u.kg_added, u.sys_med)],
              [{"field": "kg_added", "old_value": k, "new_value": round(k / 1000, 4)} for k in u.kg_added]),
        _rows("refrigerant_service_log", legit, "wrong_gas_code", "allow_real_ammonia_system", 1.0,
              "checked, legitimate: ammonia on an ammonia system (GWP 0, safety not CO2e)",
              {"allow_list": ["R04"]}, None, status="legitimate"),
    ] if not p.empty], ignore_index=True)


def detect_all(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    parts = [erp_detect(erp_frame(con)), energy_detect(con), fuel_detect(con), goo_detect(con), refrigerant_detect(con)]
    return pd.concat([p for p in parts if not p.empty], ignore_index=True)
