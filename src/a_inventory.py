"""Track A inventory (task #11): corrections → canonical tables → GHG inventory → results + lineage.

Run:  python -m src.a_inventory [--years 2023 2024 2025]     (needs `make a` first: issues + corrections)

Method = the pack's docs/METHODOLOGY.md (GHG Protocol, AR6 GWP100), re-implemented here so every
line carries lineage to record keys and factor ids. Key choices (REASONING_LOG):
* Only active corrections are applied: human-approved, or DEV-ASSUMED when NAVIGATOR_DEV_ASSUME=1.
* Duplicates are dropped, missing meter months / sea legs are added with their documented estimates.
* Contract-farm footprints include drained organic soils (R14) on the organic share of the crop area
  (clean_farm_survey.crop_organic_share; survey-reported "Organic soil" counts as fully organic).
* GoO counts only for its own vintage year, capped at site consumption (R05); biogenic CO2 is a memo (R10).
* Results are written with status `draft` (only humans publish).
"""
from __future__ import annotations

import argparse
import json

import duckdb
import numpy as np
import pandas as pd

from src import a_factors as F
from src import lineage as L
from src.db import connect, git_sha

# Share of the year a site is inside the boundary (METHODOLOGY §1): Foodhills/Bjuv acquired 27 Nov 2025,
# operations included from December 2025; not in scope before.
EST_UNCERTAINTY = 0.05  # relative uncertainty assumed for estimated (missing / spike-replaced) meter months
IN_SCOPE_FRACTION = {("S-BJU", 2025): 1 / 12, **{("S-BJU", y): 0.0 for y in range(2019, 2025)}}

TABLES = {  # issue table_name → raw table
    "erp_purchase_lines": "raw_erp_purchase_lines", "energy_meter_readings": "raw_energy_meter_readings",
    "fuel_deliveries": "raw_fuel_deliveries", "goo_cancellations": "raw_goo_cancellations",
    "refrigerant_service_log": "raw_refrigerant_service_log", "waste_transfer_notes": "raw_waste_transfer_notes",
    "travel_bookings": "raw_travel_bookings", "commuting_survey": "raw_commuting_survey",
    "shipments": "raw_shipments", "supplier_pcfs": "raw_supplier_pcfs", "farm_survey": "raw_farm_survey_fi",
}


