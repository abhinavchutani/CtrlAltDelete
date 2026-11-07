"""Navigator v2 API (docs/V2_ARCHITECTURE.md, "Endpoints").

    API_MOCK=1 make api     # every endpoint from api/fixtures (no data needed)
    make api                # real layers where built (src/p_*); retrieval stays on fixtures (on hold)

Routes only validate and dispatch; the numbers come from the layers (api/layers.py).
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from api import geo
from api import layers as L
from api import prediction as P
from api import schemas as S
from src import serve_db
from src.db import env

@asynccontextmanager
async def lifespan(_: FastAPI):
    if not L.mock_mode() and env("API_WARM", "1") != "0":
        P.warm_in_background()  # fits the v1 models once; /api/health shows warming meanwhile
    yield


app = FastAPI(title="Navigator v2", version="0.1.0", lifespan=lifespan,
              description="Synthetic data: not Apetit's real figures. Contract: api/schemas.py.")
app.add_middleware(GZipMiddleware, minimum_size=2048)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_methods=["*"], allow_headers=["*"])


def _found(x, what: str):
    if x is None:
        raise HTTPException(404, f"{what} not found")
    return x


# ── platform ───────────────────────────────────────────────────────
@app.get("/api/health", response_model=S.Health)
def health() -> S.Health:
    llm = any(env(k) for k in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY"))
    return S.Health(ok=True, mock=L.mock_mode(), serve_db=str(serve_db.serve_path()) if serve_db.exists() else None,
                    llm=llm, warming=P.warming(), layers={**L.available(), **L.live()})


@app.get("/api/geo/farms")
def geo_farms() -> dict:
    return L.mock.geo_farms() if L.mock_mode() else geo.farms()


@app.get("/api/geo/parcels")
def geo_parcels() -> dict:
    return L.mock.geo_parcels() if L.mock_mode() else geo.parcels()


# ── intent ─────────────────────────────────────────────────────────
@app.post("/api/intent", response_model=S.IntentOut)
def intent(body: S.IntentIn) -> S.IntentOut:
    return L.get("intent")(body.text)


# ── prediction ─────────────────────────────────────────────────────
@app.get("/api/scenarios", response_model=list[S.ScenarioPreset])
def scenarios() -> list[S.ScenarioPreset]:
    return L.get("scenarios")()


@app.get("/api/scenario/{scenario_id}", response_model=S.SimResult)
def scenario(scenario_id: str) -> S.SimResult:
    return _found(L.get("scenario")(scenario_id), f"scenario {scenario_id}")


@app.post("/api/simulate", response_model=S.SimResult)
def simulate(spec: S.ScenarioSpec) -> S.SimResult:
    return L.get("simulate")(spec)


@app.get("/api/cube/{scenario_id}/farms", response_model=list[S.FarmYear])
def farms(scenario_id: str, year: int | None = None) -> list[S.FarmYear]:
    return L.get("farms")(scenario_id, year)


@app.get("/api/weather", response_model=S.WeatherFrame)
def weather(climate: str = Query("ssp245"), year: int = Query(2026)) -> S.WeatherFrame:
    if climate not in ("historical", "ssp126", "ssp245", "ssp585"):
        raise HTTPException(422, f"unknown climate {climate}")
    return L.get("weather")(climate, year)


@app.get("/api/hedge", response_model=S.Hedge)
def hedge(climate: S.Climate = "ssp245") -> S.Hedge:
    return L.get("hedge")(climate)


@app.get("/api/pathways/{scenario_id}", response_model=list[S.PathwayItem])
def pathways(scenario_id: str) -> list[S.PathwayItem]:
    return L.get("pathways")(scenario_id)


# ── retrieval (fixtures while on hold) ─────────────────────────────
@app.post("/api/ask", response_model=S.AskOut)
def ask(body: S.AskIn) -> S.AskOut:
    return L.get("ask")(body.question, body.history)


@app.get("/api/report/{report_id}")
def report(report_id: str):
    raise HTTPException(501, "reports come from the retrieval layer (src.r_report), which is on hold")


@app.get("/api/options", response_model=list[S.AdaptationOption])
def options(hazard: S.Hazard | None = None, crop: str | None = None) -> list[S.AdaptationOption]:
    return L.get("options")(hazard, crop)


@app.get("/api/board/{scenario_id}", response_model=list[S.BoardRow])
def board(scenario_id: str) -> list[S.BoardRow]:
    return L.get("board")(scenario_id)


@app.post("/api/board/{row_id}/decision", response_model=S.BoardRow)
def decide(row_id: str, d: S.Decision) -> S.BoardRow:
    return _found(L.get("decide")(row_id, d), f"board row {row_id}")
