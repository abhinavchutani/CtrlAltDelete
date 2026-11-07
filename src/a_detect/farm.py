"""Farm survey + farm registry detectors (task #7). Rules from REASONING_LOG R07; thresholds
tuned on the public 2023–24 dev labels (see docs/BASELINES.md / PR notes).

* area_mismatch       survey area vs the farm's declared parcels for that crop and year (±10 %)
* decimal_shift       n_mineral_kg_ha ≥5× or ≤0.2× the crop median (non-zero): ×10 / ÷10 typo
* outlier_implausible yield_t_ha ≥5× the crop median: ÷10 typo (low yields are real crop failures)
* soil_misreport      survey says "Mineral soil" but either the soil map puts ≥30 % of both that crop's area
                      and the farm's area that year on organic soil, or the same farm reported "Organic soil"
                      for the same crop in another year and the map agrees (≥30 % of the crop's area or ≥50 % of
                      the farm). Map alone (≈ 88 % accurate) was 12/23 right on the dev years; these always
                      need individual expert review
* coordinate_swap     farm_registry lat/lon swapped (lat < lon in the Nordics)
"""
from __future__ import annotations

import duckdb
import numpy as np
import pandas as pd

from src.a_detect import CANDIDATE_COLUMNS, empty

AREA_TOL = 0.10
SHIFT_HI, SHIFT_LO = 5.0, 0.2
YIELD_HI = 5.0
SOIL_CROP_SHARE, SOIL_FARM_SHARE = 0.30, 0.50
SHIFT_FIELDS = ("n_mineral_kg_ha",)  # other numeric fields showed no planted shifts on dev


