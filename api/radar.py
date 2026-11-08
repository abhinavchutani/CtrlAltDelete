"""Field Radar v4 (light redesign): the Overview's numbers in one call, computed from the warm engine.

    POST /api/radar/outlook  {climate, levers}  -> Outlook

Every number comes from src.p_engine (the same cube /api/simulate uses) or the snapshot; nothing is typed in.
Exact € stay inside: only bands and buckets leave. The horizon is fixed at 2026–2040 (15 seasons) for every climate,
so the Low / Middle / High switch compares like with like.

Season status (shape + colour in the UI) is a € rule on the season's total € at risk (all contract crops):
    risk  ≥ €250k   (a "costly year", same edge as src.p_search.HIGH_EUR)
    watch ≥ €100k
    ok    otherwise
A field's status is its farm's yield class for that year (src.p_engine: ≤ −20 % bad, ≤ −10 % watch).
"""
from __future__ import annotations

import json
import threading
from collections import Counter
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel

from api import geo
from api import insight
from api import prediction as P
from api import schemas as S
from src import serve_db

HORIZON = 2040
LAST_OBSERVED = 2026  # the last season with observed weather (src.p_spec.FIRST_YEAR): "next season" is the one after
RISK_EUR, WATCH_EUR = 250_000, 100_000
Status = Literal["ok", "watch", "risk"]
Bucket = Literal["lt100k", "100k_250k", "250k_plus"]
FARM_STATUS: dict[str, Status] = {"ok": "ok", "watch": "watch", "bad": "risk"}
ISSUE_TYPE = {"drought_flowering": "drought", "heat_flowering": "heat"}

_cache: dict[str, tuple] = {}
_cache_lock = threading.Lock()


# ── shapes ──────────────────────────────────────────────────────────
class OutlookIn(BaseModel):
    climate: S.Climate = "ssp245"
    levers: list[S.Lever] = []


class SourceRef(BaseModel):
    node_id: str  # the knowledge-graph node this number came from
    label: str
    detail: str | None = None  # "2,683 rows", "5.1 % off", ...
    kind: Literal["data", "model", "doc", "tacit"]


class Season(BaseModel):
    year: int
    status: Status
    bucket: Bucket
    band: S.EurBand


class Issue(BaseModel):
    id: str
    year: int
    type: str  # drought | heat | other kinds (waterlogging, ...)
    label: str  # "Drought at flowering"
    status: Status  # critical → risk, notable → watch
    region: S.Region
    crop: str
    month: int | None
    eur_at_risk: S.EurBand | None
    rain_vs_normal_pct: int | None  # the stage month vs 1991–2020, region mean
    temp_vs_normal_c: float | None
    hot_days: float | None
    fields_below: int  # pea fields of the crop on farms ≥10 % below their normal yield that year
    farms_below: int
    why: str
    sources: list[SourceRef]


class Contract(BaseModel):  # one region × crop contract in one season
    region: S.Region
    crop: str
    band: S.EurBand
    status: Status  # the season € rule applied to this contract alone
    change_pct: float  # harvest vs the 1991–2020 normal for this region × crop


class FarmBadYears(BaseModel):  # one farm with at least one bad year after the last observed season
    farm_id: str
    region: S.Region
    pea_fields: int
    bad_years: list[int]


class FarmStatus(BaseModel):
    farm_id: str
    status: Status
    change_pct: float


class Outlook(BaseModel):
    climate: S.Climate
    levers: list[S.Lever]
    years: list[int]
    money: S.EurBand  # mean € at risk a year
    costly_years: int  # seasons ≥ €250k
    worst_year: int
    worst_band: S.EurBand
    seasons: list[Season]
    next_season: int  # the first season after the last observed one (2026)
    next_contracts: list[Contract]  # every contract crop's € at stake in next_season
    issues: list[Issue]
    focus_year: int  # the worst season: the Overview's "fields needing attention" / "where it hurts"
    fields_risk: int  # pea fields on 'bad' farms in focus_year
    fields_watch: int
    pea_fields: int
    farms_focus: list[FarmStatus]  # every farm's status in focus_year
    near_years: tuple[int, int]  # the next five seasons
    near_fields_hit: int  # pea fields on farms with at least one bad year in near_years
    near_farm_ids: list[str]  # those farms (pea growers only; the map filter)
    repeat_bins: list[int]  # farms by number of bad years after the last observed season: [0, 1, 2, 3+]
    repeat_years: tuple[int, int]
    repeat_farm_ids: list[str]  # farms with 2+ bad years (the map filter)
    repeat_region: S.Region | None  # where most of them are
    farms_hit: list[FarmBadYears]  # every farm with a bad year from next season on, most-hit first
    near_region: S.Region | None
    worst_region: S.Region | None
    contract_farms: int
    regions: list[S.Region]
    sources: list[SourceRef]
    synthetic: bool = True


