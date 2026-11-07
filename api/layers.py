"""Which function answers each endpoint: the fixtures (API_MOCK=1) or the real layer (API_MOCK=0).

Real mode (task #95):
    scenarios / scenario / simulate / farms / weather → api.prediction (adapts src.p_presets, p_engine, p_weather;
                                                         presets and frames precomputed by `make v2`)
    hedge    → src.p_hedge.hedge(climate) -> Hedge                     (lane C, #91; 503 until built)
    pathways → src.p_pathways.pathways(scenario_id) -> list[PathwayItem] (lane C, #91)
    intent   → src.p_parse.parse(text) -> IntentOut                     (lane C, #90)
Each real function takes the same arguments as its api.mock twin and returns the api.schemas model (or a
dict that validates). Real mode never falls back to fixtures for prediction: an unbuilt module is a 503.

Retrieval (ask / options / board / decide) stays on the fixtures whatever API_MOCK says until a human
confirms in the chat that it is back (RETRIEVAL_LIVE below).
"""
from __future__ import annotations

import importlib
from collections.abc import Callable

from fastapi import HTTPException

from api import mock
from src.db import env

REAL: dict[str, tuple[str, str]] = {
    "scenarios": ("api.prediction", "scenarios"),
    "scenario": ("api.prediction", "scenario"),
    "simulate": ("api.prediction", "simulate"),
    "farms": ("api.prediction", "farms"),
    "weather": ("api.prediction", "weather"),
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
    for mod in sorted({m for m, _ in REAL.values()} | {"src.p_engine", "src.p_presets", "src.p_weather"}):
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
