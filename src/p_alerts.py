"""Prediction layer (v2): alerts, critical and notable only, on one plausible weather path (task #89, V2-7).

Rules run over the cube from p_engine (region × crop × year, exact € inside):
* critical: € at risk ≥ CRIT_EUR, or production < CRIT_SUPPLY × contracted, or the tipping marker
  (the 10-year rolling share of bad years first passes TIP_ODDS, as in p_pathways);
* notable:  € at risk ≥ NOTABLE_EUR, or a bad year (< 80 % of the 1991–2020 mean) on a contract crop.
Nothing below notable is sent. At most PER_YEAR per year and MAX_ALERTS per scenario: critical first, then by €.
Each alert's hazard (H1–H7) and kind come from the stress feature that cost the most yield that year (ridge
contribution vs the 1991–2020 baseline); an alert whose drop has no stress driver is not sent (no hazard to act on).
Texts are templates filled with computed numbers only; € appears only as a band. "On this weather path", never "will".
"""
from __future__ import annotations

import pandas as pd

from src import p_spec as S

CRIT_EUR, NOTABLE_EUR = 250_000.0, 100_000.0
CRIT_SUPPLY = 0.70
BAD_FRACTION = 0.80
TIP_ODDS, TIP_WINDOW = 0.25, 10
PER_YEAR, MAX_ALERTS = 2, 12
CONTRACT_CROPS = ("pea", "potato", "carrot", "spinach", "turnip_rape")

# stress feature prefix → (alert kind, hazard, stage month, label)
DRIVERS = [
    ("st_drought", "drought_flowering", "H1", 6, "drought in the sensitive stage"),
    ("st_hot", "heat_flowering", "H2", 6, "heat at flowering"),
    ("hot_days_tmax_ge_27", "heat_flowering", "H2", 6, "hot days (Tmax ≥ 27 °C)"),
    ("st_heavy_rain_after_sow", "waterlogging", "H3", 5, "waterlogging after sowing"),
    ("st_rain_before_harvest", "wet_harvest", "H4", 8, "rain before harvest"),
    ("st_season_len", "supply_shortfall", "H5", 8, "a short season"),
    ("st_immature", "supply_shortfall", "H5", 9, "crops not maturing in time"),
    ("st_gdd_deficit", "supply_shortfall", "H5", 9, "too little warmth to mature"),
    ("st_sow_doy", "supply_shortfall", "H5", 5, "late sowing"),
    ("st_blight_days", "blight_weather", "H6", 7, "late-blight weather"),
    ("st_beetle_days", "beetle_weather", "H7", 5, "pollen-beetle weather"),
]
TITLES = {"drought_flowering": "Flowering drought", "heat_flowering": "Heat at flowering", "waterlogging": "Waterlogging",
          "wet_harvest": "Wet harvest", "supply_shortfall": "Supply shortfall", "blight_weather": "Blight weather",
          "beetle_weather": "Pollen-beetle weather", "risk_threshold": "Bad-year odds pass 1 in 4"}


def classify(driver: str | None) -> tuple[str, str, int, str] | None:
    if not isinstance(driver, str):
        return None
    for prefix, kind, hazard, month, label in DRIVERS:
        if driver.startswith(prefix):
            return kind, hazard, month, label
    return None


def tipping_years(cube: pd.DataFrame) -> pd.DataFrame:
    """First year per region × crop where the trailing TIP_WINDOW-year share of bad years exceeds TIP_ODDS."""
    rows = []
    for (region, crop), g in cube.sort_values("year").groupby(["region", "crop"]):
        share = g.bad_year.astype(float).rolling(TIP_WINDOW, min_periods=TIP_WINDOW).mean()
        hit = g.year[share > TIP_ODDS]
        if len(hit):
            y = int(hit.iloc[0])
            rows.append({"region": region, "crop": crop, "year": y,
                         "bad_years": int(g[(g.year > y - TIP_WINDOW) & (g.year <= y)].bad_year.sum())})
    return pd.DataFrame(rows, columns=["region", "crop", "year", "bad_years"])


