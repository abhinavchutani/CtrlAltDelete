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
Kind = Literal["hub", "data", "model", "doc", "tacit", "gap", "entity"]
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
        ("doc:options", "Adaptation options", ["model:plans"]),
        ("doc:solutions", "Adaptation research", [HUB, "doc:options"])]

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
SITE_RE = re.compile(r"^S-[A-Z]{2,4}$", re.I)
# An entity node (a farm or a site) hangs off the table that holds its master row, so notes and gaps about the same
# farm or site group around one node: the "self-grouping" is plain ID matching, no model.
ENTITY_TABLE = {"farm": "data:clean_farm_registry", "site": "data:raw_energy_meter_readings"}
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
    tags: list[str] | None = None  # tacit only: the tags it was filed with (topic, region, crop, …)
    by: str | None = None  # tacit only: who said it


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


class Citation(BaseModel):
    source: str
    publisher: str
    year: int
    title: str
    url: str
    kind: Literal["research", "guide"]
    locator: str
    quote: str
    translation: str | None = None


class Solution(BaseModel):  # one cited measure from kb/solutions.json (src.r_solutions)
    id: str
    hazards: list[str]
    crops: list[str]
    title: str
    what: str
    window: str
    lead_time: str
    cost: str
    lever: str | None  # set when the yield model can also run it
    limits: str
    evidence: list[Citation]
    reviewed: bool = False
    model_saves: S.EurBand | None = None  # the plan finder's best single run of this lever, when it has run


class RadarAskOut(S.AskOut):
    used_node_ids: list[str]
    sources: list[SourceChip]
    solutions: list[Solution] = []


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


class EntityTable(BaseModel):
    table: str
    label: str
    rows: int
    years: str
    issues: int | None = None  # open data-quality flags on its rows (tables with a record_key only)
    corrections: int | None = None


class EntityGap(BaseModel):
    gap_id: str
    label: str


class EntityView(BaseModel):
    """Everything linked to one farm or site ID (src.r_entity.entity_view), plus people's notes and open gaps."""
    id: str
    kind: str
    name: str | None
    tables: list[EntityTable]
    issue_types: list[tuple[str, int]] = []
    notes: list[S.KnowledgeItem] = []
    gaps: list[EntityGap] = []
    synthetic: bool = True


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


def _entity_kind(ref: str) -> str | None:
    return "farm" if FARM_RE.fullmatch(ref) else "site" if SITE_RE.fullmatch(ref) else None


def _note_links(k: S.KnowledgeItem) -> list[str]:
    out = []
    for ref in k.linked_refs:
        if _entity_kind(ref):
            out.append(f"entity:{ref.upper()}")
        elif ref.startswith(("data:", "model:", "doc:")):
            out.append(ref)
    if any(t.startswith("link:weather") for t in k.tags):
        out.append("data:raw_weather_daily")
    return list(dict.fromkeys(out)) or [HUB]


def _gap_label(g: dict) -> str:
    site = g["owner"].split(", ", 1)[-1]
    what = g["record_key"].rsplit(":", 1)[-1].replace("_", " ")
    mon = MONTHS[g["month"]] if g.get("month") else ""
    return f"{site.split()[0]} {what}, {mon[:3]} {g['year']}?".replace(" ,", ",")


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
    entities: dict[str, str] = {}  # entity:ID → label

    def entity(ref: str, label: str | None = None) -> None:
        nid = f"entity:{ref.upper()}"
        if nid not in entities:
            entities[nid] = label or ref.upper()
            nodes.append(Node(id=nid, kind="entity", label=entities[nid]))
            edges.append(Edge(source=nid, target=ENTITY_TABLE[_entity_kind(ref) or "farm"]))

    notes = [k for k in K.items() if k.status in ("pending_review", "approved")]
    for k in notes[-20:]:  # the panel stays small; the full view could page
        nid = f"tacit:{k.knowledge_id}"
        for ref in k.linked_refs:
            if _entity_kind(ref):
                entity(ref)
        nodes.append(Node(id=nid, kind="tacit", label=_short(k.statement), verified=k.status == "approved", detail=k.statement,
                          tags=k.tags, by=k.contributed_by))
        edges += [Edge(source=nid, target=t) for t in _note_links(k)]
    gaps = _gaps()
    for g in gaps[:5]:
        site = g["owner"].split(", ", 1)[-1]  # "Energy manager, Kantvik oilseed mill" → the site's name
        what = g["record_key"].rsplit(":", 1)[-1].replace("_", " ")
        mon = MONTHS[g["month"]] if g.get("month") else ""
        nodes.append(Node(id=g["gap_id"], kind="gap", label=_gap_label(g),
                          question=f"the {what} reading at {site} for {mon} {g['year']}".replace("  ", " "), detail=g["draft_message"]))
        if g.get("site_id") and SITE_RE.fullmatch(g["site_id"]):
            entity(g["site_id"], site.split()[0])
            edges.append(Edge(source=g["gap_id"], target=f"entity:{g['site_id'].upper()}"))
        else:
            edges.append(Edge(source=g["gap_id"], target="data:raw_energy_meter_readings"))
    counts = {"data": len(DATA), "model": len(MODELS), "doc": len(DOCS), "tacit": len(notes), "gap": len(gaps),
              "entity": len(entities)}
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


