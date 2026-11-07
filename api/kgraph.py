"""Field Radar v4: "What it knows", the assistant's knowledge graph, and the Teach flow that files notes into it.

    GET  /api/graph                    -> Graph   (data tables, models, documents, people's notes, gaps)
    POST /api/radar/ask                -> AskOut + the graph nodes the answer used (lights them up)
    POST /api/tacit/notes              -> Filed   (src.r_knowledge.add: always pending_review = "unverified")
    POST /api/tacit/notes/{id}/confirm -> KnowledgeItem (a second person approves: four-eyes, src.r_knowledge.decide)
    PATCH /api/tacit/notes/{id}        -> Filed   ("Edit where it went": src.r_knowledge.refile)
    POST /api/tacit/interviews         -> Interview (the questions a gap's owner answers; nothing is sent)

Counts are read from the snapshot catalog (out/v2/catalog.json row counts) and the knowledge log; no number here is
typed in. Filing is deterministic keyword rules (topic, region, farm), not an LLM. A note is never marked verified
by code: it turns solid only when a different person approves it.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, Field

from api import schemas as S
from src import serve_db
from src.db import REPO_ROOT

CATALOG = REPO_ROOT / "out" / "v2" / "catalog.json"
Kind = Literal["hub", "data", "model", "doc", "tacit", "gap"]
HUB = "crop:pea"

# The tables the pea story stands on (label, edges). Row counts come from the catalog.
DATA: list[tuple[str, str, list[str]]] = [
    ("clean_farm_registry", "Contract farms", [HUB]),
    ("raw_parcel_crop_history_and_plan", "Fields & crops", [HUB, "data:clean_farm_registry"]),
    ("clean_farm_survey", "Finnish harvests", [HUB, "model:yield"]),
    ("raw_foodhills_odlingsdata_se", "Skåne deliveries", [HUB, "model:yield"]),
    ("raw_weather_daily", "Weather", [HUB, "model:yield"]),
    ("raw_climate_grid_cells", "Climate futures", ["data:raw_weather_daily"]),
    ("raw_contract_prices_and_replacement_premiums", "Contract prices", [HUB, "model:plans"]),
    ("raw_energy_meter_readings", "Energy meters", ["data:results"]),
    ("results", "Emissions inventory", ["doc:method"]),
]
MODELS = [("model:yield", "Yield model", [HUB]), ("model:plans", "Plan finder", ["model:yield"])]
DOCS = [("doc:method", "Method note", ["model:yield"]), ("doc:reasoning", "Reasoning log", ["doc:method"]),
        ("doc:options", "Adaptation options", ["model:plans"])]

# Filing rules: words in a note → topic (first match wins).
TOPICS: list[tuple[str, str]] = [
    (r"drain|waterlog|flood|wet\b|soggy", "Sowing & drainage"),
    (r"\bsow|sowing|seed", "Sowing & drainage"),
    (r"irrigat|water(?:ing)?\b", "Irrigation"),
    (r"beetle|pest|aphid|weevil|disease|blight|mould|mold", "Pests & disease"),
    (r"heat|hot\b|drought|dry\b|rain|frost|weather", "Weather"),
    (r"harvest|yield|tonn|deliver", "Harvest & deliveries"),
    (r"soil|peat|clay|sand", "Soil"),
]
WEATHER_WORDS = r"rain|dry|drought|heat|hot|frost|wet|waterlog|flood|april|may|june|july|spring|summer"
FARM_RE = re.compile(r"\b([FS]\d{3,4})\b", re.I)
REGION_NAME = {"FI_SW": "SW Finland", "SE_SKANE": "Skåne"}
MONTHS = ["", "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November",
          "December"]


# ── shapes ──────────────────────────────────────────────────────────
class Node(BaseModel):
    id: str
    kind: Kind
    label: str
    records: int | None = None
    verified: bool | None = None  # tacit only: approved by a second person
    detail: str | None = None  # tacit statement / a gap's draft message
    question: str | None = None  # gap only: what nobody has told it yet, in words


class Edge(BaseModel):
    source: str
    target: str


class Graph(BaseModel):
    nodes: list[Node]
    edges: list[Edge]
    counts: dict[str, int]  # data / model / doc / tacit / gap
    synthetic: bool = True


class RadarAskIn(S.AskIn):
    pass


class SourceChip(BaseModel):
    node_id: str
    kind: Literal["data", "model", "doc", "tacit"]
    label: str
    detail: str | None = None


class RadarAskOut(S.AskOut):
    used_node_ids: list[str]
    sources: list[SourceChip]


class NoteIn(BaseModel):
    text: str = Field(min_length=3)
    contributed_by: str = Field(min_length=1)  # typed by the person; code never fills it
    role: str | None = None
    farm_id: str | None = None  # the farm the user came from (map card), else read from the text
    gap_id: str | None = None  # set when the note answers a gap interview


class Filed(BaseModel):
    note_id: str
    path: list[str]  # Pea › region › farm › topic
    topic: str
    siblings: int  # older notes on the same topic
    linked_node_ids: list[str]
    linked_labels: list[str]
    verified: bool
    item: S.KnowledgeItem


class ConfirmIn(BaseModel):
    reviewer: str = Field(min_length=1)
    note: str = ""


class RefileIn(BaseModel):
    topic: str


class InterviewIn(BaseModel):
    gap_id: str


class Interview(BaseModel):
    gap_id: str
    recipient: str
    questions: list[str]
    draft_message: str


# ── graph ───────────────────────────────────────────────────────────
@lru_cache(maxsize=1)
def _row_counts() -> dict[str, int]:
    out = {c["table"]: int(c.get("row_count") or 0) for c in json.loads(CATALOG.read_text())} if CATALOG.exists() else {}
    missing = [t for t, _, _ in DATA if not out.get(t)]
    if missing and serve_db.exists():  # the catalog skips counting its biggest tables
        with serve_db.connect() as con:
            for t in missing:
                try:
                    out[t] = int(con.execute(f'SELECT count(*) FROM "{t}"').fetchone()[0])
                except Exception:  # noqa: BLE001 - a table absent from the snapshot just shows no count
                    pass
    return out


def _gaps() -> list[dict]:
    if not serve_db.exists():
        return []
    from src import r_gaps
    with serve_db.connect() as con:
        return r_gaps.gaps(con, 2025)["gaps"]


def _short(s: str, n: int = 26) -> str:
    s = s.strip().rstrip(".")
    return s if len(s) <= n else s[: n - 1].rsplit(" ", 1)[0] + "…"


def _note_links(k: S.KnowledgeItem) -> list[str]:
    out = []
    for ref in k.linked_refs:
        if FARM_RE.fullmatch(ref):
            out.append("data:clean_farm_registry")
        elif ref.upper().startswith("S-"):
            out.append("data:raw_energy_meter_readings")
        elif ref.startswith(("data:", "model:", "doc:")):
            out.append(ref)
    if any(t.startswith("link:weather") for t in k.tags):
        out.append("data:raw_weather_daily")
    return list(dict.fromkeys(out)) or [HUB]


def graph() -> Graph:
    from src import r_knowledge as K

    rows = _row_counts()
    nodes = [Node(id=HUB, kind="hub", label="PEA")]
    edges: list[Edge] = []
    for table, label, to in DATA:
        nodes.append(Node(id=f"data:{table}", kind="data", label=label, records=rows.get(table)))
        edges += [Edge(source=f"data:{table}", target=t) for t in to]
    for nid, label, to in MODELS:
        nodes.append(Node(id=nid, kind="model", label=label))
        edges += [Edge(source=nid, target=t) for t in to]
    for nid, label, to in DOCS:
        nodes.append(Node(id=nid, kind="doc", label=label))
        edges += [Edge(source=nid, target=t) for t in to]
    notes = [k for k in K.items() if k.status in ("pending_review", "approved")]
    for k in notes[-20:]:  # the panel stays small; the full view could page
        nid = f"tacit:{k.knowledge_id}"
        nodes.append(Node(id=nid, kind="tacit", label=_short(k.statement), verified=k.status == "approved", detail=k.statement))
        edges += [Edge(source=nid, target=t) for t in _note_links(k)]
    gaps = _gaps()
    for g in gaps[:5]:
        site = g["owner"].split(", ", 1)[-1]  # "Energy manager, Kantvik oilseed mill" → the site's name
        what = g["record_key"].rsplit(":", 1)[-1].replace("_", " ")
        mon = MONTHS[g["month"]] if g.get("month") else ""
        nodes.append(Node(id=g["gap_id"], kind="gap", label=f"{site.split()[0]} {what}, {mon[:3]} {g['year']}?".replace(" ,", ","),
                          question=f"the {what} reading at {site} for {mon} {g['year']}".replace("  ", " "), detail=g["draft_message"]))
        edges.append(Edge(source=g["gap_id"], target="data:raw_energy_meter_readings"))
    counts = {"data": len(DATA), "model": len(MODELS), "doc": len(DOCS), "tacit": len(notes), "gap": len(gaps)}
    return Graph(nodes=nodes, edges=edges, counts=counts)


# ── ask, with the nodes it used ─────────────────────────────────────
def _node_for(e: dict) -> str | None:
    ref = e.get("ref", "")
    if ref.startswith("knowledge:"):
        return f"tacit:{ref.split(':', 1)[1]}"
    if e.get("kind") == "doc":
        if "REASONING_LOG" in ref:
            return "doc:reasoning"
        if "adaptation" in ref.lower():
            return "doc:options"
        return "doc:method"
    table = ref.split(":", 1)[0].split("#", 1)[0]
    known = {f"data:{t}" for t, _, _ in DATA}
    for t in (table, table.replace("raw_", "clean_"), f"raw_{table}", f"clean_{table}"):
        if f"data:{t}" in known:
            return f"data:{t}"
    if table.startswith("energy"):
        return "data:raw_energy_meter_readings"
    if ref.startswith(("result", "C1", "C2", "scenario")):
        return "model:yield"
    return None


def ask(body: RadarAskIn) -> RadarAskOut:
    from api import layers as L

    out = L.get("ask")(body.question, body.history)
    a = out if isinstance(out, dict) else out.model_dump()
    rows, labels = _row_counts(), {f"data:{t}": lab for t, lab, _ in DATA}
    labels |= {n: lab for n, lab, _ in MODELS} | {n: lab for n, lab, _ in DOCS}
    used: list[str] = []
    for e in a.get("evidence", []):
        n = _node_for(e)
        if n and n not in used:
            used.append(n)
    chips = []
    for n in used[:4]:
        kind = n.split(":", 1)[0]
        detail = None
        if kind == "data" and rows.get(n[5:]):
            detail = f"{rows[n[5:]]:,} rows"
        chips.append(SourceChip(node_id=n, kind=kind if kind in ("data", "model", "doc", "tacit") else "data",  # type: ignore[arg-type]
                                label=labels.get(n, n.split(":", 1)[1]), detail=detail))
    return RadarAskOut(**a, used_node_ids=used + ([HUB] if used else []), sources=chips)


# ── teach: file a note ──────────────────────────────────────────────
def _farm_region(farm_id: str) -> str | None:
    from api import geo
    return next((f["properties"]["region"] for f in geo.farms()["features"] if f["properties"]["farm_id"] == farm_id), None)


def _topic(text: str) -> str:
    return next((t for pat, t in TOPICS if re.search(pat, text, re.I)), "Notes")


def _filed(item: S.KnowledgeItem) -> Filed:
    from src import r_knowledge as K

    tag = lambda p: next((t.split(":", 1)[1] for t in item.tags if t.startswith(p + ":")), None)  # noqa: E731
    topic, region, farm = tag("topic") or "Notes", tag("region"), next((r for r in item.linked_refs if FARM_RE.fullmatch(r)), None)
    if tag("domain"):  # a gap answer: filed where the missing record lives (domain › site › topic)
        path = [tag("domain").capitalize(), tag("site") or "", topic]
        path = [p for p in path if p]
    else:
        path = ["Pea"] + ([REGION_NAME.get(region, region)] if region else []) + ([farm] if farm else []) + [topic]
    siblings = sum(1 for k in K.items() if k.knowledge_id != item.knowledge_id and k.status in ("pending_review", "approved")
                   and f"topic:{topic}" in k.tags)
    links = _note_links(item)
    label = {"data:clean_farm_registry": f"{farm}'s fields" if farm else "Contract farms",
             "data:raw_weather_daily": "its weather cell", HUB: "Pea",
             "data:raw_energy_meter_readings": f"{tag('site')}'s meter readings" if tag("site") else "Energy meters"}
    return Filed(note_id=item.knowledge_id, path=path, topic=topic, siblings=siblings,
                 linked_node_ids=[f"tacit:{item.knowledge_id}", *links], linked_labels=[label.get(n, n) for n in links],
                 verified=item.status == "approved", item=item)


def file_note(body: NoteIn) -> Filed:
    from src import r_knowledge as K

    gap = next((g for g in _gaps() if g["gap_id"] == body.gap_id), None) if body.gap_id else None
    if body.gap_id and gap is None:
        raise HTTPException(404, f"gap {body.gap_id} not found")
    if gap:  # an answer to a gap interview is about that record, not about a crop
        site = gap["owner"].split(", ", 1)[-1]
        tags = [f"domain:{gap['domain']}", f"site:{site}", "topic:Missing readings"]
        refs = [r for r in (gap["site_id"], gap["record_key"]) if r]
    else:
        farm = (body.farm_id or (m.group(1).upper() if (m := FARM_RE.search(body.text)) else None))
        region = _farm_region(farm) if farm else None
        tags = ["crop:pea", f"topic:{_topic(body.text)}"] + ([f"region:{region}"] if region else [])
        if re.search(WEATHER_WORDS, body.text, re.I):
            tags.append("link:weather")
        refs = [farm] if farm else []
    try:
        item = K.add(S.KnowledgeIn(statement=body.text.strip(), type="explanation", tags=tags, linked_refs=refs,
                                   contributed_by=body.contributed_by.strip(), role=body.role,
                                   source="interview" if body.gap_id else "assistant:teach"))
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    return _filed(item)


def confirm(note_id: str, body: ConfirmIn) -> S.KnowledgeItem:
    from src import r_knowledge as K
    try:
        item = K.decide(note_id, S.KnowledgeDecision(decision="approve", reviewer=body.reviewer, note=body.note))
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    if item is None:
        raise HTTPException(404, f"note {note_id} not found")
    return item


def refile(note_id: str, body: RefileIn) -> Filed:
    from src import r_knowledge as K
    cur = next((k for k in K.items() if k.knowledge_id == note_id), None)
    if cur is None:
        raise HTTPException(404, f"note {note_id} not found")
    tags = [t for t in cur.tags if not t.startswith("topic:")] + [f"topic:{body.topic}"]
    item = K.refile(note_id, S.KnowledgeRefile(tags=tags))
    return _filed(item)  # type: ignore[arg-type]


def topics() -> list[str]:
    return list(dict.fromkeys([t for _, t in TOPICS] + ["Missing readings", "Notes"]))


def interview(body: InterviewIn) -> Interview:
    g = next((x for x in _gaps() if x["gap_id"] == body.gap_id), None)
    if g is None:
        raise HTTPException(404, f"gap {body.gap_id} not found")
    return Interview(gap_id=g["gap_id"], recipient=g["owner"],
                     questions=["What is the real reading (or what happened that month)?",
                                "Who else could confirm it?"],
                     draft_message=g["draft_message"])
