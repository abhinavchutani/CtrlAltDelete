"""Retrieval layer (v2): tacit knowledge capture with human review (task #112; DATA_INGESTION_AND_RETRIEVAL.md §7).

    from src.r_knowledge import KnowledgeIn, KnowledgeDecision, add, decide, items, for_entities
    k = add(KnowledgeIn(statement="Old freezer line at Säkylä decommissioned March 2025", type="fact",
                        tags=["site:S-SAK", "domain:refrigerants"], linked_refs=["S-SAK"],
                        contributed_by="Matti (energy manager)", confidence="sure", source="chat:2026-11-07"))
    decide(k.knowledge_id, KnowledgeDecision(decision="approve", reviewer="Anna", note="checked"))

Run:  python -m src.r_knowledge            (lists items and their status)

Rules (doc §7.3–7.4):
* every item starts `pending_review`; nothing is saved without a person's name in `contributed_by`;
* only a person approves, rejects or supersedes it, `reviewer` is required (code never fills it), and it
  must be someone other than the contributor (four-eyes rule);
* pending items may be shown only with a label ("unreviewed"); approved items are cited as evidence with who said
  it and who approved it;
* knowledge annotates, never overwrites: measured values change only through v1's correction log, which this
  module never touches. A conflict check flags statements that contradict the data (e.g. "decommissioned" while
  that site's readings continue) for the reviewer;
* only work facts: the store keeps the statement, tags, links, contributor and review trail, nothing personal.
The store is an append-only event log, out/v2/knowledge.jsonl (one line per add or decision); state = replay.
The API shapes live in api/schemas.py (KnowledgeIn, KnowledgeItem, KnowledgeDecision, KnowledgeRefile; #123).
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from api.schemas import EvidenceRef, KnowledgeDecision, KnowledgeIn, KnowledgeItem, KnowledgeRefile
from src.db import REPO_ROOT

STORE = REPO_ROOT / "out" / "v2" / "knowledge.jsonl"
STOP_WORDS = r"decommission|shut down|closed|stopped|no longer|removed|discontinued|replaced"


STATUS = {"approve": "approved", "reject": "rejected", "supersede": "superseded"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _events(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def _append(path: Path, event: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def items(status: str | None = None, path: Path | None = None) -> list[KnowledgeItem]:
    """Current state of every item (replay of the log), optionally filtered by status."""
    state: dict[str, dict] = {}
    for e in _events(path or STORE):
        if e["event"] == "add":
            state[e["item"]["knowledge_id"]] = e["item"]
        elif e["event"] == "decision" and e["knowledge_id"] in state:
            state[e["knowledge_id"]].update(status=STATUS[e["decision"]], reviewer=e["reviewer"],
                                            review_note=e["note"], reviewed_at=e["at"])
        elif e["event"] == "refile" and e["knowledge_id"] in state:
            state[e["knowledge_id"]].update(tags=e["tags"], linked_refs=e["linked_refs"])
    out = [KnowledgeItem(**v) for v in state.values()]
    return [k for k in out if status is None or k.status == status]


def conflicts_for(k: KnowledgeIn, con=None) -> list[EvidenceRef]:
    """Statements that say something stopped, while the linked site's data continues after valid_from."""
    if con is None or not re.search(STOP_WORDS, k.statement, re.I):
        return []
    from src import r_sql as S
    since = int((k.valid_from or "1900")[:4])
    out = []
    for ref in k.linked_refs:
        if not re.match(r"^S-[A-Z]{2,4}$", ref.upper()):
            continue
        for table in ("raw_refrigerant_service_log", "raw_energy_meter_readings"):
            r = S.run_sql(f"SELECT count(*), max(year) FROM {table} WHERE site_id = ? AND year >= ?",
                          [ref.upper(), since], con=con, max_rows=1)
            n, last = r["rows"][0]
            if n:
                out.append(EvidenceRef(kind="table_row", ref=f"{table}:{ref.upper()}",
                                       label=f"{table}: {n} rows for {ref.upper()} from {since} to {last} "
                                             f"(the statement says it stopped; check before approving)"))
    return out


