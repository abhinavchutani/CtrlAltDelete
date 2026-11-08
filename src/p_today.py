"""Prediction layer (v4 Overview): the season *so far* on one day, for the four daily widgets (task #127).

    from src.p_today import today
    today(con, "2026-06-18", climate="ssp245", crop="pea")

Run:  python -m src.p_today 2026-06-18 [climate] [crop]

Season-so-far = the stage model of src.c_features run on daily weather up to day D, nothing after it:
sowing (5-day mean ≥ the crop threshold from 1 April), stages by degree-days above 5 °C, and the soil-water
bucket (its daily AET only depends on earlier days). Stage indices and cumulative sums are computed once per
season and read at day D, which gives the same result as cutting the weather at D (both are causal); stage dates
after D are *expected* dates from 1991–2020, never the real ones.

Two signals, each since sowing and only inside the crop's season window [sowing, maturity):
    dryness  = 1 − ΣAET / ΣPET                (0 = no water stress, 1 = none of the demand met)
    hot days = days with Tmax ≥ 27 °C from the start of flowering (the sensitive stage)
"How unusual" ranks today's value against the same calendar day in each of the 30 normal years (1991–2020),
mid-rank percentile (ties count half). A region is the mean over its grid cells, each on its dominant soil.

Status of a region × crop on day D (one rule, used by every widget):
    risk  ◆  dryness or heat ≥ the 90th percentile, and the crop has started flowering
    watch ▲  ≥ the 75th percentile (and ≥ 90th before flowering)
    ok    ●  otherwise
"What changed since yesterday" diffs D against D−1: status up or down, a stage reached, a jump ≥ 10 points.

The weather is the synthetic twin: 'historical' up to 2026, then one SSP realisation. Not a forecast.
Deterministic; read-only on out/serve.duckdb.
"""
from __future__ import annotations

import sys
import threading
from dataclasses import dataclass
from datetime import date, timedelta
from functools import lru_cache

import duckdb
import numpy as np
import pandas as pd

from src import c_features as F
from src.p_weather import dominant_soil

NORMAL = (1991, 2020)
LAST_OBSERVED = 2026
YEARS = (2026, 2040)
CROP_YEAR = 2025  # the parcel mix every prediction holds (C2 rule; api.geo uses the same year)
SEASON_START = (4, 1)  # day 0 = 1 April (c_features.SEASON)
WATCH_PCT, RISK_PCT, JUMP_PTS = 75.0, 90.0, 10.0
REGION_CROPS: dict[str, tuple[str, ...]] = {"FI_SW": ("pea", "potato", "spinach", "carrot", "turnip_rape"),
                                            "SE_SKANE": ("pea",)}
STAGES = ("sown", "flowering", "fill", "harvest")  # c_features: sow → sens → fill → mature
STAGE_WORD = {"not_sown": "not sown yet", "sown": "growing", "flowering": "flowering", "fill": "filling",
              "harvest": "harvested"}
REGION_NAME = {"FI_SW": "SW Finland", "SE_SKANE": "Skåne"}
CROP_NAME = {"pea": "pea", "potato": "potato", "spinach": "spinach", "carrot": "carrot", "turnip_rape": "turnip rape"}
STATUS_WORD = {"ok": "on track", "watch": "watch", "risk": "bad year"}
RANK = {"ok": 0, "watch": 1, "risk": 2}

_lock = threading.Lock()


# ── weather blocks ──────────────────────────────────────────────────
@dataclass(frozen=True)
class Block:
    keys: pd.DataFrame  # cell_id, year (one row per cell-year)
    arr: dict[str, np.ndarray]  # c_features.season_arrays: rows × days (day 0 = 1 April)
    aet: dict[str, np.ndarray]  # soil → daily actual ET, rows × days


def _block(con: duckdb.DuckDBPyConnection, path: str, y0: int, y1: int) -> Block:
    src = (f"(SELECT * FROM raw_weather_daily WHERE scenario = '{path}' "
           f"AND year(date) BETWEEN {int(y0)} AND {int(y1)})")
    keys, arr, _ = F.season_arrays(con, src)
    aet = {soil: F.soil_water(arr["precip_mm"], arr["pet_mm"], cap) for soil, cap in F.BUCKET_MM.items()}
    return Block(keys[["cell_id", "year"]].reset_index(drop=True), arr, aet)