def survey_with_parcels(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Survey rows + declared parcel area and soil-map organic share (per crop and per farm-year)."""
    sv = con.execute("SELECT * FROM raw_farm_survey_fi").df()
    ph = con.execute("""
        SELECT h.farm_id, h.crop, h.year, sum(p.area_ha) AS parcel_ha,
               sum(CASE WHEN p.soil_class_soilmap = 'organic' THEN p.area_ha ELSE 0 END) AS organic_ha,
               count(*) AS n_parcels
        FROM raw_parcel_crop_history_and_plan h JOIN raw_parcels p USING (parcel_id)
        WHERE h.status = 'declared' GROUP BY 1, 2, 3""").df()
    fy = ph.groupby(["farm_id", "year"])[["parcel_ha", "organic_ha"]].sum().reset_index()
    fy["farm_organic_share"] = fy.organic_ha / fy.parcel_ha
    d = sv.merge(ph, on=["farm_id", "crop", "year"], how="left")
    d = d.merge(fy[["farm_id", "year", "farm_organic_share"]], on=["farm_id", "year"], how="left")
    d["crop_organic_share"] = d.organic_ha / d.parcel_ha
    org = d.soil_type_reported.eq("Organic soil").astype(int)
    d["crop_organic_reports"] = org.groupby([d.farm_id, d.crop]).transform("sum") - org  # other years only
    return d


def _cands(rows: pd.DataFrame, **cols) -> pd.DataFrame:
    if rows.empty:
        return empty()
    out = pd.DataFrame({"table_name": "farm_survey", "record_key": rows.record_key.values,
                        "year": rows.year.values})
    for k, v in cols.items():
        out[k] = v if isinstance(v, (str, int, float)) else list(v)
    return out[CANDIDATE_COLUMNS]


def area_mismatch(d: pd.DataFrame) -> pd.DataFrame:
    r = d[d.parcel_ha.notna() & ((d.area_ha / d.parcel_ha - 1).abs() > AREA_TOL)]
    return _cands(r, issue_type="area_mismatch", rule_id="farm_area_vs_parcels",
                  confidence=np.clip(0.6 + (r.area_ha / r.parcel_ha - 1).abs(), 0, 0.99).round(2),
                  explanation=[f"survey area {a:.2f} ha vs {p:.2f} ha of declared parcels" for a, p in zip(r.area_ha, r.parcel_ha)],
                  evidence=[{"area_ha": a, "parcel_ha": round(p, 3)} for a, p in zip(r.area_ha, r.parcel_ha)],
                  proposed_fix=[{"field": "area_ha", "old_value": a, "new_value": round(p, 2)} for a, p in zip(r.area_ha, r.parcel_ha)])


def decimal_shift(d: pd.DataFrame) -> pd.DataFrame:
    out = []
    for f in SHIFT_FIELDS:
        med = d.groupby("crop")[f].transform("median")
        ratio = d[f] / med
        r = d.assign(med=med, ratio=ratio)[(d[f] > 0) & ((ratio >= SHIFT_HI) | (ratio <= SHIFT_LO))]
        factor = np.where(r.ratio >= SHIFT_HI, 0.1, 10.0)
        out.append(_cands(r, issue_type="decimal_shift", rule_id=f"farm_{f}_x10",
                          confidence=0.9,
                          explanation=[f"{f} {v} is {q:.1f}× the {c} median {m:.1f}: likely a ×10 slip" for v, q, c, m in zip(r[f], r.ratio, r.crop, r.med)],
                          evidence=[{"value": v, "crop_median": m, "ratio": round(q, 3)} for v, m, q in zip(r[f], r.med, r.ratio)],
                          proposed_fix=[{"field": f, "old_value": v, "new_value": round(v * k, 2)} for v, k in zip(r[f], factor)]))
    return pd.concat(out, ignore_index=True) if out else empty()


def yield_outlier(d: pd.DataFrame) -> pd.DataFrame:
    med = d.groupby("crop").yield_t_ha.transform("median")
    r = d.assign(med=med)[d.yield_t_ha / med >= YIELD_HI]
    return _cands(r, issue_type="outlier_implausible", rule_id="farm_yield_x10",
                  confidence=0.9,
                  explanation=[f"yield {y} t/ha is {y / m:.1f}× the {c} median {m:.2f}" for y, m, c in zip(r.yield_t_ha, r.med, r.crop)],
                  evidence=[{"yield_t_ha": y, "crop_median": m} for y, m in zip(r.yield_t_ha, r.med)],
                  proposed_fix=[{"field": "yield_t_ha", "old_value": y, "new_value": round(y / 10, 3)} for y in r.yield_t_ha])


def soil_misreport(d: pd.DataFrame) -> pd.DataFrame:
    cs, fs = d.crop_organic_share.fillna(0), d.farm_organic_share.fillna(0)
    hist = d.get("crop_organic_reports", pd.Series(0, index=d.index)).fillna(0) > 0
    both = (cs >= SOIL_CROP_SHARE) & (fs >= SOIL_CROP_SHARE)
    hit = d.soil_type_reported.eq("Mineral soil") & (both | (hist & ((cs >= SOIL_CROP_SHARE) | (fs >= SOIL_FARM_SHARE))))
    r = d.assign(cs=cs, fs=fs)[hit]
    conf = np.where(both[hit], 0.85, 0.75)
    return _cands(r, issue_type="soil_misreport", rule_id="farm_soilmap_organic",
                  confidence=conf,
                  explanation=[f"survey says mineral; soil map: {c:.0%} of this crop's area and {f:.0%} of the farm is organic" for c, f in zip(r.cs, r.fs)],
                  evidence=[{"crop_organic_share": round(c, 3), "farm_organic_share": round(f, 3), "soil_map_accuracy": 0.88} for c, f in zip(r.cs, r.fs)],
                  proposed_fix=[{"field": "soil_type_reported", "old_value": "Mineral soil", "new_value": "Organic soil"} for _ in range(len(r))])


def coordinate_swap(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    reg = con.execute("SELECT record_key, farm_id, lat, lon, joined_year FROM raw_farm_registry").df()
    r = reg[reg.lat < reg.lon]
    if r.empty:
        return empty()
    return pd.DataFrame({
        "table_name": "farm_registry", "record_key": r.record_key.values, "year": None,
        "issue_type": "coordinate_swap", "confidence": 0.95, "rule_id": "farm_latlon_swapped",
        "explanation": [f"lat {a} < lon {o}: impossible for Finland/Sweden, coordinates swapped" for a, o in zip(r.lat, r.lon)],
        "evidence": [{"lat": a, "lon": o} for a, o in zip(r.lat, r.lon)],
        "proposed_fix": [{"field": "lat,lon", "old_value": f"{a},{o}", "new_value": f"{o},{a}"} for a, o in zip(r.lat, r.lon)],
    })[CANDIDATE_COLUMNS]


def detect_all(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    d = survey_with_parcels(con)
    parts = [area_mismatch(d), decimal_shift(d), yield_outlier(d), soil_misreport(d), coordinate_swap(con)]
    parts = [p for p in parts if not p.empty]
    return pd.concat(parts, ignore_index=True) if parts else empty()