# ── helpers ─────────────────────────────────────────────────────────
def status_of(eur: float) -> Status:
    return "risk" if eur >= RISK_EUR else "watch" if eur >= WATCH_EUR else "ok"


def bucket_of(eur: float) -> Bucket:
    return "250k_plus" if eur >= RISK_EUR else "100k_250k" if eur >= WATCH_EUR else "lt100k"


def _cubes(climate: str, levers: list[dict]):
    """(region × crop × year cube, farm × year cube, clean spec) on the warm engine, cached per spec."""
    from src import p_engine, p_spec

    P.ready("outlook")
    spec, _ = p_spec.validate({"climate": climate, "horizon_end": HORIZON, "levers": levers})
    key = json.dumps(spec, sort_keys=True)
    with _cache_lock:
        if key in _cache:
            return _cache[key]
    with P.ENGINE_LOCK:
        cube, farms = p_engine.run_spec(P.context(), spec)
    with _cache_lock:
        _cache[key] = (cube, farms, spec)
    return cube, farms, spec


def _farm_region() -> dict[str, str]:
    return {f["properties"]["farm_id"]: f["properties"]["region"] for f in geo.farms()["features"]}


def _pea_fields_by_farm() -> Counter:
    return Counter(f["properties"]["farm_id"] for f in geo.parcels()["features"] if f["properties"].get("crop") == "pea")


def provenance_sources() -> list[SourceRef]:
    """The receipt: what the numbers are built on, counted from the snapshot (api.insight.provenance)."""
    p = insight.provenance()
    out = [
        SourceRef(node_id="data:clean_farm_registry", label="Contract farms", detail=f"{p['farms']:,}", kind="data"),
        SourceRef(node_id="data:clean_farm_survey", label="Finnish harvest records",
                  detail=f"{p['fi_yield_records']:,} · {p['fi_yield_years'][0]}–{str(p['fi_yield_years'][1])[2:]}", kind="data"),
        SourceRef(node_id="data:raw_foodhills_odlingsdata_se", label="Skåne pea deliveries",
                  detail=f"{p['se_delivery_records']:,} · {p['se_delivery_years'][0]}–{str(p['se_delivery_years'][1])[2:]}", kind="data"),
        SourceRef(node_id="data:raw_weather_daily", label=f"Daily weather, {p['weather_cells']} grid cells",
                  detail=f"{p['weather_days'] / 1e6:.1f}M days", kind="data"),
    ]
    if p.get("backtest"):
        b = p["backtest"]
        yrs = b["test_years"]
        out.append(SourceRef(node_id="model:yield", label=f"Yield model, tested on {yrs[0]}–{str(yrs[-1])[2:]}",
                             detail=f"{b['model_error_pct']} % off", kind="model"))
    out.append(SourceRef(node_id="data:raw_climate_grid_cells", label="Climate futures",
                         detail=f"{len(p['climate_paths'])} paths to {p['climate_years'][1]}", kind="data"))
    return out


def _issue_sources(climate: str, year: int, region: str) -> list[SourceRef]:
    path = "historical" if year <= 2025 else climate
    name = "SW Finland" if region == "FI_SW" else "Skåne"
    return [SourceRef(node_id="data:raw_weather_daily", label=f"Weather, {name} cells", detail=f"{path} {year}", kind="data"),
            SourceRef(node_id="model:yield", label="Yield model", kind="model")]


def _majority(farm_ids: list[str], region_of: dict[str, str]):
    c = Counter(region_of.get(f) for f in farm_ids if region_of.get(f))
    return c.most_common(1)[0][0] if c else None