@dataclass(frozen=True)
class Series:
    """One row per (cell, soil, year): stage day indices and cumulative signals within [sow, maturity)."""
    keys: pd.DataFrame  # cell_id, soil, year
    sow: np.ndarray
    sens: np.ndarray
    fill: np.ndarray
    mat: np.ndarray  # n_days when never reached
    cpet: np.ndarray  # rows × days
    caet: np.ndarray
    chot: np.ndarray

    def dryness(self, d: int) -> np.ndarray:
        p, a = self.cpet[:, d], self.caet[:, d]
        return np.where(p > 0, 1.0 - a / np.where(p > 0, p, 1.0), 0.0)

    def hot(self, d: int) -> np.ndarray:
        return self.chot[:, d]


def stage_days(t: np.ndarray, crop: F.Crop) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """sow, sens, fill, mature day indices per row: the rule in c_features.crop_features."""
    nd = t.shape[1]
    days = np.arange(nd)[None, :]
    t5 = pd.DataFrame(t.T).rolling(5, min_periods=5).mean().to_numpy().T
    sow = F.first_true(t5 >= crop.sow_t)
    gdd = np.cumsum(np.where(days >= sow[:, None], np.maximum(t - F.GDD_BASE, 0.0), 0.0), axis=1)
    sens, fill, mat = (F.first_true(gdd >= g) for g in (crop.sens, crop.fill, crop.mature))
    return sow, sens, fill, mat


def _series(block: Block, pairs: pd.DataFrame, crop: str) -> Series:
    """Series for (cell_id, soil) pairs × every year in the block."""
    rows = block.keys.reset_index().rename(columns={"index": "row"}).merge(pairs, on="cell_id")
    r = rows["row"].to_numpy()
    t, tx, pet = block.arr["tmean_c"][r], block.arr["tmax_c"][r], block.arr["pet_mm"][r]
    aet = np.empty_like(pet)
    for soil in rows["soil"].unique():
        m = (rows["soil"] == soil).to_numpy()
        aet[m] = block.aet[soil][r[m]]
    sow, sens, fill, mat = stage_days(t, F.CROPS[crop])
    days = np.arange(t.shape[1])[None, :]
    season = (days >= sow[:, None]) & (days < mat[:, None])
    flower_on = (days >= sens[:, None]) & (days < mat[:, None])
    return Series(rows[["cell_id", "soil", "year"]].reset_index(drop=True), sow, sens, fill, mat,
                  np.cumsum(pet * season, axis=1), np.cumsum(aet * season, axis=1),
                  np.cumsum((tx >= F.HOT_C) & flower_on, axis=1).astype(float))


# ── cached inputs ───────────────────────────────────────────────────
class Inputs:
    """Everything one (path, year) needs, loaded once per process."""

    def __init__(self, con: duckdb.DuckDBPyConnection, path: str, year: int):
        self.path, self.year = path, year
        self.normal = _normal_block(con)
        self.now = _block(con, path, year, year)
        grid = con.execute("SELECT cell_id, region FROM raw_climate_grid_cells").df()
        self.cell_soil = dominant_soil(con).merge(grid, on="cell_id")  # cell_id, soil, region
        self.farms = _farm_cells(con)  # crop, farm_id, region, cell_id, soil, fields
        self._series: dict[tuple[str, str, str], tuple[Series, Series]] = {}

    def series(self, crop: str, level: str) -> tuple[Series, Series]:
        """(normal, now) Series for the region cells ('cells') or the farms' cell × soil pairs ('farms')."""
        key = (crop, level, "")
        if key not in self._series:
            if level == "cells":
                pairs = self.cell_soil[["cell_id", "soil"]]
            else:
                pairs = self.farms[self.farms.crop == crop][["cell_id", "soil"]].drop_duplicates()
            self._series[key] = (_series(self.normal, pairs, crop), _series(self.now, pairs, crop))
        return self._series[key]


_normal_cache: list[Block] = []


def _normal_block(con: duckdb.DuckDBPyConnection) -> Block:
    if not _normal_cache:
        _normal_cache.append(_block(con, "historical", *NORMAL))
    return _normal_cache[0]


