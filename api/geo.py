"""GeoJSON for the map in real mode (task #95): farm points from serve.duckdb, parcel polygons from the pack.

Parcels are simplified for the browser: only parcel_id, farm_id and area_ha are kept, coordinates rounded to
5 decimals (~1 m), cached at out/v2/geo_parcels.json; the API gzips the response (GZipMiddleware).
Each parcel also carries `crop`: the crop declared for 2025, the parcel mix every prediction holds (C2 rule).
It is joined at read time from the snapshot, so the geometry cache never goes stale.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from fastapi import HTTPException

from src import serve_db
from src.db import REPO_ROOT, env

CACHE = REPO_ROOT / "out" / "v2" / "geo_parcels.json"
KEEP = ("parcel_id", "farm_id", "area_ha")
CROP_YEAR = 2025


def _round(coords):
    if isinstance(coords[0], (int, float)):
        return [round(coords[0], 5), round(coords[1], 5)]
    return [_round(c) for c in coords]


def simplify(geo: dict) -> dict:
    return {"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": {"type": f["geometry"]["type"], "coordinates": _round(f["geometry"]["coordinates"])},
         "properties": {k: f["properties"].get(k) for k in KEEP}} for f in geo["features"]]}


def pack_parcels_path() -> Path:
    d = Path(env("DATA_DIR", "data/APETIT_CLIMATE_NATURE_NAVIGATOR_2026")).expanduser()
    d = d if d.is_absolute() else REPO_ROOT / d
    return d / "data" / "06_nature" / "parcels.geojson"


def parcel_crops() -> dict[str, str]:
    """parcel_id → crop declared for CROP_YEAR. Empty without the snapshot (the map still draws, uncoloured by crop)."""
    if not serve_db.exists():
        return {}
    with serve_db.connect() as con:
        rows = con.execute("SELECT parcel_id, crop FROM raw_parcel_crop_history_and_plan WHERE year = ?",
                           [CROP_YEAR]).fetchall()
    return dict(rows)


def with_crops(geo: dict, crops: dict[str, str]) -> dict:
    for f in geo["features"]:
        f["properties"]["crop"] = crops.get(f["properties"]["parcel_id"])
    return geo


def _geometry() -> dict:
    if CACHE.exists():
        return json.loads(CACHE.read_text())
    src = pack_parcels_path()
    if not src.exists():
        raise HTTPException(503, f"parcels.geojson not found under DATA_DIR ({src})")
    out = simplify(json.loads(src.read_text()))
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(out, separators=(",", ":")))
    return out


@lru_cache(maxsize=1)
def parcels() -> dict:
    return with_crops(_geometry(), parcel_crops())


@lru_cache(maxsize=1)
def farms() -> dict:
    if not serve_db.exists():
        raise HTTPException(503, "out/serve.duckdb missing: run `make snapshot`")
    with serve_db.connect() as con:
        rows = con.execute("SELECT farm_id, region, lat, lon FROM clean_farm_registry ORDER BY farm_id").fetchall()
    return {"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [round(lon, 5), round(lat, 5)]},
         "properties": {"farm_id": f, "region": r}} for f, r, lat, lon in rows]}