# ── the endpoint ────────────────────────────────────────────────────
def outlook(body: OutlookIn) -> Outlook:
    from src import p_alerts, p_season

    if not serve_db.exists():
        raise HTTPException(503, "out/serve.duckdb missing: run `make snapshot`")
    levers = [lv.model_dump(mode="json") for lv in body.levers]
    cube, farms, spec = _cubes(body.climate, levers)

    by_year = cube.groupby("year").eur_loss.sum()
    seasons = [Season(year=int(y), status=status_of(e), bucket=bucket_of(e), band=S.eur_band(float(e)))
               for y, e in by_year.items()]
    worst_year = int(by_year.idxmax())

    region_of = _farm_region()
    pea = _pea_fields_by_farm()
    # farms ≥10 % below normal, per (region, year) → fields of the alert's crop on them
    below = farms[farms.risk != "ok"]

    issues: list[Issue] = []
    with serve_db.connect() as con:
        for a in sorted(p_alerts.alerts("radar", spec, cube, None), key=lambda a: (a["year"], a["region"])):
            month = a.get("month")
            rain = temp = hot = None
            if month:
                m = next((x for x in p_season.months(con, body.climate, a["year"], a["region"])["months"]
                          if x["month"] == month), None)
                if m:
                    rain, temp, hot = m["precip_anom_pct"], m["tmean_anom_c"], m["hot_days"]
            fs = [f for f in below[below.year == a["year"]].farm_id if region_of.get(f) == a["region"]]
            n_fields = sum(pea[f] for f in fs) if a.get("crop") == "pea" else 0
            farms_hit = sum(1 for f in fs if pea[f]) if a.get("crop") == "pea" else len(fs)
            kind = a["kind"]
            issues.append(Issue(
                id=a["id"], year=a["year"], type=ISSUE_TYPE.get(kind, kind), label=kind.replace("_", " at ").capitalize()
                if kind in ISSUE_TYPE else kind.replace("_", " ").capitalize(),
                status="risk" if a["severity"] == "critical" else "watch", region=a["region"], crop=a.get("crop") or "",
                month=month, eur_at_risk=a.get("eur_at_risk"), rain_vs_normal_pct=rain, temp_vs_normal_c=temp,
                hot_days=hot, fields_below=n_fields, farms_below=farms_hit, why=a["why"],
                sources=_issue_sources(body.climate, a["year"], a["region"])))

    next_season = LAST_OBSERVED + 1
    nxt = cube[cube.year == next_season].sort_values("eur_loss", ascending=False)
    next_contracts = [Contract(region=r.region, crop=r.crop, band=S.eur_band(float(r.eur_loss)), status=status_of(float(r.eur_loss)),
                               change_pct=round(float(r.change_pct)))
                      for r in nxt.itertuples(index=False)]

    near = (next_season, next_season + 4)
    fut = farms[farms.year >= next_season]
    bad = fut[fut.risk == "bad"]
    near_farms = set(bad[bad.year <= near[1]].farm_id)
    near_fields_hit = sum(n for f, n in pea.items() if f in near_farms)
    per_farm = bad.groupby("farm_id").size()
    counts = [int(per_farm.get(f, 0)) for f in fut.farm_id.unique()]
    repeat_bins = [sum(c == k for c in counts) for k in (0, 1, 2)] + [sum(c >= 3 for c in counts)]
    repeat_ids = sorted(per_farm[per_farm >= 2].index)

    farms_hit = sorted(
        (FarmBadYears(farm_id=f, region=region_of[f], pea_fields=int(pea[f]),  # type: ignore[arg-type]
                      bad_years=sorted(int(y) for y in g.year)) for f, g in bad.groupby("farm_id") if f in region_of),
        key=lambda x: (-len(x.bad_years), x.bad_years[0], x.farm_id))

    fy = farms[farms.year == worst_year]
    status_by_farm = {r.farm_id: FARM_STATUS[r.risk] for r in fy.itertuples(index=False)}
    fields_risk = sum(n for f, n in pea.items() if status_by_farm.get(f) == "risk")
    fields_watch = sum(n for f, n in pea.items() if status_by_farm.get(f) == "watch")
    reg_loss = cube[cube.year == worst_year].groupby("region").eur_loss.sum()

    return Outlook(
        climate=body.climate, levers=body.levers, years=[s.year for s in seasons],
        money=S.eur_band(float(by_year.mean())), costly_years=sum(s.status == "risk" for s in seasons),
        worst_year=worst_year, worst_band=S.eur_band(float(by_year.max())), seasons=seasons, issues=issues,
        next_season=next_season, next_contracts=next_contracts,
        near_years=near, near_fields_hit=near_fields_hit, near_farm_ids=sorted(f for f in near_farms if pea[f]), repeat_bins=repeat_bins,
        repeat_years=(next_season, int(fut.year.max())), repeat_farm_ids=repeat_ids,
        repeat_region=_majority(repeat_ids, region_of), farms_hit=farms_hit, near_region=_majority(list(near_farms), region_of),
        focus_year=worst_year, fields_risk=fields_risk, fields_watch=fields_watch, pea_fields=sum(pea.values()),
        farms_focus=[FarmStatus(farm_id=r.farm_id, status=FARM_STATUS[r.risk], change_pct=round(float(r.change_pct), 1))
                     for r in fy.itertuples(index=False)],
        worst_region=str(reg_loss.idxmax()) if len(reg_loss) else None,  # type: ignore[arg-type]
        contract_farms=len(region_of), regions=sorted(set(region_of.values())),  # type: ignore[arg-type]
        sources=provenance_sources(),
    )
