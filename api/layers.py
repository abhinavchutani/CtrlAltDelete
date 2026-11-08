"""Which function answers each endpoint: the fixtures (API_MOCK=1) or the real layer (API_MOCK=0).

Real mode (task #95):
    scenarios / scenario / simulate / farms / weather → api.prediction (adapts src.p_presets, p_engine, p_weather;
                                                         presets and frames precomputed by `make v2`)
    hedge / pathways → api.prediction (src.p_hedge.hedge, src.p_pathways.pathways; 503 while the model warms)
    intent   → src.p_parse.parse(text, base) -> IntentOut               (lane C, #90)
Each real function takes the same arguments as its api.mock twin and returns the api.schemas model (or a
dict that validates). Real mode never falls back to fixtures for prediction: an unbuilt module is a 503.

Retrieval is back (human, 7 Nov 13:10): ask / options / board / decide use src.r_* in real mode as soon as
their module imports; an unbuilt one (r_options #87, r_board #94) keeps serving its fixture, and /api/health
reports which ones are live (`live:<name>`) so the UI labels fixture rows.
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
    "hedge": ("api.prediction", "hedge"),
    "pathways": ("api.prediction", "pathways"),
    "intent": ("src.p_parse", "parse"),
    "sbti_pathway": ("src.b_sbti", "serve"),  # #130: deterministic, reads serve.duckdb + the pack
    # retrieval (lane A), served from fixtures while on hold
    "ask": ("src.r_agent", "ask"),
    "options": ("src.r_options", "options"),
    "board": ("src.r_board", "board"),
    "decide": ("src.r_board", "decide"),
}
RETRIEVAL = {"ask", "options", "board", "decide"}
RETRIEVAL_LIVE = True  # retrieval back on (human, 7 Nov); set False to force fixtures


def mock_mode() -> bool:
    return env("API_MOCK", "0").strip().lower() in ("1", "true", "yes")


def _imports(mod: str) -> bool:
    try:
        importlib.import_module(mod)
        return True
    except ImportError:
        return False


def uses_mock(name: str) -> bool:
    if mock_mode():
        return True
    return name in RETRIEVAL and not (RETRIEVAL_LIVE and _imports(REAL[name][0]))


def live() -> dict[str, bool]:
    """Per retrieval endpoint: True when real mode answers it from src.r_* (else its fixture)."""
    return {f"live:{n}": not uses_mock(n) for n in sorted(RETRIEVAL)}


def available() -> dict[str, bool]:
    """Which real modules import (shown in /api/health so everyone sees what's wired)."""
    return {m: _imports(m) for m in sorted({m for m, _ in REAL.values()} | {"src.p_engine", "src.p_presets", "src.p_weather", "src.p_hedge", "src.p_pathways"})}


def get(name: str) -> Callable:
    if uses_mock(name):
        return getattr(mock, name)
    mod, fn = REAL[name]
    try:
        return getattr(importlib.import_module(mod), fn)
    except (ImportError, AttributeError) as e:
        raise HTTPException(503, f"{mod}.{fn} is not built yet ({e.__class__.__name__}); "
                                 "run with API_MOCK=1 for fixtures") from e
