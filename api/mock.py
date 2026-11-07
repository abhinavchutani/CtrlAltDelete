"""API_MOCK=1 backend: every endpoint answered from api/fixtures/*.json (built by api.fixtures_build).

Each function has the same signature as its real layer function (api/layers.py), so the API
calls either one the same way. Fixtures are illustrative; see api/fixtures_build.py.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from api import schemas as S

FIXTURES = Path(__file__).resolve().parent / "fixtures"
SIM_IDS = {"ssp126": "current_plan_ssp245", "ssp245": "current_plan_ssp245", "ssp585": "current_plan_ssp585"}
SIMULATE_WORDS = ("what if", "what happens", "irrigat", "split", "heat-tolerant", "heat tolerant", "sow", "move ",
                  "jos ", "tänk om", "om vi")
_decisions: dict[str, S.BoardRow] = {}  # mock only: in memory, lost on restart (the real log is r_board's)


@lru_cache(maxsize=None)
def load(name: str):
    return json.loads((FIXTURES / f"{name}.json").read_text())


def spec_id(spec: S.ScenarioSpec) -> str:
    return "custom_" + hashlib.sha1(spec.model_dump_json().encode()).hexdigest()[:10]


def scenarios() -> list[S.ScenarioPreset]:
    return [S.ScenarioPreset(**p) for p in load("scenarios")]


def _sim_for(climate: str) -> S.SimResult:
    return S.SimResult(**load(f"scenario_{SIM_IDS[climate]}"))


def _reshape(base: S.SimResult, sid: str, spec: S.ScenarioSpec) -> S.SimResult:
    """Reuse a fixture for another spec: trim or keep years to the horizon (mock only)."""
    years = [y for y in base.years if y <= spec.horizon_end]
    return base.model_copy(update={
        "scenario_id": sid, "spec": spec, "years": years, "farms_url": f"/api/cube/{sid}/farms",
        "regions": [r for r in base.regions if r.year <= spec.horizon_end],
        "alerts": [a for a in base.alerts if a.year <= spec.horizon_end]})


def scenario(scenario_id: str) -> S.SimResult | None:
    preset = next((p for p in scenarios() if p.scenario_id == scenario_id), None)
    if preset is None:
        return None
    return _reshape(_sim_for(preset.spec.climate), scenario_id, preset.spec)


def simulate(spec: S.ScenarioSpec) -> S.SimResult:
    base = _sim_for(spec.climate)
    out = _reshape(base, spec_id(spec), spec)
    if spec.levers:
        out.meters = out.meters.model_copy(update={"vs_current_plan": "better"})
    return out


def farms(scenario_id: str, year: int | None = None) -> list[S.FarmYear]:
    rows = [S.FarmYear(**r) for r in load("farms")]
    if year is None:
        return rows
    have = sorted({r.year for r in rows})
    near = min(have, key=lambda y: abs(y - year))
    return [r.model_copy(update={"year": year}) for r in rows if r.year == near]


def weather(climate: str, year: int) -> S.WeatherFrame:
    frames = [S.WeatherFrame(**f) for f in load("weather")]
    same = [f for f in frames if f.climate == climate] or [f for f in frames if f.climate != "historical"]
    f = min(same, key=lambda f: abs(f.year - year))
    return f.model_copy(update={"climate": climate, "year": year})


def hedge(climate: str) -> S.Hedge:
    return S.Hedge(**load("hedge")).model_copy(update={"climate": climate})


def pathways(scenario_id: str) -> list[S.PathwayItem]:
    return [S.PathwayItem(**p) for p in load("pathways")]


def options(hazard: str | None = None, crop: str | None = None) -> list[S.AdaptationOption]:
    rows = [S.AdaptationOption(**o) for o in load("options")]
    return [o for o in rows if (hazard is None or hazard in o.hazards)
            and (crop is None or crop in o.crops or "all" in o.crops)]


def board(scenario_id: str) -> list[S.BoardRow]:
    rows = [S.BoardRow(**r) for r in load("board")]
    rows = [r.model_copy(update={"scenario_id": scenario_id}) for r in rows]
    return [_decisions.get(r.row_id, r) for r in rows]


def decide(row_id: str, d: S.Decision) -> S.BoardRow | None:
    row = next((r for r in board(row_id.rsplit("-", 1)[0]) if r.row_id == row_id), None)
    if row is None:
        return None
    row = row.model_copy(update={"status": d.status, "decided_by": d.decided_by, "reason": d.reason,
                                 "decided_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                 "action": d.action or row.action})
    _decisions[row_id] = row
    return row


def ask(question: str, history: list[dict] | None = None) -> S.AskOut:
    a = [S.AskOut(**x) for x in load("ask")]
    q = question.lower()
    if "pea" in q or "deliver" in q or "report" in q:
        return a[0]
    if "guarantee" in q or "goo" in q or "origin" in q:
        return a[1]
    return a[2]


def is_simulate(text: str) -> bool:
    t = text.lower()
    return any(w in t for w in SIMULATE_WORDS) and "deliver" not in t


def intent(text: str) -> S.IntentOut:
    fx = load("intent")
    base = S.IntentOut(**fx["simulate" if is_simulate(text) else "ask"])
    return base.model_copy(update={"text": text})


def geo_farms() -> dict:
    return load("geo_farms")


def geo_parcels() -> dict:
    return load("geo_parcels")