def candidates(cube: pd.DataFrame) -> pd.DataFrame:
    c = cube.copy()
    supply = c.t / c.contracted_t
    crit = (c.eur_loss >= CRIT_EUR) | (supply < CRIT_SUPPLY)
    notable = (c.eur_loss >= NOTABLE_EUR) | (c.bad_year & c.crop.isin(CONTRACT_CROPS))
    c["severity"] = pd.Series(pd.NA, index=c.index, dtype="object").where(~notable, "notable").where(~crit, "critical")
    return c[c.severity.notna()]


def _evidence(climate: str, region: str, crop: str, year: int) -> list[dict]:
    wx = "historical" if year <= S.FIRST_YEAR else climate
    return [{"kind": "weather", "ref": f"weather:{wx}:{year}", "label": f"Weather frame {wx} {year} (one plausible path)"},
            {"kind": "result", "ref": f"C2:{climate}:{region}:{crop}:p_bad_year", "label": "Ensemble bad-year odds 2041–60 (v1 C2)"},
            {"kind": "assumption", "ref": "p_engine:2025_mix_current_management",
             "label": "2025 parcel mix and current management held for every year"}]


def alerts(sid: str, spec: dict, cube: pd.DataFrame, suggest=None) -> list[dict]:
    """The scenario's alerts (dicts shaped like api.schemas.Alert). `suggest(region, crop, year, hazard)` → lever|None."""
    climate, out = spec["climate"], []
    for r in candidates(cube).itertuples(index=False):
        cls = classify(r.driver)
        if cls is None:
            continue
        kind, hazard, month, label = cls
        why = (f"On this weather path, {r.crop.replace('_', ' ')} in {r.region} reaches {r.t:,.0f} t in {r.year} "
               f"({r.change_pct:+.0f} % vs the 1991–2020 mean of {r.contracted_t:,.0f} t); the main stress is {label} "
               f"({r.driver_pct:+.0f} % of yield).")
        out.append({"id": f"{sid}:{r.region}:{r.crop}:{r.year}:{kind}", "year": int(r.year), "month": month,
                    "region": r.region, "crop": r.crop, "severity": r.severity, "kind": kind, "hazard": hazard,
                    "title": f"{TITLES[kind]}, {r.crop.replace('_', ' ')} {r.region}", "why": why,
                    "eur_at_risk": r.eur_band, "suggested_lever": suggest(r.region, r.crop, int(r.year), hazard) if suggest else None,
                    "evidence": _evidence(climate, r.region, r.crop, int(r.year)), "_eur": float(r.eur_loss)})
    by_cell = cube.set_index(["region", "crop", "year"])
    for t in tipping_years(cube).itertuples(index=False):
        row = by_cell.loc[(t.region, t.crop, t.year)]
        cls = classify(row.driver)
        hazard = cls[1] if cls else "H1"   # the threshold marker takes the hazard of that year's stress (default drought)
        why = (f"On this weather path, {t.crop.replace('_', ' ')} in {t.region} has {t.bad_years} bad years "
               f"(< {BAD_FRACTION:.0%} of the 1991–2020 mean) in the {TIP_WINDOW} years to {t.year}: the odds pass 1 in 4. "
               f"Start adaptation now.")
        out.append({"id": f"{sid}:{t.region}:{t.crop}:{t.year}:risk_threshold", "year": int(t.year), "month": None,
                    "region": t.region, "crop": t.crop, "severity": "critical", "kind": "risk_threshold", "hazard": hazard,
                    "title": f"{TITLES['risk_threshold']}, {t.crop.replace('_', ' ')} {t.region}", "why": why,
                    "eur_at_risk": row.eur_band, "suggested_lever": suggest(t.region, t.crop, int(t.year), hazard) if suggest else None,
                    "evidence": _evidence(climate, t.region, t.crop, int(t.year)), "_eur": float("inf")})
    return cap(out)


def cap(items: list[dict]) -> list[dict]:
    """Critical first, then by € (exact, internal); at most PER_YEAR per year and MAX_ALERTS in total."""
    items = sorted(items, key=lambda a: (a["severity"] != "critical", -a["_eur"], a["year"], a["id"]))
    kept, per_year = [], {}
    for a in items:
        if per_year.get(a["year"], 0) >= PER_YEAR:
            continue
        per_year[a["year"]] = per_year.get(a["year"], 0) + 1
        kept.append({k: v for k, v in a.items() if k != "_eur"})
        if len(kept) == MAX_ALERTS:
            break
    return sorted(kept, key=lambda a: (a["year"], a["severity"] != "critical", a["id"]))
