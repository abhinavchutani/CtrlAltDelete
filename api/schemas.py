"""The v2 contract: every shape the API sends or accepts (docs/V2_ARCHITECTURE.md, "The contract").

    from api.schemas import ScenarioSpec, SimResult, Alert, AskOut, ...

This file is the only hard dependency between the three lanes. Prediction (src/p_*) and
Retrieval (src/r_*) return exactly these models; the React app gets its TypeScript types from
the exported OpenAPI (`python -m api.export_openapi`). After CP1 a shape changes only when all
three agents agree in the chat.

Additions beyond the architecture doc (no conflict with it): `ScenarioPreset` (the item shape
of GET /api/scenarios), `Health` (GET /api/health), `ReportRef` and `TableOut` (the documented
dict shapes of `AskOut.report` / `AskOut.table`, used by the fixture tests), and `eur_band()`.
"""
from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field

Door = Literal["ask", "simulate"]
Climate = Literal["ssp126", "ssp245", "ssp585"]
Region = Literal["FI_SW", "SE_SKANE"]
Crop = Literal["pea", "potato", "carrot", "spinach", "wheat", "barley", "oats", "turnip_rape", "grass_ley", "fallow"]
Severity = Literal["critical", "notable"]
Confidence = Literal["high", "medium", "low"]
EurBand = Literal["< €50k", "€50–100k", "€100–250k", "€250k–1M", "> €1M"]
# H1 drought, H2 heat at flowering, H3 waterlogging, H4 harvest rain, H5 season length, H6 blight, H7 pollen beetle
Hazard = Literal["H1", "H2", "H3", "H4", "H5", "H6", "H7"]
Window = Literal["strategic", "pre_season", "in_season"]
Simulated = Literal["simulated", "simulated_with_caveat", "assumption"]  # RISK_MITIGATION §9: say which, out loud

EUR_BANDS: tuple[str, ...] = ("< €50k", "€50–100k", "€100–250k", "€250k–1M", "> €1M")
_BAND_EDGES = (50_000, 100_000, 250_000, 1_000_000)


def eur_band(eur: float) -> EurBand:
    """The one € → band rule every layer uses (lower edge inclusive: €100k → "€100–250k")."""
    for edge, band in zip(_BAND_EDGES, EUR_BANDS):
        if eur < edge:
            return band  # type: ignore[return-value]
    return EUR_BANDS[-1]  # type: ignore[return-value]


# ── levers (the only things a spoken idea can change) ──────────────
class Irrigate(BaseModel):
    type: Literal["irrigate"]
    crop: Literal["pea", "potato"]
    target: Literal["drought_exposed", "all"] = "drought_exposed"


class EarlierSowing(BaseModel):
    type: Literal["earlier_sowing"]
    crop: Crop | Literal["all"] = "all"


class RegionSplit(BaseModel):
    type: Literal["region_split"]
    crop: Literal["pea"] = "pea"
    fi_share: float  # 0.2–0.9 (bounds and messages live in src/p_spec.py)


class HeatTolerant(BaseModel):
    type: Literal["heat_tolerant_variety"]
    crop: Literal["pea"] = "pea"
    from_year: int = 2030
    penalty_cut: float = 0.3  # 0–0.6, an ASSUMPTION


class CropArea(BaseModel):
    type: Literal["crop_area"]
    crop: Crop
    region: Region
    change_pct: float  # −50…+50


Lever = Annotated[Irrigate | EarlierSowing | RegionSplit | HeatTolerant | CropArea, Field(discriminator="type")]


class ScenarioSpec(BaseModel):
    climate: Climate = "ssp245"
    horizon_end: Literal[2031, 2040, 2050, 2060] = 2040
    levers: list[Lever] = []  # [] = their current plan
    label: str | None = None  # short human name, e.g. "Irrigate dry pea fields"


class ScenarioPreset(BaseModel):  # one item of GET /api/scenarios
    scenario_id: str
    label: str
    spec: ScenarioSpec


# ── /api/intent ────────────────────────────────────────────────────
class IntentIn(BaseModel):
    text: str
    base: ScenarioSpec | None = None  # the spec on screen; follow-ups ("add a heat-tolerant pea") build on it


class IntentOut(BaseModel):
    door: Door
    text: str
    spec: ScenarioSpec | None = None  # when door == "simulate"
    heard: list[str] = []  # chips shown back: "climate: middle path", "irrigate dry pea fields"
    problems: list[str] = []  # out-of-range values, unknown levers → shown, never silently fixed


# ── prediction ─────────────────────────────────────────────────────
class EvidenceRef(BaseModel):
    kind: Literal["result", "lineage", "weather", "table_row", "doc", "assumption"]
    ref: str
    label: str


class Alert(BaseModel):
    id: str
    year: int
    month: int | None = None  # stage month, e.g. 6 = pea flowering
    region: Region
    crop: Crop | None = None
    severity: Severity
    kind: Literal["drought_flowering", "heat_flowering", "waterlogging", "wet_harvest", "blight_weather",
                  "beetle_weather", "supply_shortfall", "risk_threshold", "assumption"]
    hazard: Hazard | None = None  # the dominant driver; picks the options from the KB
    title: str  # template text, e.g. "Pea flowering drought, SE_SKANE"
    why: str  # template text built from numbers in code
    eur_at_risk: EurBand | None = None
    suggested_lever: Lever | None = None
    evidence: list[EvidenceRef] = []


class RegionYear(BaseModel):
    region: Region
    crop: Crop
    year: int
    change_vs_baseline_pct: float  # rounded to whole %
    eur_at_risk: EurBand
    bad_year: bool  # < 80 % of the 1991–2020 mean


