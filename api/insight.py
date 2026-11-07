"""UI v3 endpoints: what the model is built on, month-by-month weather, and the plan finder (streamed).

* provenance(): counts straight from the snapshot + the C1 backtest score file. Nothing typed by hand.
* months():     src.p_season over the snapshot.
* search_events(): src.p_search on the warm engine, as Server-Sent Events (text/event-stream is not gzipped, so
  each simulated plan reaches the browser as soon as it is done). One shared run per (climate, horizon).
"""
from __future__ import annotations

import json
import threading
import time
from collections.abc import Iterator

from fastapi import HTTPException

from api import prediction as P
from src import serve_db
from src.db import REPO_ROOT

BACKTEST = REPO_ROOT / "out" / "scores" / "C1_backtest.json"
class _Run:
    """One search per (climate, horizon), computed in its own thread. Every request follows its events, live while it
    runs and replayed once done (deterministic). A failed run is dropped so the next request tries again."""

    def __init__(self) -> None:
        self.events: list[dict] = []
        self.done = False
        self.cv = threading.Condition()


_RUNS: dict[tuple[str, int], _Run] = {}
_RUNS_LOCK = threading.Lock()


def _con():
    if not serve_db.exists():
        raise HTTPException(503, "out/serve.duckdb missing: run `make snapshot`")
    return serve_db.connect()


def provenance() -> dict:
    with _con() as con:
        one = lambda sql: con.execute(sql).fetchone()  # noqa: E731
        farms, = one("SELECT count(DISTINCT farm_id) FROM raw_parcels")
        parcels, = one("SELECT count(*) FROM raw_parcels")
        h0, h1 = one("SELECT min(year), max(year) FROM raw_parcel_crop_history_and_plan WHERE status = 'declared'")
        fi_n, fi0, fi1 = one("SELECT count(*), min(year), max(year) FROM clean_farm_survey WHERE yield_t_ha IS NOT NULL")
        se_n, se0, se1 = one("SELECT count(*), min(skördeår), max(skördeår) FROM raw_foodhills_odlingsdata_se")
        cells, w0, w1 = one("SELECT count(DISTINCT cell_id), min(year(date)), max(year(date)) FROM raw_weather_daily "
                            "WHERE scenario = 'historical'")
        days, = one("SELECT count(*) FROM raw_weather_daily")
        c0, c1 = one("SELECT min(year(date)), max(year(date)) FROM raw_weather_daily WHERE scenario <> 'historical'")
        paths = [s for (s,) in con.execute("SELECT DISTINCT scenario FROM raw_weather_daily WHERE scenario <> 'historical' "
                                           "ORDER BY 1").fetchall()]
    backtest = None
    if BACKTEST.exists():
        b = json.loads(BACKTEST.read_text())
        backtest = {"train_until": int(str(b["train_years"]).lstrip("≤")), "test_years": b["test_years"],
                    "model_error_pct": round(b["production_mape_pct"]["model"], 1),
                    "baseline_error_pct": round(b["production_mape_pct"]["farm_mean_baseline"], 1)}
    return {"farms": farms, "parcels": parcels, "crop_history_years": [h0, h1],
            "fi_yield_records": fi_n, "fi_yield_years": [fi0, fi1],
            "se_delivery_records": se_n, "se_delivery_years": [se0, se1],
            "weather_cells": cells, "weather_years": [w0, w1], "weather_days": days,
            "climate_paths": paths, "climate_years": [c0, c1], "backtest": backtest, "synthetic": True}


def months(climate: str, year: int, region: str) -> dict:
    from src import p_season
    with _con() as con:
        return p_season.months(con, climate, year, region)


def _start(key: tuple[str, int]) -> _Run:
    from src import p_engine, p_search

    run, ctx = _Run(), P.context()

    def engine(spec: dict):
        with P.ENGINE_LOCK:  # one engine run at a time: the context's DuckDB connection is shared
            return p_engine.run_spec(ctx, spec)[0]

    def go() -> None:
        failed = False
        try:
            for ev in p_search.search(engine, *key):
                with run.cv:
                    run.events.append(ev)
                    run.cv.notify_all()
        except Exception as e:  # noqa: BLE001 - followers get an error event instead of a cut stream
            failed = True
            with run.cv:
                run.events.append({"type": "error", "detail": f"{e.__class__.__name__}: {e}"})
        finally:
            with run.cv:
                run.done = True
                run.cv.notify_all()
            if failed:
                with _RUNS_LOCK:
                    _RUNS.pop(key, None)

    threading.Thread(target=go, name=f"plan-finder-{key[0]}-{key[1]}", daemon=True).start()
    return run


def _run_for(climate: str, horizon_end: int) -> _Run:
    key = (climate, horizon_end)
    with _RUNS_LOCK:
        if key not in _RUNS:
            _RUNS[key] = _start(key)
        return _RUNS[key]


def _events(climate: str, horizon_end: int) -> Iterator[dict]:
    run, i = _run_for(climate, horizon_end), 0
    while True:
        with run.cv:
            while i >= len(run.events) and not run.done:
                run.cv.wait(timeout=30)
            batch, done = run.events[i:], run.done
        yield from batch
        i += len(batch)
        if done and i >= len(run.events):
            return


def search_events(climate: str, horizon_end: int) -> Iterator[str]:
    """SSE lines. Call P.ready() first (in the route) so a cold model is a 503, not a broken stream."""
    try:
        for ev in _events(climate, horizon_end):
            yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
    except Exception as e:  # noqa: BLE001 - the stream is already open; say what broke instead of cutting it
        yield f"data: {json.dumps({'type': 'error', 'detail': f'{e.__class__.__name__}: {e}'})}\n\n"


def prewarm_in_background(climate: str = "ssp245", horizon_end: int = 2040) -> threading.Thread:
    """After the engine warms: build the default plan + comparison grid (the first /api/simulate needs them, ~10 s),
    then start the default plan search, so the first clicks answer at once."""
    def go() -> None:
        while P.context() is None:
            if P.context_error():
                return
            time.sleep(2)
        from src import p_engine
        try:
            with P.ENGINE_LOCK:
                p_engine.plan_for(P.context(), climate, horizon_end)
                p_engine.grid_for(P.context(), climate, horizon_end)
        except Exception:  # noqa: BLE001 - a failed prewarm only means the first simulate builds them itself
            pass
        _run_for(climate, horizon_end)
    th = threading.Thread(target=go, name="plan-finder-prewarm", daemon=True)
    th.start()
    return th
