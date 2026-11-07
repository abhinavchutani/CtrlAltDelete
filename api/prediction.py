"""API_MOCK=0 backend for the prediction endpoints: adapts lane C's src/p_* to the api.mock signatures (task #95).

* Presets, their cubes and the weather frames are precomputed by `make v2` into out/v2/ and read from disk
  (fast, no model needed). A missing file → None (404) or an HTTPException 503 saying "run make v2".
* `simulate` needs the fitted v1 models: `warm()` loads `p_engine.load_context()` once, in a background thread
  started by the API lifespan; until it finishes /api/health says `warming: true` and simulate answers 503.
* Custom runs keep their farm cube in memory (keyed by scenario_id) for /api/cube/{id}/farms.
Endpoints whose module is not built yet (hedge, pathways, intent: #90/#91) are left to api/layers.py, which
answers 503 for them; nothing here falls back to fixtures, so real mode never shows mock numbers.
"""
from __future__ import annotations

import json
import threading
from functools import lru_cache
import time
from pathlib import Path

import pandas as pd
from fastapi import HTTPException

from api import schemas as S
from src.db import REPO_ROOT

V2 = REPO_ROOT / "out" / "v2"
_state: dict = {"ctx": None, "warming": False, "error": None, "seconds": None}
_custom_farms: dict[str, pd.DataFrame] = {}
_lock = threading.Lock()


# ── context (lifespan) ─────────────────────────────────────────────
def warm() -> None:
    """Load the prediction context (fits v1 models, ~10–60 s). Safe to call twice."""
    with _lock:
        if _state["ctx"] is not None or _state["warming"]:
            return
        _state["warming"] = True
    t = time.time()
    try:
        from src import p_engine

        _state["ctx"] = p_engine.load_context()
        _state["seconds"] = round(time.time() - t, 1)
    except Exception as e:  # noqa: BLE001 - surfaced through /api/health and simulate's 503
        _state["error"] = f"{e.__class__.__name__}: {e}"
    finally:
        _state["warming"] = False


def warm_in_background() -> threading.Thread:
    th = threading.Thread(target=warm, name="p_engine-warm", daemon=True)
    th.start()
    return th


def warming() -> bool:
    return bool(_state["warming"])


def context_error() -> str | None:
    return _state["error"]


def _need(path: Path, what: str) -> Path:
    if not path.exists():
        raise HTTPException(503, f"{what} missing ({path.relative_to(REPO_ROOT)}): run `make v2`")
    return path


# ── presets ────────────────────────────────────────────────────────
def scenarios() -> list[S.ScenarioPreset]:
    idx = json.loads(_need(V2 / "scenarios" / "index.json", "preset index").read_text())
    return [S.ScenarioPreset(**p) for p in idx]


def scenario(scenario_id: str) -> S.SimResult | None:
    if "/" in scenario_id or ".." in scenario_id:
        return None
    from src import p_presets

    _need(V2 / "scenarios", "presets")
    try:
        return S.SimResult(**p_presets.get_scenario(scenario_id, out=V2))
    except FileNotFoundError:
        return None


def simulate(spec: S.ScenarioSpec) -> S.SimResult:
    ctx = _state["ctx"]
    if ctx is None:
        why = _state["error"] or ("the model is warming up, try again in a few seconds" if warming() else "not loaded")
        raise HTTPException(503, f"simulate unavailable: {why}")
    from src import p_engine

    sim, cube = p_engine.simulate(ctx, spec.model_dump(mode="json"))
    _custom_farms[sim["scenario_id"]] = cube["farms"]
    return S.SimResult(**sim)


def _farm_rows(df: pd.DataFrame, year: int | None) -> list[S.FarmYear]:
    if year is not None:
        df = df[df.year == year]
    return [S.FarmYear(farm_id=r.farm_id, year=int(r.year), change_vs_baseline_pct=float(round(r.change_pct)), risk=r.risk)
            for r in df.itertuples(index=False)]


@lru_cache(maxsize=16)
def _preset_farms(path: Path, mtime: float) -> pd.DataFrame:
    return pd.read_parquet(path)


def farms(scenario_id: str, year: int | None = None) -> list[S.FarmYear]:
    if scenario_id in _custom_farms:
        return _farm_rows(_custom_farms[scenario_id], year)
    if "/" in scenario_id or ".." in scenario_id:
        raise HTTPException(404, "unknown scenario")
    p = V2 / "cube" / f"{scenario_id}_farms.parquet"
    if not p.exists():
        raise HTTPException(404, f"no farm cube for {scenario_id} (presets: run `make v2`; custom runs live in memory)")
    return _farm_rows(_preset_farms(p, p.stat().st_mtime), year)


# ── weather ────────────────────────────────────────────────────────
def weather(climate: str, year: int) -> S.WeatherFrame:
    from src import p_weather

    _need(V2 / "weather", "weather frames")
    if year <= 2026:
        climate = "historical"  # the SSP paths start in 2027; before that the frame is observed weather
    try:
        return S.WeatherFrame(**p_weather.get_frame(climate, year, out_dir=V2 / "weather"))
    except FileNotFoundError:
        raise HTTPException(404, f"no weather frame for {climate} {year}") from None