class Meters(BaseModel):
    eur_at_risk_per_year: EurBand  # mean over the horizon
    vs_current_plan: Literal["better", "same", "worse"]
    co2e_direction: Literal["lower", "same", "higher"]  # replacement-import emissions
    confidence: Confidence
    confidence_why: list[str]  # e.g. "near-term years", "assumption: heat-tolerant variety"


class BetterOption(BaseModel):
    spec: ScenarioSpec
    saves: EurBand
    why: str


class SimResult(BaseModel):
    scenario_id: str  # hash of the spec; presets have readable ids
    spec: ScenarioSpec
    years: list[int]  # 2026 … horizon_end
    regions: list[RegionYear]
    farms_url: str  # /api/cube/{scenario_id}/farms → FarmYear rows
    alerts: list[Alert] = Field(max_length=12)  # critical + notable only, at most 12
    meters: Meters
    better: BetterOption | None = None
    synthetic: bool = True  # UI must show the "synthetic data" banner


class FarmYear(BaseModel):
    farm_id: str
    year: int
    change_vs_baseline_pct: float
    risk: Literal["ok", "watch", "bad"]


# ── adaptation (RISK_MITIGATION_AND_ADAPTATION.md) ─────────────────
class AdaptationOption(BaseModel):  # one row of kb/adaptation_options.csv
    option_id: str
    hazards: list[Hazard]
    crops: list[str]
    option: str
    window: Window
    lead_time_yrs: tuple[int, int]
    cost_level: Literal["low", "low_med", "med", "high"]
    ghg: Literal["better", "same", "worse"]
    nutrients: Literal["better", "same", "worse", "depends"]
    water: Literal["better", "same", "worse"]
    robustness: Literal["no_regret", "scenario_dependent", "maladaptive", "reactive"]
    simulated: Simulated
    lever: Lever | None = None  # set when the engine can re-run it
    source_name: str
    source_url: str | None = None
    reviewed_by: str | None = None  # only a human fills reviewed_by


class HedgePoint(BaseModel):  # one Finland share on the frontier
    fi_share: float  # 0.00–1.00 of contracted pea volume
    expected_loss: EurBand  # mean € at risk per year
    tail_loss: EurBand  # mean of the worst 10 % of years (CVaR10)
    is_now: bool
    is_best: bool


class Hedge(BaseModel):
    climate: Climate
    points: list[HedgePoint]
    why: str  # e.g. "Moving 15 pp to FI_SW cuts the 1-in-10-year loss from €250k–1M to €100–250k"


class PathwayItem(BaseModel):  # one bar in the pathways Gantt
    crop: Crop
    region: Region
    climate: Climate
    threshold: str  # e.g. "bad-year odds > 1 in 4"
    tipping_year: int | None  # None = not crossed before horizon_end
    option_id: str
    option: str
    decide_by: int | None  # tipping_year − lead time (max); None when no tipping
    signpost: str  # e.g. "3 seasons in a row with > 5 hot days at pea flowering in SE_SKANE"
    simulated: Simulated


class BoardRow(BaseModel):  # one line of the decision board (§4.3)
    row_id: str
    scenario_id: str
    risk: str
    crop: Crop
    region: Region
    hazard: Hazard
    eur_at_risk: EurBand
    eur_tail: EurBand | None = None
    action: str
    option_ids: list[str]
    owner: str
    decide_by: int | None
    trigger: str
    evidence: list[EvidenceRef]
    robustness: str
    simulated: Simulated
    status: Literal["pending", "approved", "edited", "rejected"] = "pending"
    decided_by: str | None = None
    decided_at: str | None = None
    reason: str | None = None


class Decision(BaseModel):
    status: Literal["approved", "edited", "rejected"]
    decided_by: str = Field(min_length=1)  # typed by a human in the UI; code never fills it
    reason: str
    action: str | None = None


class WeatherCell(BaseModel):
    cell_id: str
    region: Region
    lat: float  # 0.25° square around (lat, lon)
    lon: float
    tmax_anom_c: float  # growing season vs 1991–2020
    precip_anom_pct: float
    drought_index: float  # 0–1, from the stage soil-water bucket
    hot_days_flowering: int


class WeatherFrame(BaseModel):
    climate: Climate | Literal["historical"]
    year: int
    cells: list[WeatherCell]


# ── retrieval ──────────────────────────────────────────────────────
class AskIn(BaseModel):
    question: str
    history: list[dict] = []


class AskOut(BaseModel):
    status: Literal["answered", "not_in_data"]
    answer_md: str
    table: dict | None = None  # {"columns": [...], "rows": [[...]]}, at most 50 rows
    evidence: list[EvidenceRef]  # table + record keys, file + row, or doc + section
    report: dict | None = None  # {"report_id", "filename", "url"} when a file was made
    pending_approval: bool = False  # any draft result used


class TableOut(BaseModel):  # the documented shape of AskOut.table
    columns: list[str]
    rows: list[list] = Field(max_length=50)


class ReportRef(BaseModel):  # the documented shape of AskOut.report
    report_id: str
    filename: str
    url: str


# ── platform ───────────────────────────────────────────────────────
class Health(BaseModel):
    ok: bool
    mock: bool
    serve_db: str | None  # path when out/serve.duckdb exists, else None
    llm: bool  # an LLM key is configured
    warming: bool = False  # the prediction context is still loading (V2-3)
    layers: dict[str, bool] = {}  # which src.p_* / src.r_* modules are importable (API_MOCK=0)
