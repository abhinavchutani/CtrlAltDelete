"""Build the mock fixtures in api/fixtures/*.json (task #83).

    python -m api.fixtures_build        # needs out/serve.duckdb (make snapshot); output is committed

The fixtures are MOCKS for the walking skeleton (API_MOCK=1): shapes are exact (every file is
validated against api/schemas.py here and in tests/test_api_contract.py), places are real pack
geometry (grid cells, farm points, parcel points), but the scenario values are illustrative, not
model output. Real values come from src/p_* (lane C). Deterministic: a fixed seed, no clock.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from api import schemas as S
from src.serve_db import connect

OUT = Path(__file__).resolve().parent / "fixtures"
SEED = 83
CROPS = [("FI_SW", "pea"), ("SE_SKANE", "pea"), ("FI_SW", "potato"), ("FI_SW", "carrot"),
         ("FI_SW", "spinach"), ("FI_SW", "turnip_rape")]
FARM_YEARS = (2026, 2031, 2040, 2060)
NOTE = "fixture: illustrative values, not model output"


def ev(kind: str, ref: str, label: str) -> S.EvidenceRef:
    return S.EvidenceRef(kind=kind, ref=ref, label=label)


# ── prediction ─────────────────────────────────────────────────────
def c3_mean_eur(con, climate: str) -> dict[tuple[str, str], float]:
    """v1's C3 expected € at risk per region × crop (results, metric eur_at_risk): the fixture's scale."""
    rows = con.execute("SELECT category, value FROM results WHERE metric = 'eur_at_risk' AND scenario = ?",
                       [climate]).fetchall()
    return {tuple(c.split(":")): float(v) for c, v in rows}


def regions(con, climate: str, years: list[int], rng: np.random.Generator) -> list[S.RegionYear]:
    eur = c3_mean_eur(con, climate)
    drift = {"ssp126": -0.1, "ssp245": -0.25, "ssp585": -0.45}[climate]  # % per year, illustrative
    out = []
    for region, crop in CROPS:
        base = eur.get((region, crop), 40_000.0)
        for y in years:
            if (region, crop, y) == ("SE_SKANE", "pea", 2026):
                change = -13.0  # the 2026 Swedish pea drought (v1: delivery change −13.0 %)
            else:
                change = drift * (y - 2026) + rng.normal(0, 9)
            bad = change < -20
            out.append(S.RegionYear(region=region, crop=crop, year=y, change_vs_baseline_pct=round(change),
                                    eur_at_risk=S.eur_band(base * (1 + max(-change, 0) / 25)), bad_year=bad))
    return out


ALERTS = {  # (year, month, region, crop, severity, kind, hazard, eur, lever)
    "ssp245": [
        (2027, 6, "SE_SKANE", "pea", "notable", "drought_flowering", "H1", 140_000, {"type": "irrigate", "crop": "pea"}),
        (2029, 6, "SE_SKANE", "pea", "critical", "heat_flowering", "H2", 310_000,
         {"type": "region_split", "fi_share": 0.45}),
        (2031, 8, "FI_SW", "potato", "notable", "blight_weather", "H6", 120_000, None),
        (2034, 5, "FI_SW", "pea", "notable", "waterlogging", "H3", 105_000,
         {"type": "crop_area", "crop": "pea", "region": "FI_SW", "change_pct": -10}),
        (2037, 6, "SE_SKANE", "pea", "critical", "risk_threshold", "H2", 280_000,
         {"type": "heat_tolerant_variety", "from_year": 2030, "penalty_cut": 0.3}),
        (2039, 9, "SE_SKANE", "pea", "notable", "wet_harvest", "H4", 160_000, {"type": "earlier_sowing", "crop": "pea"}),
    ],
    "ssp585": [
        (2028, 6, "SE_SKANE", "pea", "critical", "heat_flowering", "H2", 330_000,
         {"type": "heat_tolerant_variety", "from_year": 2030, "penalty_cut": 0.3}),
        (2032, 6, "SE_SKANE", "pea", "critical", "risk_threshold", "H2", 420_000,
         {"type": "region_split", "fi_share": 0.5}),
        (2036, 7, "FI_SW", "potato", "notable", "drought_flowering", "H1", 180_000, {"type": "irrigate", "crop": "potato"}),
        (2041, 8, "FI_SW", "potato", "critical", "blight_weather", "H6", 260_000, None),
        (2045, 6, "FI_SW", "pea", "notable", "heat_flowering", "H2", 150_000, {"type": "earlier_sowing", "crop": "pea"}),
        (2052, 5, "FI_SW", "turnip_rape", "notable", "beetle_weather", "H7", 110_000, None),
    ],
}
KIND_TITLE = {"drought_flowering": "drought at flowering", "heat_flowering": "heat at flowering",
              "waterlogging": "waterlogging after sowing", "wet_harvest": "rain at harvest",
              "blight_weather": "late-blight weather", "beetle_weather": "pollen-beetle weather",
              "risk_threshold": "bad-year odds pass 1 in 4", "supply_shortfall": "supply shortfall"}


def alerts(climate: str, horizon: int) -> list[S.Alert]:
    out = []
    for i, (y, m, region, crop, sev, kind, hz, eur, lever) in enumerate(ALERTS[climate]):
        if y > horizon:
            continue
        out.append(S.Alert(
            id=f"{climate}-{y}-{region}-{crop}-{kind}", year=y, month=m, region=region, crop=crop, severity=sev,
            kind=kind, hazard=hz, title=f"{crop.replace('_', ' ').capitalize()} {KIND_TITLE[kind]}, {region}",
            why=f"On this weather path, {crop} in {region} loses about {round(eur / 1000)}k € in {y} ({NOTE}).",
            eur_at_risk=S.eur_band(eur), suggested_lever=lever,
            evidence=[ev("result", f"C3:{climate}:{region}:{crop}:eur_at_risk", "v1 C3 € at risk (scale)"),
                      ev("weather", f"{climate}:{y}", f"weather path {climate} {y}")]))
    return out


def sim(con, sid: str, spec: S.ScenarioSpec, rng: np.random.Generator) -> S.SimResult:
    years = list(range(2026, spec.horizon_end + 1))
    worst = {"ssp126": "€100–250k", "ssp245": "€250k–1M", "ssp585": "€250k–1M"}[spec.climate]
    return S.SimResult(
        scenario_id=sid, spec=spec, years=years, regions=regions(con, spec.climate, years, rng),
        farms_url=f"/api/cube/{sid}/farms", alerts=alerts(spec.climate, spec.horizon_end),
        meters=S.Meters(eur_at_risk_per_year=worst, vs_current_plan="same", co2e_direction="same",
                        confidence="medium" if spec.horizon_end <= 2040 else "low",
                        confidence_why=["one plausible weather path", NOTE]
                        + ([] if spec.horizon_end <= 2040 else ["years beyond 2040"])),
        better=S.BetterOption(
            spec=S.ScenarioSpec(climate=spec.climate, horizon_end=spec.horizon_end, label="Irrigate dry pea + 45 % FI",
                                levers=[{"type": "irrigate", "crop": "pea"}, {"type": "region_split", "fi_share": 0.45}]),
            saves="€50–100k", why=f"Irrigation cuts the drought years and the split pools the two regions ({NOTE})."))


def presets() -> list[S.ScenarioPreset]:
    def p(sid, label, climate, levers=(), horizon=2040):
        return S.ScenarioPreset(scenario_id=sid, label=label,
                                spec=S.ScenarioSpec(climate=climate, horizon_end=horizon, levers=list(levers), label=label))
    return [p("current_plan_ssp126", "Current plan, low emissions", "ssp126"),
            p("current_plan_ssp245", "Current plan, middle path", "ssp245"),
            p("current_plan_ssp585", "Current plan, high emissions", "ssp585", horizon=2060),
            p("irrigate_dry_pea_ssp245", "Irrigate dry pea fields", "ssp245", [{"type": "irrigate", "crop": "pea"}]),
            p("split_70_30_ssp245", "70/30 Finland–Sweden pea split", "ssp245",
              [{"type": "region_split", "fi_share": 0.7}]),
            p("heat_tolerant_pea_ssp585", "Heat-tolerant pea from 2030", "ssp585",
              [{"type": "heat_tolerant_variety", "from_year": 2030, "penalty_cut": 0.3}], horizon=2060)]


def farms(con, rng: np.random.Generator) -> list[S.FarmYear]:
    ids = [r[0] for r in con.execute("SELECT farm_id FROM clean_farm_registry ORDER BY farm_id").fetchall()]
    out = []
    for y in FARM_YEARS:
        ch = rng.normal(-0.3 * (y - 2026), 12, len(ids))
        out += [S.FarmYear(farm_id=f, year=y, change_vs_baseline_pct=round(float(c)),
                           risk="bad" if c < -20 else "watch" if c < -8 else "ok") for f, c in zip(ids, ch)]
    return out


def weather(con, climate: str, year: int, rng: np.random.Generator) -> S.WeatherFrame:
    cells = con.execute("SELECT cell_id, region, lat, lon FROM raw_climate_grid_cells ORDER BY cell_id").fetchall()
    warm = {"historical": 0.6, "ssp245": 1.3, "ssp585": 2.4}[climate]
    out = []
    for cid, region, lat, lon in cells:
        dry = 0.75 if (climate, year, region) == ("historical", 2026, "SE_SKANE") else 0.35 + 0.1 * warm
        out.append(S.WeatherCell(
            cell_id=cid, region=region, lat=lat, lon=lon, tmax_anom_c=round(warm + rng.normal(0, 0.3), 2),
            precip_anom_pct=round(-30 * dry + rng.normal(0, 6), 1), drought_index=round(float(np.clip(dry + rng.normal(0, 0.08), 0, 1)), 2),
            hot_days_flowering=int(max(0, round(warm * 2 + (3 if region == "SE_SKANE" else 0) + rng.normal(0, 1))))))
    return S.WeatherFrame(climate=climate, year=year, cells=out)


def hedge() -> S.Hedge:
    pts = []
    for k in range(21):
        s = k / 20
        exp_eur = 230_000 + 260_000 * (s - 0.5) ** 2   # illustrative U-shape
        tail = 300_000 + 1_400_000 * (s - 0.45) ** 2
        pts.append(S.HedgePoint(fi_share=round(s, 2), expected_loss=S.eur_band(exp_eur), tail_loss=S.eur_band(tail),
                                is_now=k == 6, is_best=k == 9))
    return S.Hedge(climate="ssp245", points=pts,
                   why=f"Moving 15 pp of pea to FI_SW cuts the 1-in-10-year loss by one band ({NOTE}).")


def pathways() -> list[S.PathwayItem]:
    rows = [("pea", "SE_SKANE", "ssp585", 2039, "A04", "Heat/drought-tolerant pea varieties (breeding partnership)", 2027,
             "3 seasons in a row with > 5 hot days at pea flowering in SE_SKANE", "assumption"),
            ("pea", "SE_SKANE", "ssp585", 2039, "A07", "Diversify sourcing regions (FI/SE portfolio)", 2038,
             "pooled pea shortfall > 15 % in 2 of 5 years", "simulated"),
            ("pea", "SE_SKANE", "ssp245", 2047, "A01", "Efficient irrigation systems", 2044,
             "flowering drought index > 0.6 in 3 of 5 seasons in SE_SKANE", "simulated"),
            ("potato", "FI_SW", "ssp585", None, "A12", "Blight-resistant varieties + forecast-based spraying", None,
             "more than 10 blight-risk days in July–August, 3 seasons running", "simulated_with_caveat")]
    return [S.PathwayItem(crop=c, region=r, climate=cl, threshold="bad-year odds > 1 in 4", tipping_year=t,
                          option_id=o, option=opt, decide_by=d, signpost=sg, simulated=sim_)
            for c, r, cl, t, o, opt, d, sg, sim_ in rows]


# ── retrieval (on hold: these fixtures are what /api/ask, /api/options, /api/board serve) ──
def options() -> list[S.AdaptationOption]:
    rows = [("A01", ["H1"], ["all"], "Efficient irrigation systems", "strategic", (2, 3), "high", "worse", "worse",
             "worse", "scenario_dependent", "simulated", {"type": "irrigate", "crop": "pea"}),
            ("A04", ["H1", "H2"], ["pea", "turnip_rape"], "Heat/drought-tolerant varieties (breeding partnership / trials)",
             "strategic", (8, 12), "med", "same", "same", "better", "no_regret", "assumption",
             {"type": "heat_tolerant_variety", "from_year": 2030, "penalty_cut": 0.3}),
            ("A06", ["H2", "H5"], ["pea", "turnip_rape"], "Change sowing time (earlier sowing to escape heat at flowering)",
             "pre_season", (1, 1), "low", "same", "same", "same", "no_regret", "simulated_with_caveat",
             {"type": "earlier_sowing", "crop": "pea"}),
            ("A07", ["H1", "H2", "H3", "H4", "H5"], ["all"], "Diversify sourcing regions (FI/SE portfolio)", "strategic",
             (1, 1), "med", "same", "same", "same", "no_regret", "simulated", {"type": "region_split", "fi_share": 0.45}),
            ("A08", ["H3"], ["all"], "Parcel selection: avoid poorly drained clay for sensitive crops", "pre_season",
             (1, 1), "low", "same", "better", "same", "no_regret", "simulated",
             {"type": "crop_area", "crop": "pea", "region": "FI_SW", "change_pct": -10})]
    return [S.AdaptationOption(option_id=o, hazards=h, crops=c, option=t, window=w, lead_time_yrs=lt, cost_level=cost,
                               ghg=g, nutrients=n, water=wa, robustness=rb, simulated=sm, lever=lv,
                               source_name="LIFE AgriAdapt; RISK_MITIGATION_AND_ADAPTATION.md §7",
                               source_url="https://agriadapt.eu/northern-region/")
            for o, h, c, t, w, lt, cost, g, n, wa, rb, sm, lv in rows]


OWNER = {"strategic": "R&D, Sourcing, CFO", "pre_season": "Agronomy, Procurement", "in_season": "Procurement, Supply chain"}


def board() -> list[S.BoardRow]:
    rows = [("Heat at flowering", "pea", "SE_SKANE", "H2", 310_000, 600_000, "Start heat-tolerant pea trials with a breeder",
             ["A04", "A06"], "strategic", 2027, "assumption"),
            ("Drought at flowering", "pea", "SE_SKANE", "H1", 140_000, 280_000, "Irrigate the most drought-exposed pea parcels",
             ["A01"], "strategic", 2044, "simulated"),
            ("Supply concentration", "pea", "SE_SKANE", "H2", 280_000, 520_000, "Move 15 pp of contracted pea volume to FI_SW",
             ["A07"], "strategic", 2038, "simulated"),
            ("Late-blight weather", "potato", "FI_SW", "H6", 120_000, None, "Forecast-based spraying + resistant varieties",
             ["A12"], "pre_season", None, "simulated_with_caveat")]
    return [S.BoardRow(row_id=f"current_plan_ssp245-{i + 1}", scenario_id="current_plan_ssp245", risk=risk, crop=c,
                       region=r, hazard=h, eur_at_risk=S.eur_band(e), eur_tail=S.eur_band(t) if t else None, action=a,
                       option_ids=ids, owner=OWNER[w], decide_by=d, trigger=f"signpost for {h} in {r}",
                       evidence=[ev("result", f"C3:ssp245:{r}:{c}:eur_at_risk", "v1 C3 € at risk"),
                                 ev("doc", "docs/RISK_MITIGATION_AND_ADAPTATION.md#7", "adaptation options KB")],
                       robustness="no_regret" if sm != "simulated_with_caveat" else "scenario_dependent", simulated=sm)
            for i, (risk, c, r, h, e, t, a, ids, w, d, sm) in enumerate(rows)]


def ask(con) -> list[S.AskOut]:
    se = con.execute("""SELECT year, value FROM results WHERE metric = 'delivery_change_pct'
                        AND category = 'SE_SKANE:pea' AND year BETWEEN 2021 AND 2026 ORDER BY year""").fetchall()
    return [
        S.AskOut(status="answered",
                 answer_md="Year-on-year change in pea deliveries from Swedish (SE_SKANE) farms, 2021–2026. "
                           f"In 2026 they fell {abs(se[-1][1]):.1f} % on 2025 (the drought year). *(fixture answer)*",
                 table={"columns": ["year", "delivery_change_pct"], "rows": [[y, round(v, 2)] for y, v in se]},
                 evidence=[ev("result", f"C:deliveries:SE_SKANE:pea:{y}", f"delivery change {y}") for y, _ in se],
                 report={"report_id": "fixture-pea-deliveries-se", "filename": "pea_deliveries_se_2021_2026.xlsx",
                         "url": "/api/report/fixture-pea-deliveries-se"},
                 pending_approval=True),
        S.AskOut(status="answered",
                 answer_md="A guarantee of origin counts only if its vintage year equals the consumption year, capped at "
                           "the site's consumption; the registry statement beats the internal log. *(fixture answer)*",
                 evidence=[ev("doc", "REASONING_LOG.md#goo", "GoO rule"),
                           ev("table_row", "raw_goo_registry_statement", "GoO registry statement")]),
        S.AskOut(status="not_in_data", answer_md="Not in the data: the pack has no 2019 energy meter readings. "
                                                 "*(fixture answer)*", evidence=[]),
    ]


def intents() -> dict[str, S.IntentOut]:
    t = "What if we irrigate the driest pea fields and move to a 70/30 Finland–Sweden split?"
    return {
        "simulate": S.IntentOut(door="simulate", text=t, heard=["climate: middle path", "irrigate dry pea fields",
                                                                "pea split 70 % Finland"],
                                spec=S.ScenarioSpec(climate="ssp245", horizon_end=2040, label="Irrigate + 70/30 split",
                                                    levers=[{"type": "irrigate", "crop": "pea"},
                                                            {"type": "region_split", "fi_share": 0.7}])),
        "ask": S.IntentOut(door="ask", text="How did pea deliveries from Swedish farms in 2026 compare with 2021?"),
    }


# ── geo ────────────────────────────────────────────────────────────
def geo_farms(con) -> dict:
    rows = con.execute("SELECT farm_id, region, lat, lon FROM clean_farm_registry ORDER BY farm_id").fetchall()
    return {"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [round(lon, 5), round(lat, 5)]},
         "properties": {"farm_id": f, "region": r}} for f, r, lat, lon in rows]}


def geo_parcels(con, n: int = 400) -> dict:
    """A sample of parcels as squares of their area around the parcel point (fixture only; V2-3 serves real ones)."""
    rows = con.execute("""SELECT p.parcel_id, p.farm_id, p.lat, p.lon, p.area_ha, c.crop FROM raw_parcels p
                          LEFT JOIN raw_parcel_crop_history_and_plan c ON c.parcel_id = p.parcel_id AND c.year = 2025
                          ORDER BY hash(p.parcel_id) LIMIT ?""", [n]).fetchall()
    feats = []
    for pid, fid, lat, lon, ha, crop in rows:
        half = (ha * 1e4) ** 0.5 / 2
        dy, dx = half / 111_320, half / (111_320 * np.cos(np.radians(lat)))
        ring = [[round(lon + sx * dx, 5), round(lat + sy * dy, 5)] for sx, sy in [(-1, -1), (1, -1), (1, 1), (-1, 1), (-1, -1)]]
        feats.append({"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [ring]},
                      "properties": {"parcel_id": pid, "farm_id": fid, "area_ha": round(ha, 2), "crop": crop}})
    return {"type": "FeatureCollection", "features": feats}


def dump(name: str, obj, indent: int | None = 1) -> None:
    if isinstance(obj, list):
        obj = [o.model_dump(mode="json") if hasattr(o, "model_dump") else o for o in obj]
    elif hasattr(obj, "model_dump"):
        obj = obj.model_dump(mode="json")
    elif isinstance(obj, dict):
        obj = {k: v.model_dump(mode="json") if hasattr(v, "model_dump") else v for k, v in obj.items()}
    (OUT / f"{name}.json").write_text(json.dumps(obj, indent=indent, ensure_ascii=False) + "\n")


def main() -> None:
    OUT.mkdir(exist_ok=True)
    rng = np.random.default_rng(SEED)
    con = connect()
    ps = presets()
    dump("scenarios", ps)
    for sid in ("current_plan_ssp245", "current_plan_ssp585"):
        spec = next(p.spec for p in ps if p.scenario_id == sid)
        dump(f"scenario_{sid}", sim(con, sid, spec, rng), indent=None)
    dump("farms", farms(con, rng), indent=None)
    dump("weather", [weather(con, c, y, rng) for c, y in [("historical", 2026), ("ssp245", 2035), ("ssp585", 2050)]],
         indent=None)
    dump("hedge", hedge())
    dump("pathways", pathways())
    dump("options", options())
    dump("board", board())
    dump("ask", ask(con))
    dump("intent", intents())
    dump("geo_farms", geo_farms(con), indent=None)
    dump("geo_parcels", geo_parcels(con), indent=None)
    print(f"fixtures → {OUT} ({len(list(OUT.glob('*.json')))} files)")


if __name__ == "__main__":
    main()