def _farm_cells(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Farms growing each contract crop in CROP_YEAR, on the grid cell and soil most of those fields sit on."""
    crops = sorted({c for cs in REGION_CROPS.values() for c in cs})
    marks = ", ".join("?" * len(crops))
    return con.execute(f"""
        WITH f AS (
            SELECT h.crop, h.farm_id, g.region, g.cell_id, coalesce(p.soil_class_soilmap, 'clay') AS soil
            FROM raw_parcel_crop_history_and_plan h
            JOIN c_parcel_cell g USING (parcel_id) JOIN raw_parcels p USING (parcel_id)
            WHERE h.year = ? AND h.crop IN ({marks})),
        cn AS (SELECT crop, farm_id, region, cell_id, count(*) AS k FROM f GROUP BY crop, farm_id, region, cell_id),
        c AS (SELECT *, row_number() OVER (PARTITION BY crop, farm_id ORDER BY k DESC, cell_id) AS r FROM cn),
        sn AS (SELECT crop, farm_id, soil, count(*) AS k FROM f GROUP BY crop, farm_id, soil),
        s AS (SELECT *, row_number() OVER (PARTITION BY crop, farm_id ORDER BY k DESC, soil) AS r FROM sn),
        n AS (SELECT crop, farm_id, count(*) AS fields FROM f GROUP BY ALL)
        SELECT c.crop, c.farm_id, c.region, c.cell_id,
               CASE WHEN s.soil IN ('sand','fine_sand','silt','clay','organic') THEN s.soil ELSE 'clay' END AS soil,
               n.fields
        FROM c JOIN s USING (crop, farm_id) JOIN n USING (crop, farm_id)
        WHERE c.r = 1 AND s.r = 1 ORDER BY c.crop, c.farm_id""", [CROP_YEAR, *crops]).df()


@lru_cache(maxsize=8)
def _inputs_cached(path: str, year: int) -> Inputs:
    from src import serve_db
    with serve_db.connect() as con:
        return Inputs(con, path, year)


def inputs(path: str, year: int, con: duckdb.DuckDBPyConnection | None = None) -> Inputs:
    with _lock:
        if con is None:
            return _inputs_cached(path, year)
        return Inputs(con, path, year)


# ── statistics ──────────────────────────────────────────────────────
def percentile(value: float, normal: np.ndarray) -> float:
    """Mid-rank percentile of `value` among `normal` (ties count half), 0–100."""
    n = np.asarray(normal, dtype=float)
    if not len(n):
        return 50.0
    return float(100.0 * ((n < value).sum() + 0.5 * (n == value).sum()) / len(n))


def status_of(dry_pct: float, heat_pct: float, flowering: bool) -> str:
    p = max(dry_pct, heat_pct)
    if flowering and p >= RISK_PCT:
        return "risk"
    if p >= (WATCH_PCT if flowering else RISK_PCT):
        return "watch"
    return "ok"


def path_of(year: int, climate: str) -> str:
    return "historical" if year <= LAST_OBSERVED else climate


def day_index(d: date) -> int:
    return (d - date(d.year, *SEASON_START)).days


def season_days(year: int) -> tuple[date, date]:
    return date(year, *SEASON_START), date(year, 10, 31)


def _dates(year: int, idx: float) -> str:
    return (date(year, *SEASON_START) + timedelta(days=int(idx))).isoformat()


# ── one region × crop on one day ────────────────────────────────────
def _region_rows(inp: Inputs, s: Series, region: str) -> np.ndarray:
    cells = set(inp.cell_soil.loc[inp.cell_soil.region == region, "cell_id"])
    return s.keys["cell_id"].isin(cells).to_numpy()


def region_day(inp: Inputs, region: str, crop: str, d: int) -> dict:
    """Stage, signals, percentiles and status of one region × crop on day index d."""
    normal, now = inp.series(crop, "cells")
    rn, rt = _region_rows(inp, normal, region), _region_rows(inp, now, region)
    nd = now.cpet.shape[1]
    d = int(np.clip(d, 0, nd - 1))

    # stage: a stage is reached when most of the region's cells reached it by day d
    stage_idx = {"sown": now.sow[rt], "flowering": now.sens[rt], "fill": now.fill[rt], "harvest": now.mat[rt]}
    normal_idx = {"sown": normal.sow[rn], "flowering": normal.sens[rn], "fill": normal.fill[rn],
                  "harvest": normal.mat[rn]}
    stages, current = [], "not_sown"
    for name in STAGES:
        idx = stage_idx[name]
        if (idx <= d).mean() > 0.5:
            stages.append({"name": name, "date": _dates(inp.year, float(np.median(idx[idx <= d]))), "expected": False})
            current = name
        else:
            exp = np.median(np.minimum(normal_idx[name], nd))
            stages.append({"name": name, "date": _dates(inp.year, max(float(exp), d + 1)), "expected": True})
    flowering = current in ("flowering", "fill", "harvest")

    # signals: region mean over cells, today vs the same day in each normal year
    dry_now = float(now.dryness(d)[rt].mean())
    hot_now = float(np.round(now.hot(d)[rt].mean()))  # whole days: a fraction of a hot day is not a signal
    yrs = normal.keys.loc[rn, "year"].to_numpy()
    dry_norm = pd.Series(normal.dryness(d)[rn]).groupby(yrs).mean().to_numpy()
    hot_norm = np.round(pd.Series(normal.hot(d)[rn]).groupby(yrs).mean().to_numpy())
    dry_pct, heat_pct = percentile(dry_now, dry_norm), percentile(hot_now, hot_norm)
    return {
        "region": region, "crop": crop, "stage": current, "stages": stages,
        "status": status_of(dry_pct, heat_pct, flowering),
        "dryness": round(dry_now, 3), "dryness_pct": round(dry_pct), "dryness_normal": [round(float(x), 3) for x in dry_norm],
        "hot_days": round(hot_now, 1), "heat_pct": round(heat_pct), "hot_normal": [round(float(x), 1) for x in hot_norm],
        "hot_days_p50": round(float(np.median(hot_norm)), 1),
    }


def farm_spread(inp: Inputs, region: str, crop: str, d: int) -> dict | None:
    """Each farm's dryness so far as a percentile of its own cell × soil normal; spread across the region's farms."""
    farms = inp.farms[(inp.farms.crop == crop) & (inp.farms.region == region)]
    if farms.empty:
        return None
    normal, now = inp.series(crop, "farms")
    d = int(np.clip(d, 0, now.cpet.shape[1] - 1))
    nk = normal.keys.assign(v=normal.dryness(d))
    tk = now.keys.assign(v=now.dryness(d))
    norms = {k: g["v"].to_numpy() for k, g in nk.groupby(["cell_id", "soil"])}
    today_v = {(r.cell_id, r.soil): r.v for r in tk.itertuples(index=False)}
    pct = np.array([percentile(today_v[(f.cell_id, f.soil)], norms[(f.cell_id, f.soil)])
                    for f in farms.itertuples(index=False)])
    return {"region": region, "crop": crop, "farms": int(len(pct)), "fields": int(farms.fields.sum()),
            "p10": round(float(np.percentile(pct, 10))), "p50": round(float(np.median(pct))),
            "p90": round(float(np.percentile(pct, 90))),
            "share_ge_90": round(float((pct >= RISK_PCT).mean()), 3),
            "share_ge_75": round(float((pct >= WATCH_PCT).mean()), 3)}


# ── what changed ────────────────────────────────────────────────────
def _label(region: str, crop: str) -> str:
    return f"{REGION_NAME.get(region, region)} {CROP_NAME.get(crop, crop)}"


def changes(prev: list[dict], cur: list[dict]) -> list[dict]:
    """Differences between yesterday's and today's region × crop rows (same order), most serious first."""
    out = []
    before = {(r["region"], r["crop"]): r for r in prev}
    for r in cur:
        p = before.get((r["region"], r["crop"]))
        if p is None:
            continue
        who = _label(r["region"], r["crop"])
        if r["status"] != p["status"]:
            up = RANK[r["status"]] > RANK[p["status"]]
            out.append({"region": r["region"], "crop": r["crop"], "kind": "escalated" if up else "eased",
                        "from_status": p["status"], "to_status": r["status"],
                        "text": f"{who}: {STATUS_WORD[p['status']]} → {STATUS_WORD[r['status']]}"})
        if r["stage"] != p["stage"]:
            out.append({"region": r["region"], "crop": r["crop"], "kind": "stage", "from_status": p["status"],
                        "to_status": r["status"], "text": f"{who}: now {STAGE_WORD[r['stage']]}"})
        for key, word in (("dryness_pct", "dryness"), ("heat_pct", "heat")):
            if abs(r[key] - p[key]) >= JUMP_PTS:
                out.append({"region": r["region"], "crop": r["crop"], "kind": "jump", "from_status": p["status"],
                            "to_status": r["status"],
                            "text": f"{who}: {word} {_ordinal(p[key])} → {_ordinal(r[key])} percentile"})
    order = {"escalated": 0, "eased": 1, "jump": 2, "stage": 3}
    return sorted(out, key=lambda c: (order[c["kind"]], -RANK[c["to_status"]]))


def _ordinal(n: float) -> str:
    n = int(round(n))
    suf = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suf}"


# ── the day ─────────────────────────────────────────────────────────
def pairs() -> list[tuple[str, str]]:
    return [(r, c) for r, cs in REGION_CROPS.items() for c in cs]


def today(day: str | date, climate: str = "ssp245", crop: str = "pea",
          con: duckdb.DuckDBPyConnection | None = None) -> dict:
    """Everything the four widgets show for one day. `crop` picks the crop for widgets ①, ③ and ④."""
    d0 = date.fromisoformat(day) if isinstance(day, str) else day
    first, last = season_days(d0.year)
    if not (YEARS[0] <= d0.year <= YEARS[1]) or not (first <= d0 <= last):
        raise ValueError(f"date must be 1 Apr–31 Oct of {YEARS[0]}–{YEARS[1]}, got {d0.isoformat()}")
    if crop not in F.CROPS:
        raise ValueError(f"unknown crop {crop!r}")
    path = path_of(d0.year, climate)
    inp = inputs(path, d0.year, con)
    d = day_index(d0)
    cur = [region_day(inp, r, c, d) for r, c in pairs()]
    prev = [region_day(inp, r, c, d - 1) for r, c in pairs()] if d > 0 else []
    focus = [r for r in cur if r["crop"] == crop]
    counts = {s: sum(r["status"] == s for r in cur) for s in ("ok", "watch", "risk")}
    return {
        "date": d0.isoformat(), "climate": climate, "path": path, "crop": crop,
        "season": [first.isoformat(), last.isoformat()],
        "regions": focus, "all": cur, "counts": counts, "changes": changes(prev, cur),
        "farms": [f for f in (farm_spread(inp, r["region"], crop, d) for r in focus) if f],
        "normal_years": list(NORMAL), "synthetic": True,
    }


def default_date(crop: str = "pea", year: int = LAST_OBSERVED) -> str:
    """The demo clock's start: the first 2026 day a region's crop reaches 'bad year', else its flowering start."""
    inp = inputs(path_of(year, "ssp245"), year)
    nd = inp.now.arr["tmean_c"].shape[1]
    for d in range(nd):
        for region in REGION_CROPS:
            if crop in REGION_CROPS[region] and region_day(inp, region, crop, d)["status"] == "risk":
                return _dates(year, d)
    r = region_day(inp, "SE_SKANE", crop, nd - 1)
    return next(s["date"] for s in r["stages"] if s["name"] == "flowering")


def main() -> None:
    day = sys.argv[1] if len(sys.argv) > 1 else default_date()
    climate = sys.argv[2] if len(sys.argv) > 2 else "ssp245"
    crop = sys.argv[3] if len(sys.argv) > 3 else "pea"
    t = today(day, climate, crop)
    print(f"{t['date']} · {t['path']} · {crop}  counts {t['counts']}")
    for r in t["regions"]:
        print(f"  {r['region']:9} {r['stage']:9} {r['status']:5} dryness {r['dryness']:.2f} ({r['dryness_pct']}th)"
              f"  hot {r['hot_days']} ({r['heat_pct']}th)")
    for c in t["changes"]:
        print(f"  change: {c['text']}")
    for f in t["farms"]:
        print(f"  farms {f['region']}: n={f['farms']} p10/50/90 {f['p10']}/{f['p50']}/{f['p90']}  ≥90th {f['share_ge_90']:.0%}")


if __name__ == "__main__":
    main()
