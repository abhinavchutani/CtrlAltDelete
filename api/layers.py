"""Which function answers each endpoint: the fixtures (API_MOCK=1) or the real layer (API_MOCK=0).

This table IS the interface the Prediction lane implements. Each real function takes the same
arguments as its api.mock twin and returns the api.schemas model (or a dict that validates):

    src.p_presets.list_presets() -> list[ScenarioPreset]
    src.p_presets.load(scenario_id) -> SimResult | None
    src.p_engine.simulate(spec: ScenarioSpec) -> SimResult
    src.p_cube.farms(scenario_id, year: int | None) -> list[FarmYear]
    src.p_weather.frame(climate, year) -> WeatherFrame
    src.p_hedge.hedge(climate) -> Hedge
    src.p_pathways.pathways(scenario_id) -> list[PathwayItem]
    src.p_parse.parse(text) -> IntentOut

Retrieval is ON HOLD (humans, 7 Nov): ask / options / board / decide / report always use the
fixtures, whatever API_MOCK says, until a human re-enables them (RETRIEVAL_LIVE below).
"""
from __future__ import annotations

import importlib
from collections.abc import Callable

from fastapi import HTTPException

from api import mock
from src.db import env

REAL: dict[str, tuple[str, str]] = {
    "scenarios": ("src.p_presets", "list_presets"),
    "scenario": ("src.p_presets", "load"),
    "simulate": ("src.p_engine", "simulate"),
    "farms": ("src.p_cube", "farms"),
    "weather": ("src.p_weather", "frame"),
    "hedge": ("src.p_hedge", "hedge"),
    "pathways": ("src.p_pathways", "pathways"),
    "intent": ("src.p_parse", "parse"),
    # retrieval (lane A), served from fixtures while on hold
    "ask": ("src.r_agent", "ask"),
    "options": ("src.r_options", "options"),
    "board": ("src.r_board", "board"),
    "decide": ("src.r_board", "decide"),
}
RETRIEVAL = {"ask", "options", "board", "decide"}
RETRIEVAL_LIVE = False  # flip only when a human says retrieval is back


def mock_mode() -> bool:
    return env("API_MOCK", "0").strip().lower() in ("1", "true", "yes")


def uses_mock(name: str) -> bool:
    return mock_mode() or (name in RETRIEVAL and not RETRIEVAL_LIVE)


def available() -> dict[str, bool]:
    """Which real modules import (shown in /api/health so everyone sees what's wired)."""
    out = {}
    for mod in sorted({m for m, _ in REAL.values()}):
        try:
            importlib.import_module(mod)
            out[mod] = True
        except ImportError:
            out[mod] = False
    return out


def get(name: str) -> Callable:
    if uses_mock(name):
        return getattr(mock, name)
    mod, fn = REAL[name]
    try:
        return getattr(importlib.import_module(mod), fn)
    except (ImportError, AttributeError) as e:
        raise HTTPException(503, f"{mod}.{fn} is not built yet ({e.__class__.__name__}); "
                                 "run with API_MOCK=1 for fixtures") from e
