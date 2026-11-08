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
from fastapi.responses import FileResponse, StreamingResponse

from api import geo
from api import insight
from api import kgraph
from api import layers as L
from api import prediction as P
from api import radar
from api import schemas as S
from src import serve_db
from src.db import env

@asynccontextmanager
async def lifespan(_: FastAPI):
    if not L.mock_mode() and env("API_WARM", "1") != "0":
        P.warm_in_background()  # fits the v1 models once; /api/health shows warming meanwhile
        insight.prewarm_in_background()  # then runs the default plan search once (cached, replayed on request)
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
    base = body.base.model_dump(mode="json") if body.base else None
    return L.get("intent")(body.text, base)


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


# ── UI v3: provenance, monthly weather, plan finder ────────────────
def _need_data() -> None:
    if L.mock_mode() and not serve_db.exists():
        raise HTTPException(503, "needs out/serve.duckdb (run `make snapshot`)")


@app.get("/api/provenance", response_model=S.Provenance)
def provenance() -> S.Provenance:
    _need_data()
    return S.Provenance(**insight.provenance())


@app.get("/api/weather/months", response_model=S.MonthsFrame)
def weather_months(region: S.Region, year: int = Query(2026, ge=1991, le=2060),
                   climate: S.Climate = "ssp245") -> S.MonthsFrame:
    _need_data()
    return S.MonthsFrame(**insight.months(climate, year, region))


@app.post("/api/search")
def search(body: S.SearchIn) -> StreamingResponse:
    """The plan finder: every change the engine can run, then their combinations, ranked; streamed as SSE."""
    if L.mock_mode():
        raise HTTPException(503, "the plan finder runs the live model (API_MOCK=0)")
    P.ready("plan finder")
    return StreamingResponse(insight.search_events(body.climate, body.horizon_end), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ── Field Radar v4 (light redesign) ────────────────────────────────
@app.post("/api/radar/outlook", response_model=radar.Outlook)
def radar_outlook(body: radar.OutlookIn) -> radar.Outlook:
    if L.mock_mode():
        raise HTTPException(503, "the outlook runs the live model (API_MOCK=0)")
    return radar.outlook(body)


@app.get("/api/graph", response_model=kgraph.Graph)
def graph() -> kgraph.Graph:
    return kgraph.graph()


@app.get("/api/entity/{entity_id}", response_model=kgraph.EntityView)
def entity(entity_id: str) -> kgraph.EntityView:
    return kgraph.entity(entity_id)


@app.post("/api/radar/ask", response_model=kgraph.RadarAskOut)
def radar_ask(body: kgraph.RadarAskIn) -> kgraph.RadarAskOut:
    return kgraph.ask(body)


@app.get("/api/solutions", response_model=list[kgraph.Solution])
def solutions(hazard: list[str] = Query(["H1", "H2"]), crop: str | None = "pea", climate: S.Climate = "ssp245") -> list[kgraph.Solution]:
    """Cited adaptation measures for a problem (kb/solutions.json); the plan finder's result is added where it ran."""
    return kgraph.solutions(hazard, crop, climate)


@app.get("/api/tacit/topics", response_model=list[str])
def tacit_topics() -> list[str]:
    return kgraph.topics()


@app.post("/api/tacit/notes", response_model=kgraph.Filed)
def tacit_note(body: kgraph.NoteIn) -> kgraph.Filed:
    return kgraph.file_note(body)


@app.post("/api/tacit/notes/{note_id}/confirm", response_model=S.KnowledgeItem)
def tacit_confirm(note_id: str, body: kgraph.ConfirmIn) -> S.KnowledgeItem:
    return kgraph.confirm(note_id, body)


@app.patch("/api/tacit/notes/{note_id}", response_model=kgraph.Filed)
def tacit_refile(note_id: str, body: kgraph.RefileIn) -> kgraph.Filed:
    return kgraph.refile(note_id, body)


@app.post("/api/tacit/interviews", response_model=kgraph.Interview)
def tacit_interview(body: kgraph.InterviewIn) -> kgraph.Interview:
    return kgraph.interview(body)


# ── knowledge + gaps (#123): src.r_knowledge / src.r_gaps ──────────
@app.get("/api/knowledge", response_model=list[S.KnowledgeItem])
def knowledge(status: str | None = None) -> list[S.KnowledgeItem]:
    from src import r_knowledge
    return r_knowledge.items(status)


@app.post("/api/knowledge", response_model=S.KnowledgeItem)
def knowledge_add(body: S.KnowledgeIn) -> S.KnowledgeItem:
    from src import r_knowledge
    try:
        if serve_db.exists():
            with serve_db.connect() as con:
                return r_knowledge.add(body, con)
        return r_knowledge.add(body)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


@app.post("/api/knowledge/{knowledge_id}/decision", response_model=S.KnowledgeItem)
def knowledge_decide(knowledge_id: str, body: S.KnowledgeDecision) -> S.KnowledgeItem:
    from src import r_knowledge
    try:
        return _found(r_knowledge.decide(knowledge_id, body), f"knowledge {knowledge_id}")
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


@app.get("/api/gaps", response_model=list[S.Gap])
def gaps(year: int | None = None) -> list[S.Gap]:
    _need_data()
    from src import r_gaps
    with serve_db.connect() as con:
        return [S.Gap(**g) for g in r_gaps.gaps(con, year)["gaps"]]


# ── retrieval (fixtures while on hold) ─────────────────────────────
@app.post("/api/ask", response_model=S.AskOut)
def ask(body: S.AskIn) -> S.AskOut:
    return L.get("ask")(body.question, body.history)


XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@app.get("/api/report/{report_id}")
def report(report_id: str) -> FileResponse:
    if L.mock_mode():
        raise HTTPException(404, "reports are made by src.r_report in real mode (API_MOCK=0)")
    try:
        from src import r_report
    except ImportError as e:
        raise HTTPException(503, f"src.r_report not available: {e}") from e
    path = r_report.path_for(report_id)
    if path is None or not path.exists():
        raise HTTPException(404, f"report {report_id} not found")
    return FileResponse(path, media_type=XLSX, filename=path.name)


@app.get("/api/options", response_model=list[S.AdaptationOption])
def options(hazard: S.Hazard | None = None, crop: str | None = None) -> list[S.AdaptationOption]:
    return L.get("options")(hazard, crop)


@app.get("/api/board/{scenario_id}", response_model=list[S.BoardRow])
def board(scenario_id: str) -> list[S.BoardRow]:
    return L.get("board")(scenario_id)


@app.post("/api/board/{row_id}/decision", response_model=S.BoardRow)
def decide(row_id: str, d: S.Decision) -> S.BoardRow:
    return _found(L.get("decide")(row_id, d), f"board row {row_id}")
