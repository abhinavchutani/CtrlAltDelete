"""Retrieval layer: cited adaptation solutions for the hazards the twin shows (kb/solutions.json).

    from src.r_solutions import for_problem, match, answer
    for_problem(["H1"], "pea")          # solutions for drought at flowering in pea, best-supported first
    match("what helps against heat at flowering?")   # -> ["H2"] (or None when it is not a solutions question)

Deterministic: keyword rules pick the hazard, the knowledge base lists the solutions, and every line of an answer
is a quote from a named source (file + locator). No LLM writes or ranks anything here, and no number is invented:
the only numbers shown are the sources' own words. Items stay "unreviewed" until a person fills reviewed_by.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from src.db import REPO_ROOT

KB = REPO_ROOT / "kb" / "solutions.json"
HAZARD_NAME = {"H1": "drought at flowering", "H2": "heat at flowering"}
ISSUE_HAZARD = {"drought": "H1", "drought_flowering": "H1", "heat": "H2", "heat_flowering": "H2"}

ASKS_FOR_HELP = re.compile(
    r"\b(help|helps|solution|solutions|fix|what can (we|i)|what should|reduce|adapt|adaptation|cope|prevent|protect|"
    r"measure|measures|options?|mitigat\w*|avoid|ways? to)\b", re.I)
DROUGHT = re.compile(r"\b(drought|dry|dryness|water|rain|torka|kuivuus)\b", re.I)
HEAT = re.compile(r"\b(heat|hot|warm|temperature|värme|helle)\b", re.I)


@lru_cache(maxsize=1)
def _kb(path: Path = KB) -> dict:
    d = json.loads(path.read_text(encoding="utf-8"))
    ids = {s["id"] for s in d["sources"]}
    for sol in d["solutions"]:  # every citation must point at a listed source
        for e in sol["evidence"]:
            if e["source"] not in ids:
                raise ValueError(f"{sol['id']}: unknown source {e['source']}")
    return d


def sources() -> dict[str, dict]:
    return {s["id"]: s for s in _kb()["sources"]}


def for_problem(hazards: list[str], crop: str | None = "pea") -> list[dict]:
    """Solutions for any of these hazards and this crop, with each citation resolved to its source.
    Order: the ones the yield model can also run first, then by number of citations (most supported first)."""
    src = sources()
    out = []
    for sol in _kb()["solutions"]:
        if not set(hazards) & set(sol["hazards"]):
            continue
        if crop and crop not in sol["crops"] and "all" not in sol["crops"]:
            continue
        ev = [{**e, **{k: src[e["source"]][k] for k in ("publisher", "year", "title", "url", "kind")}} for e in sol["evidence"]]
        out.append({**sol, "evidence": ev, "reviewed": False})
    return sorted(out, key=lambda s: (s["lever"] is None, -len(s["evidence"]), s["id"]))


def match(question: str) -> list[str] | None:
    """The hazards a "what helps against …" question is about; None when it is not asking for solutions."""
    if not ASKS_FOR_HELP.search(question):
        return None
    hz = (["H1"] if DROUGHT.search(question) else []) + (["H2"] if HEAT.search(question) else [])
    if not hz and re.search(r"\b(flower\w*|bad (year|season)|yield|pea)\b", question, re.I):
        hz = ["H1", "H2"]
    return hz or None


def answer(question: str, crop: str = "pea") -> dict | None:
    """An AskOut-shaped answer listing the cited solutions, or None when the question is not a solutions question."""
    hz = match(question)
    if not hz:
        return None
    sols = for_problem(hz, crop)
    if not sols:
        return None
    what = " and ".join(HAZARD_NAME[h] for h in hz)
    lines = [f"{len(sols)} measures for {what} in {crop}, each backed by the sources below."]
    lines += [f"- **{s['title']}**: {s['what']}" for s in sols]
    evidence = [{"kind": "doc", "ref": f"solutions:{s['id']}#{e['source']}",
                 "label": f"{e['publisher']} ({e['year']}), {e['locator']}"} for s in sols for e in s["evidence"]]
    return {"status": "answered", "answer_md": "\n".join(lines), "table": None, "evidence": evidence, "report": None,
            "pending_approval": True, "solutions": sols}