def _model_saves(climate: str = "ssp245", horizon_end: int = 2040) -> dict[str, S.EurBand]:
    """Lever type → the best "saves" band among the plan finder's single-change runs (only if that run exists)."""
    from api import insight
    run = insight._RUNS.get((climate, horizon_end))  # noqa: SLF001 - read-only peek at a finished run
    if run is None:
        return {}
    bands = list(S.EUR_BANDS)
    best: dict[str, str] = {}
    for ev in list(run.events):
        c = ev.get("candidate") if ev.get("type") == "candidate" else None
        if not c or c.get("phase") != "single" or not c.get("saves"):
            continue
        t = c["levers"][0]["type"]
        if t not in best or bands.index(c["saves"]) > bands.index(best[t]):
            best[t] = c["saves"]
    return best  # type: ignore[return-value]


def solutions(hazards: list[str], crop: str | None = "pea", climate: str = "ssp245") -> list[Solution]:
    from src import r_solutions
    saves = _model_saves(climate)
    return [Solution(**s, model_saves=saves.get(s["lever"]) if s["lever"] else None) for s in r_solutions.for_problem(hazards, crop)]


def ask(body: RadarAskIn) -> RadarAskOut:
    from api import layers as L
    from src import r_solutions

    sol = r_solutions.answer(body.question)
    if sol:  # "what helps against …": answered from the cited solutions base, not the data tools
        sols = solutions(r_solutions.match(body.question) or [])
        pubs = list(dict.fromkeys(f"{e.publisher} ({e.year})" for x in sols for e in x.evidence))
        chips = [SourceChip(node_id="doc:solutions", kind="doc", label="Adaptation research",
                            detail=f"{len(pubs)} sources")]
        if any(x.model_saves for x in sols):
            chips.append(SourceChip(node_id="model:plans", kind="model", label="Plan finder", detail="model runs"))
        return RadarAskOut(**{k: v for k, v in sol.items() if k != "solutions"}, solutions=sols, sources=chips,
                           used_node_ids=["doc:solutions", HUB, "doc:options"] + (["model:plans"] if len(chips) > 1 else []))

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
    label = {"data:raw_weather_daily": "its weather cell", HUB: "Pea"}
    for n in links:
        if n.startswith("entity:"):
            ref = n.split(":", 1)[1]
            label[n] = f"{ref}'s fields" if _entity_kind(ref) == "farm" else f"{tag('site') or ref}'s meter readings"
    parents = [ENTITY_TABLE[_entity_kind(n.split(":", 1)[1]) or "farm"] for n in links if n.startswith("entity:")]
    return Filed(note_id=item.knowledge_id, path=path, topic=topic, siblings=siblings,
                 linked_node_ids=list(dict.fromkeys([f"tacit:{item.knowledge_id}", *links, *parents])),
                 linked_labels=[label.get(n, n) for n in links],
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


# ── entity drawer: everything linked to one farm or site ────────────
def _table_label(table: str) -> str:
    known = {t: lab for t, lab, _ in DATA}
    return known.get(table) or table.removeprefix("raw_").removeprefix("clean_").replace("_", " ").capitalize().replace("Goo ", "GoO ")


def entity(entity_id: str) -> EntityView:
    """Tables (rows, years, open flags), people's notes and open gaps for one ID; read-only (src.r_entity)."""
    from src import r_entity, r_knowledge as K

    eid = entity_id.strip().upper()
    if not _entity_kind(eid):
        raise HTTPException(404, f"{entity_id} is not a farm or site ID")
    if not serve_db.exists():
        raise HTTPException(503, "needs the serve database (out/serve.duckdb)")
    with serve_db.connect() as con:
        v = r_entity.entity_view(con, eid)
    if v is None:
        raise HTTPException(404, f"{entity_id} not found")
    names = {r[0] for r in v["rows"]}
    tables = [EntityTable(table=t, label=_table_label(t), rows=int(n), years=yrs, issues=iss, corrections=corr)
              for t, _col, n, yrs, iss, corr, _ex in v["rows"]
              if not (t.startswith("raw_") and any(t[4:].startswith(c[6:]) for c in names if c.startswith("clean_")))]
    # ↑ the cleaned copy stands for its raw file
    tables.sort(key=lambda x: -x.rows)
    gaps = [EntityGap(gap_id=g["gap_id"], label=_gap_label(g)) for g in _gaps()
            if (g.get("site_id") or "").upper() == eid or eid in g["record_key"].upper()]
    return EntityView(id=eid, kind=v["kind"], name=REGION_NAME.get(v["name"], v["name"]), tables=tables,
                      issue_types=[(t, int(n)) for t, n in v.get("issue_types", [])],
                      notes=K.for_entities([eid]), gaps=gaps)