# ── 1. corrections → clean tables ─────────────────────────────────────
def active_corrections(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    dev = "OR c.approved_by = 'DEV-ASSUMED'" if L.dev_mode() else ""
    return con.execute(f"""
        SELECT i.table_name, c.correction_id, c.record_key, c.field, c.new_value
        FROM corrections c JOIN issues i USING (issue_id)
        WHERE i.status <> 'rejected' AND (c.approved_by <> 'DEV-ASSUMED' {dev})""").df()


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def apply_corrections(raw: pd.DataFrame, corr: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Returns (clean rows, corrections for records not present = additions)."""
    df = raw.copy()
    df["correction_ids"] = ""
    pos = {k: i for i, k in zip(df.index, df.record_key)}
    drop, missing = [], []
    for c in corr.itertuples(index=False):
        i = pos.get(c.record_key)
        if i is None:
            missing.append(c)
            continue
        if c.field in ("*", "use"):
            drop.append(i)
        else:
            for f, v in zip(c.field.split(","), str(c.new_value).split(",") if "," in c.field else [c.new_value]):
                df.at[i, f] = _num(v) if df[f].dtype.kind in "if" else v
        df.at[i, "correction_ids"] = ",".join(filter(None, [df.at[i, "correction_ids"], c.correction_id]))
    return df.drop(index=drop), pd.DataFrame(missing)


def clean_tables(con: duckdb.DuckDBPyConnection) -> dict[str, pd.DataFrame]:
    corr = active_corrections(con)
    out = {}
    for t, raw in TABLES.items():
        df, add = apply_corrections(con.execute(f"SELECT * FROM {raw}").df(), corr[corr.table_name == t])
        if t == "energy_meter_readings" and len(add):
            parts = add.record_key.str.split(":", expand=True)
            extra = pd.DataFrame({"record_key": add.record_key, "site_id": parts[1],
                                  "year": parts[2].str[:4].astype(int), "month": parts[2].str[5:7].astype(int),
                                  "carrier": parts[3], "value": add.new_value.map(_num), "unit": "MWh",
                                  "correction_ids": add.correction_id})
            df = pd.concat([df, extra.dropna(subset=["value"])], ignore_index=True)
        if t == "shipments" and len(add):
            parts = add.record_key.str.split(":", expand=True)
            years = df.drop_duplicates("ref_doc").set_index("ref_doc").year
            extra = pd.DataFrame({"record_key": add.record_key, "ref_doc": parts[1], "ef_id": parts[2],
                                  "direction": "inbound", "tkm": add.new_value.map(_num),
                                  "correction_ids": add.correction_id})
            extra["year"] = extra.ref_doc.map(years)
            df = pd.concat([df, extra.dropna(subset=["tkm", "year"])], ignore_index=True)
        out[t] = df
    return out


# ── 2. canonical tables ───────────────────────────────────────────────
def farm_components(sv: pd.DataFrame) -> dict[str, np.ndarray]:
    """Cradle-to-farm-gate kg CO2e/ha by component (METHODOLOGY §5). `organic_full` is the drained-organic-soil
    add-on for a 100 % organic crop area. FLAG (SBTi) = direct + indirect N2O, liming, organic soils."""
    E = F.FARM_EF
    n2o = E["n2o_n_to_n2o"] * E["n2o_gwp"]
    nmin, nman = sv.n_mineral_kg_ha.fillna(0).values, sv.n_manure_kg_ha.fillna(0).values
    p = sv.p_kg_ha.fillna(0).values
    yld = sv.yield_t_ha.values
    res_n = sv.crop.map(F.RESIDUE_N_PER_T).values * yld
    low = sv.fertiliser_product.fillna("").str.contains("low-carbon").values
    kwh = sv.crop.map(F.KWH_PER_T).values * yld + np.where(sv.irrigated.fillna(False).astype(bool).values, 180.0, 0.0)
    return {
        "fertiliser": nmin * np.where(low, E["fert_n_prod_lowcarbon"], E["fert_n_prod"]) + p * E["fert_p_prod"] + p * 2.2 * E["fert_k_prod"],
        "n2o_direct": (nmin * E["ef1_synthetic"] + (nman + res_n) * E["ef1_organic"]) * n2o,
        "n2o_indirect": ((nmin * E["frac_gasf"] + nman * E["frac_gasm"]) * E["ef4_n2o_n"] + (nmin + nman + res_n) * E["frac_leach"] * E["ef5_n2o_n"]) * n2o,
        "diesel": sv.diesel_l_ha.fillna(0).values * (E["diesel_ttw"] + E["diesel_wtt"]),
        "lime": sv.lime_t_ha.fillna(0).values * E["lime"] * 1000,
        "sprays": sv.sprays.fillna(0).values * E["spray_pass"],
        "electricity": kwh * 0.03,
        "organic_full": np.full(len(sv), E["org_soil_co2_t_ha"] * 1000 + E["org_soil_n2o_n_kg_ha"] * n2o),
    }


FLAG_COMPONENTS = ("n2o_direct", "n2o_indirect", "lime")  # + organic soils (METHODOLOGY §5)


def farm_kg_per_ha(sv: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """(mineral-soil kg CO2e/ha, organic-soil add-on for a 100 % organic area)."""
    c = farm_components(sv)
    mineral = sum(v for k, v in c.items() if k != "organic_full")
    return mineral, c["organic_full"]


def farm_footprints(con: duckdb.DuckDBPyConnection, sv: pd.DataFrame, erp: pd.DataFrame,
                    with_organic: bool = True) -> pd.DataFrame:
    shares = con.execute("SELECT record_key, crop_organic_share FROM clean_farm_survey").df() \
        if con.execute("SELECT count(*) FROM information_schema.tables WHERE table_name='clean_farm_survey'").fetchall()[0][0] else \
        pd.DataFrame(columns=["record_key", "crop_organic_share"])
    sv = sv.merge(shares, on="record_key", how="left")
    share = sv.crop_organic_share.fillna(0).clip(0, 1)
    share = np.where(sv.soil_type_reported.str.lower().str.startswith("organic"), 1.0, share)
    comp = farm_components(sv)
    mineral = sum(v for k, v in comp.items() if k != "organic_full")
    org = share * comp["organic_full"] if with_organic else 0.0
    sv["kg_ha"] = mineral + org
    sv["flag_kg_ha"] = sum(comp[k] for k in FLAG_COMPONENTS) + org
    sv["kg_per_kg"] = sv.kg_ha / (sv.yield_t_ha * 1000)
    sv["flag_share"] = sv.flag_kg_ha / sv.kg_ha
    d = erp[erp.material_id.isin(F.CROP_MATERIAL)].copy()
    d["crop"] = d.material_id.map(F.CROP_MATERIAL)
    d = d.groupby(["supplier_id", "crop", "year"]).agg(qty_kg=("qty_kg", "sum"), keys=("record_key", list)).reset_index()
    d = d.rename(columns={"supplier_id": "farm_id"}).merge(
        sv[["farm_id", "crop", "year", "kg_per_kg", "flag_share", "record_key"]].rename(columns={"record_key": "survey_key"}),
        on=["farm_id", "crop", "year"], how="left")
    avg = sv.groupby(["crop", "year"]).kg_per_kg.median()
    d["kg_per_kg"] = d.kg_per_kg.fillna(pd.Series(list(zip(d.crop, d.year))).map(avg))
    fs = sv.groupby(["crop", "year"]).flag_share.median()
    d["flag_share"] = d.flag_share.fillna(pd.Series(list(zip(d.crop, d.year))).map(fs))
    d["tco2e"] = d.qty_kg * d.kg_per_kg / 1000
    d["flag_tco2e"] = d.tco2e * d.flag_share
    d["region"] = "FI_SW"
    return d


def canonical(con: duckdb.DuckDBPyConnection, c: dict[str, pd.DataFrame], with_organic: bool = True) -> dict:
    q = lambda s: con.execute(s).df()
    T = {"sites": q("SELECT * FROM raw_sites"), "materials": q("SELECT * FROM raw_materials"),
         "ef_library": q("SELECT * FROM raw_emission_factor_library"),
         "heat_suppliers": q("SELECT * FROM raw_heat_supplier_factors"), "headcount": q("SELECT * FROM raw_headcount"),
         "warehousing": q("SELECT * FROM raw_frozen_warehousing"), "wastewater": q("SELECT * FROM raw_wastewater_third_party"),
         "sales": q("SELECT * FROM raw_sales_volumes")}
    erp = c["erp_purchase_lines"].copy()
    erp["year"] = erp.posting_date.str[:4].astype(int)
    erp["qty_kg"] = np.where(erp.uom == "TO", erp.quantity * 1000, np.where(erp.uom == "KG", erp.quantity, 0.0))
    erp["amount_eur"] = erp.net_amount / erp.currency.map(F.FX_PER_EUR).fillna(1.0)
    T["purchases"] = erp
    em = c["energy_meter_readings"].copy()
    em["mwh"] = np.where(em.unit == "kWh", em.value / 1000, em.value)
    fd = c["fuel_deliveries"]
    stock = q("SELECT site_id, carrier, year, stock_change FROM raw_fuel_stock_changes")
    fy = fd.groupby(["site_id", "carrier", "year"]).agg(quantity=("quantity", "sum"), keys=("record_key", list)).reset_index()
    fy = fy.merge(stock, on=["site_id", "carrier", "year"], how="left").fillna({"stock_change": 0})
    fy["mwh"] = (fy.quantity - fy.stock_change) * fy.carrier.map(F.NCV_MWH)
    em["keys"] = em.record_key.map(lambda k: [k])
    em["est_mwh"] = np.where(em.correction_ids.fillna("") != "", em.mwh, 0.0)  # months we had to estimate or fix
    fy["est_mwh"] = 0.0
    T["energy"] = pd.concat([em[["site_id", "year", "carrier", "mwh", "keys", "est_mwh"]],
                             fy[["site_id", "year", "carrier", "mwh", "keys", "est_mwh"]]], ignore_index=True)
    T["refrigerants"] = c["refrigerant_service_log"]
    reg = q("""SELECT beneficiary_site AS site_id, consumption_year AS year, mwh AS mwh_cancelled,
                      CAST(substr(production_period_start, 1, 4) AS INTEGER) AS vintage_year, cancellation_id
               FROM raw_goo_registry_statement""")
    reg["record_key"] = "goo:" + reg.site_id + ":" + reg.year.astype(str) + ":" + reg.cancellation_id
    T["goo"] = reg  # the registry statement is authoritative (R05); the internal log is only checked against it
    w = c["waste_transfer_notes"].copy()
    w["t"] = w.quantity / 1000
    efmap = {"anaerobic_digestion": "EF-WASTE-BIO-AD", "composting": "EF-WASTE-BIO-COMPOST", "incineration": "EF-WASTE-MIXED-INC",
             "recycling": "EF-WASTE-RECYCLE", "landfill_codigestion": "EF-WASTE-SPENTEARTH"}
    w["ef_id"] = w.treatment.map(efmap)
    w.loc[w.waste_stream == "plastic_waste", "ef_id"] = "EF-WASTE-PLASTIC-INC"
    T["waste"] = w
    T["travel"], T["commuting_survey"], T["shipments"] = c["travel_bookings"], c["commuting_survey"], c["shipments"]
    p = c["supplier_pcfs"]
    p = p[p.declared_unit.eq("kilogram")]
    T["pcf_used"] = p.rename(columns={"pcf_excluding_biogenic": "kgco2e_per_kg"})[["year", "supplier_id", "material_id", "kgco2e_per_kg", "record_key"]]
    T["farm_footprints"] = farm_footprints(con, c["farm_survey"], erp, with_organic)
    return T


# ── 3. calculator (METHODOLOGY §3–4) ──────────────────────────────────
def compute(T: dict, year: int) -> pd.DataFrame:
    EF = dict(zip(T["ef_library"].ef_id, T["ef_library"].kgco2e_per_unit))
    rows: list[dict] = []

    def add(scope, cat, item, t, basis, records=(), factors=()):
        rows.append(dict(year=year, scope=scope, category=cat, line_item=item, tco2e=float(t), basis=basis,
                         records=list(records), factors=list(factors)))

    en = T["energy"][T["energy"].year == year]
    fuels = en[~en.carrier.isin(["electricity", "steam", "district_heat"])]
    bio = 0.0
    for (site, car), g in fuels.groupby(["site_id", "carrier"]):
        mwh = g.mwh.sum()
        add("scope1", "stationary_and_mobile_combustion", f"{site}:{car}", mwh * F.FUEL_EF_T_PER_MWH[car],
            "fuel MWh × fossil EF", sum(g["keys"], []), [f"fuel:{car}"])
        bio += mwh * F.FUEL_BIOGENIC_T_PER_MWH.get(car, 0.0)
    rf = T["refrigerants"][T["refrigerants"].year == year]
    for (site, gas), g in rf.groupby(["site_id", "refrigerant"]):
        add("scope1", "fugitive_refrigerants", f"{site}:{gas}", g.kg_added.sum() * F.REFRIGERANT_GWP[gas] / 1000,
            "kg top-up × GWP100", g.record_key, [f"gwp:{gas}"])
    country = T["sites"].set_index("site_id").country.to_dict()
    g0 = T["goo"][(T["goo"].year == year) & (T["goo"].vintage_year == year)]
    goo = g0.groupby("site_id").mwh_cancelled.sum().to_dict()
    goo_keys = g0.groupby("site_id").record_key.agg(list).to_dict()
    for site, g in en[en.carrier == "electricity"].groupby("site_id"):
        mwh, c = g.mwh.sum(), country.get(site, "FI")
        lb = (F.GRID_FI_LB if c == "FI" else F.GRID_SE_LB)[year]
        res = (F.RESIDUAL_FI if c == "FI" else F.RESIDUAL_SE)[year]
        covered = min(mwh, goo.get(site, 0.0))
        basis = "uncovered MWh × residual mix"
        gap, est = mwh - covered, g.est_mwh.sum()
        if goo.get(site, 0.0) > 0 and 0 < gap <= EST_UNCERTAINTY * est:
            covered, basis = mwh, (f"GoO covers metered MWh; the {gap:.1f} MWh gap is within the ±{EST_UNCERTAINTY:.0%} "
                                   f"uncertainty of {est:.0f} MWh of estimated meter months, so treated as covered")
        keys = sum(g["keys"], [])
        add("scope2_location", "purchased_electricity", site, mwh * lb, "MWh × grid average", keys, [f"grid_lb:{c}:{year}"])
        add("scope2_market", "purchased_electricity", site, (mwh - covered) * res, basis,
            keys + goo_keys.get(site, []), [f"residual:{c}:{year}"])
    heat = en[en.carrier.isin(["steam", "district_heat"])]
    hef = T["heat_suppliers"]
    for site, g in heat.groupby("site_id"):
        mwh = g.mwh.sum()
        sup = hef[(hef.site_id == site) & (hef.year == year)]
        mb = float(sup.t_per_mwh.iloc[0]) if len(sup) else 0.0
        keys = sum(g["keys"], [])
        add("scope2_location", "purchased_heat_steam", site, mwh * F.HEAT_LB_EF[year], "MWh × national heat average", keys, [f"heat_lb:{year}"])
        add("scope2_market", "purchased_heat_steam", site, mwh * mb, "MWh × supplier-specific EF", keys, [f"heat_supplier:{site}:{year}"])
    pur = T["purchases"][T["purchases"].year == year]
    mm = T["materials"].set_index("material_id")
    svc = set(mm[mm.material_group == "service"].index)
    cap = set(mm[mm.material_group == "capex"].index)
    pcf = T["pcf_used"][T["pcf_used"].year == year].set_index(["supplier_id", "material_id"])
    for (mat, sup), g in pur[~pur.material_id.isin(svc | cap)].groupby(["material_id", "supplier_id"]):
        if mm.loc[mat].default_ef_id == "FARM":
            continue
        if (sup, mat) in pcf.index:
            r = pcf.loc[(sup, mat)]
            ef, basis, fac = float(r.kgco2e_per_kg), "supplier PCF (PACT)", [r.record_key]
        else:
            ef, basis, fac = EF[mm.loc[mat].default_ef_id], mm.loc[mat].default_ef_id, [mm.loc[mat].default_ef_id]
        add("scope3", "cat01_purchased_goods", f"{mat}:{sup}", g.qty_kg.sum() * ef / 1000, basis, g.record_key, fac)
    ff = T["farm_footprints"][T["farm_footprints"].year == year]
    for (crop, region), g in ff.groupby(["crop", "region"]):
        add("scope3", "cat01_purchased_goods", f"contract_farming:{region}:{crop}", g.tco2e.sum(),
            "farm-specific footprint × delivered kg", sum(g["keys"], []) + g.survey_key.dropna().tolist(), ["METHODOLOGY §5"])
    for mat, g in pur[pur.material_id.isin(svc)].groupby("material_id"):
        add("scope3", "cat01_purchased_services", mat, g.amount_eur.sum() * EF[mm.loc[mat].default_ef_id] / 1000,
            "spend × EEIO", g.record_key, [mm.loc[mat].default_ef_id])
    for mat, g in pur[pur.material_id.isin(cap)].groupby("material_id"):
        add("scope3", "cat02_capital_goods", mat, g.amount_eur.sum() * EF[mm.loc[mat].default_ef_id] / 1000,
            "capex spend × EEIO", g.record_key, [mm.loc[mat].default_ef_id])
    for car, g in fuels.groupby("carrier"):
        add("scope3", "cat03_fuel_energy", f"wtt:{car}", g.mwh.sum() * EF[F.FUEL_WTT[car]] / 1000, "fuel MWh × WTT",
            sum(g["keys"], []), [F.FUEL_WTT[car]])
    for site, g in en[en.carrier == "electricity"].groupby("site_id"):
        efid = f"EF-ELEC-UPSTREAM-{country.get(site, 'FI')}"
        add("scope3", "cat03_fuel_energy", f"elec_upstream:{site}", g.mwh.sum() * EF[efid] / 1000, "MWh × upstream + T&D", sum(g["keys"], []), [efid])
    if len(heat):
        add("scope3", "cat03_fuel_energy", "heat_upstream", heat.mwh.sum() * EF["EF-HEAT-UPSTREAM"] / 1000, "MWh × upstream",
            sum(heat["keys"], []), ["EF-HEAT-UPSTREAM"])
    sh = T["shipments"][T["shipments"].year == year]
    for (direction, efid), g in sh.groupby(["direction", "ef_id"]):
        cat = "cat04_upstream_transport" if direction == "inbound" else "cat09_downstream_transport"
        add("scope3", cat, f"{direction}:{efid}", g.tkm.sum() * EF[efid] / 1000, "tkm × WTW EF", g.record_key, [efid])
    wh = T["warehousing"][T["warehousing"].year == year]
    if len(wh):
        add("scope3", "cat09_downstream_transport", "frozen_warehousing", wh.pallet_days.sum() * EF["EF-PALLETDAY-FROZEN"] / 1000,
            "pallet-days × EF", [], ["EF-PALLETDAY-FROZEN"])
    ws = T["waste"][T["waste"].year == year]
    for (site, stream, efid), g in ws.groupby(["site_id", "waste_stream", "ef_id"]):
        add("scope3", "cat05_waste", f"{site}:{stream}", g.t.sum() * EF[efid] / 1000, "t × treatment EF", g.record_key, [efid])
    ww = T["wastewater"][T["wastewater"].year == year]
    add("scope3", "cat05_waste", "wastewater_third_party", ww.m3.sum() * EF["EF-WASTEWATER-MUNI"] / 1000, "m3 × EF", [], ["EF-WASTEWATER-MUNI"])
    tr = T["travel"][T["travel"].year == year]
    for mode, efid, item in [("flight", "EF-PKM-FLIGHT-SHORT", "flights"), ("train", "EF-PKM-TRAIN", "rail")]:
        g = tr[tr["mode"] == mode]
        add("scope3", "cat06_business_travel", item, g.pkm.sum() * EF[efid] / 1000, "pkm × EF", g.record_key, [efid])
    add("scope3", "cat06_business_travel", "hotels", tr.nights.sum() * EF["EF-HOTEL-NIGHT"] / 1000, "nights × EF", tr.record_key, ["EF-HOTEL-NIGHT"])
    cs = T["commuting_survey"]
    hc = T["headcount"][T["headcount"].year == year].set_index("site_id").headcount
    mode_ef = {"car": EF["EF-PKM-CAR"], "carpool": EF["EF-PKM-CAR"] / 2, "bus": EF["EF-PKM-BUS"], "train": EF["EF-PKM-TRAIN"],
               "bike_walk": 0.0, "ev_car": 0.03}
    for site, g in cs.groupby("site_id"):
        frac = IN_SCOPE_FRACTION.get((site, year), 1.0)
        if frac == 0:
            continue
        per = frac * (g.one_way_km * 2 * g.days_on_site_per_week * 46 * g["mode"].map(mode_ef).fillna(EF["EF-PKM-CAR"])).mean()
        add("scope3", "cat07_employee_commuting", site, per * hc.get(site, 0) / 1000, "survey mean × headcount", g.record_key, ["EF-PKM-CAR", "EF-PKM-BUS"])
    sales = T["sales"][T["sales"].year == year]
    for (grp, market), g in sales.groupby(["product_group", "market"]):
        t = g.t_sold.sum()
        kwh = t * 1000 * F.USE_PHASE_KWH_PER_KG[grp]
        if kwh > 0:
            add("scope3", "cat11_use_of_sold_products", f"{grp}:{market}", kwh * F.MARKET_GRID[market][year] / 1000,
                "kWh × market grid (method choice R15)", [], [f"use_phase:{grp}", f"grid:{market}:{year}"])
        pl, bd = F.PACK_KG_PER_T[grp]
        add("scope3", "cat12_end_of_life", f"{grp}:{market}", t * pl / 1000 * F.EOL_PLASTIC_EF_T + t * bd / 1000 * F.EOL_BOARD_EF_T,
            "packaging t × EoL EF (method choice R15)", [], [f"packaging:{grp}"])
    out = pd.DataFrame(rows)
    out.attrs["biogenic_co2_t"] = bio
    return out


def summarise(inv: pd.DataFrame) -> pd.DataFrame:
    s = inv.copy()
    s.loc[s.category.isin(["cat01_purchased_goods", "cat01_purchased_services"]), "category"] = "cat01_purchased_goods_services"
    s = s.groupby(["scope", "category"]).tco2e.sum().reset_index()
    tot = [dict(scope="total", category=f"{k}_total", tco2e=inv[inv.scope == k].tco2e.sum())
           for k in ["scope1", "scope2_location", "scope2_market", "scope3"]]
    tot.append(dict(scope="memo", category="biogenic_co2_scope1", tco2e=inv.attrs.get("biogenic_co2_t", np.nan)))
    return pd.concat([s, pd.DataFrame(tot)], ignore_index=True)


def flag_share(T: dict, year: int) -> dict:
    """FLAG emissions (SBTi) and their share of S1 + S2 (market) + S3: contract-farm FLAG components (N2O,
    liming, organic soils) + purchased commodities × library flag_share (METHODOLOGY §5)."""
    inv = compute(T, year)
    total = inv[inv.scope.isin(["scope1", "scope2_market", "scope3"])].tco2e.sum()
    ff = T["farm_footprints"][T["farm_footprints"].year == year]
    farm_flag = float(ff.flag_tco2e.sum())
    lib = T["ef_library"].set_index("ef_id").flag_share.fillna(0)
    mm = T["materials"].set_index("material_id")
    goods = inv[(inv.category == "cat01_purchased_goods") & ~inv.line_item.str.startswith("contract_farming")]
    commodity_flag = 0.0
    for r in goods.itertuples(index=False):
        mat = r.line_item.split(":")[0]
        ef_id = mm.loc[mat].default_ef_id if mat in mm.index else None
        commodity_flag += r.tco2e * float(lib.get(ef_id, 0.0))
    flag = farm_flag + commodity_flag
    return {"year": year, "flag_t": round(flag, 1), "farm_flag_t": round(farm_flag, 1),
            "commodity_flag_t": round(commodity_flag, 1), "total_t": round(float(total), 1),
            "flag_share_pct": round(100 * flag / total, 2)}


def score_a2(sub: pd.DataFrame, key: pd.DataFrame) -> dict:
    t, p = key.set_index("category").tco2e, sub.set_index("category").tco2e
    tot, detail = 0.0, {}
    for cat, w in F.A2_WEIGHTS.items():
        if cat not in t or cat not in p:
            detail[cat] = None
            continue
        err = abs(p[cat] - t[cat]) / max(abs(t[cat]), 1e-9)
        tot += w * max(0.0, 1 - err / 0.05)
        detail[cat] = round(100 * err, 2)
    return {"score": round(100 * tot / sum(F.A2_WEIGHTS.values()), 2), "error_pct": detail}


# ── 4. results + lineage ──────────────────────────────────────────────
def write_results(con: duckdb.DuckDBPyConnection, inv: pd.DataFrame, summary: pd.DataFrame, year: int,
                  scenario: str = "actual") -> int:
    L.init_schema(con)
    sha, n = git_sha(), 0
    for r in inv.itertuples(index=False):
        lin = [L.src("record", k) for k in dict.fromkeys(r.records)] + [L.src("factor", f) for f in r.factors]
        if not lin:
            lin = [L.src("doc", "pack docs/METHODOLOGY.md")]
        L.write_result(con, f"A2:{year}:{scenario}:{r.scope}:{r.category}:{r.line_item}", metric="tco2e_line",
                       value=r.tco2e, unit="t CO2e", scope=r.scope, category=r.category, year=year, scenario=scenario,
                       method=r.basis, produced_by=f"a_inventory@{sha}", lineage=lin)
        n += 1
    for s in summary.itertuples(index=False):
        rid = f"A2:{year}:{scenario}:{s.scope}:{s.category}"
        parts = [f"A2:{year}:{scenario}:{r.scope}:{r.category}:{r.line_item}" for r in inv.itertuples(index=False)
                 if (s.category.startswith(r.scope) and s.scope == "total")
                 or r.category == s.category or (s.category == "cat01_purchased_goods_services" and r.category.startswith("cat01"))]
        L.write_result(con, rid, metric="tco2e", value=float(s.tco2e), unit="t CO2e", scope=s.scope, category=s.category,
                       year=year, scenario=scenario, method="sum of line items", produced_by=f"a_inventory@{sha}",
                       lineage=[L.src("doc", p) for p in parts] or [L.src("doc", "biogenic memo: METHODOLOGY §3")])
        n += 1
    return n


def run(con: duckdb.DuckDBPyConnection, years=(2023, 2024, 2025), write: bool = True) -> dict:
    c = clean_tables(con)
    T = canonical(con, c)
    out = {}
    for y in years:
        inv = compute(T, y)
        summ = summarise(inv)
        out[y] = summ
        if write:
            write_results(con, inv, summ, y)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", type=int, nargs="+", default=[2023, 2024, 2025])
    args = ap.parse_args()
    con = connect()
    res = run(con, args.years)
    scores = {}
    for y, summ in res.items():
        tbl = f"task_dev_A2_dev_inventory_{y}"
        if con.execute(f"SELECT count(*) FROM information_schema.tables WHERE table_name='{tbl}'").fetchall()[0][0]:
            scores[y] = score_a2(summ, con.execute(f"SELECT * FROM {tbl}").df())
            print(f"A2 dev {y}:", json.dumps(scores[y]))
        else:
            print(f"A2 {y}:", summ[summ.scope.isin(["total", "memo"])].round(1).to_dict("records"))
    if scores:
        from pathlib import Path
        from src.db import REPO_ROOT
        out = Path(REPO_ROOT) / "out" / "scores"
        out.mkdir(parents=True, exist_ok=True)
        (out / "A2_dev.json").write_text(json.dumps({"method": f"a_inventory@{git_sha()}", "scores": scores}, indent=1))


if __name__ == "__main__":
    main()