def add(k: KnowledgeIn, con=None, path: Path | None = None) -> KnowledgeItem:
    """Save a new item as pending_review (POST /api/knowledge). A blank contributor is refused."""
    if not k.contributed_by.strip():
        raise ValueError("contributed_by is required: the person who said it types their name")
    p = path or STORE
    n = len([e for e in _events(p) if e["event"] == "add"]) + 1
    item = KnowledgeItem(**k.model_dump(), knowledge_id=f"K-{n:04d}", created_at=_now(),
                         conflicts=conflicts_for(k, con))
    _append(p, {"event": "add", "at": item.created_at, "item": item.model_dump()})
    return item


def _same_person(a: str, b: str) -> bool:
    """Case- and space-insensitive name match (the four-eyes check compares typed names, nothing more)."""
    norm = lambda x: " ".join(x.lower().split())  # noqa: E731
    return norm(a) == norm(b)


def decide(knowledge_id: str, d: KnowledgeDecision, path: Path | None = None) -> KnowledgeItem | None:
    """Approve, reject or supersede (POST /api/knowledge/{id}/decision). A blank reviewer is refused; unknown id → None."""
    if not d.reviewer.strip():
        raise ValueError("reviewer is required: a person approves; code never fills it")
    p = path or STORE
    item = next((k for k in items(path=p) if k.knowledge_id == knowledge_id), None)
    if item is None:
        return None
    if _same_person(d.reviewer, item.contributed_by):
        raise ValueError("four-eyes rule: the person who stated it cannot review it; ask someone else")
    _append(p, {"event": "decision", "at": _now(), "knowledge_id": knowledge_id, "decision": d.decision,
                "reviewer": d.reviewer.strip(), "note": d.note})
    return next(k for k in items(path=p) if k.knowledge_id == knowledge_id)


def refile(knowledge_id: str, r: KnowledgeRefile, path: Path | None = None) -> KnowledgeItem | None:
    """Change where an item is filed (its tags and links; PATCH /api/knowledge/{id}). The statement, contributor and
    review trail never change; a refile is one more event in the log. Unknown id → None."""
    p = path or STORE
    item = next((k for k in items(path=p) if k.knowledge_id == knowledge_id), None)
    if item is None:
        return None
    _append(p, {"event": "refile", "at": _now(), "knowledge_id": knowledge_id,
                "tags": r.tags, "linked_refs": item.linked_refs if r.linked_refs is None else r.linked_refs})
    return next(k for k in items(path=p) if k.knowledge_id == knowledge_id)


def for_entities(refs: list[str], path: Path | None = None) -> list[KnowledgeItem]:
    """Approved and pending items linked to any of these IDs (rejected / superseded never come back)."""
    want = {r.upper() for r in refs}
    return [k for k in items(path=path) if k.status in ("approved", "pending_review")
            and (want & {x.upper() for x in k.linked_refs} or want & {t.split(":", 1)[-1].upper() for t in k.tags})]


def cite(k: KnowledgeItem) -> tuple[str, EvidenceRef]:
    """One answer line + its evidence, labelled by review status (doc §7.3)."""
    who = k.contributed_by + (f" ({k.role})" if k.role else "")
    if k.status == "approved":
        line = f"{k.statement} (source {k.knowledge_id}, stated by {who}, approved by {k.reviewer})"
    else:
        line = f"According to {who} (unreviewed): {k.statement} ({k.knowledge_id})"
    return line, EvidenceRef(kind="doc", ref=f"knowledge:{k.knowledge_id}",
                             label=f"knowledge {k.knowledge_id} · {k.status.replace('_', ' ')} · {who}")


def main() -> None:
    for k in items():
        print(k.knowledge_id, k.status, "|", k.statement, "|", k.contributed_by, "|", k.reviewer or "-")


if __name__ == "__main__":
    main()
