"""Evidence copilot (Track E): answers only from tool results, and proves it.

    from src.e_agent import answer
    a = answer("What were total Scope 1 emissions in 2024 (tCO2e)?")
    a.markdown, a.value, a.unit, a.evidence, a.blocked

Two modes, same rules:
* **LLM** (LLM_API_KEY + LLM_MODEL set; OpenAI-compatible, see src/e_llm.py): the model picks tool
  calls and phrases the answer.
* **Offline stub** (no key): deterministic routing. A numeric question is answered only when it is
  plainly "<scope/category> emissions in <year>"; anything else numeric is "not in the data".
  Rubric questions return the top pack passages verbatim.

Enforced in code, whatever the mode:
* every number in the prose must equal a tool-returned number (src/e_check.py), else the reply is
  blocked; * the evidence list is appended by code from the tool results, never by the model;
* no tool result → "not in the data"; * drafts carry a "pending expert approval" badge.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

import duckdb

from src import e_check, e_llm, e_tools
from src.db import connect, db_path

NOT_IN_DATA = "Not in the data."
SYSTEM = (
    "You are the Climate & Nature Navigator copilot for a synthetic twin of a food company. "
    "Use the tools for every fact. Never state a number a tool did not return, and never compute one: "
    "use query_results with aggregate='sum' when a total is needed. Framework rules come only from "
    "search_frameworks (several rules are dated 2026), never from memory. If the tools return nothing "
    "relevant, reply exactly 'Not in the data.' and say what data would be needed. Be brief: one or two "
    "sentences. Do not write an evidence list; it is added automatically."
)
TOOLS = [
    {"type": "function", "function": {
        "name": "query_results",
        "description": "Rows of the results table (published/approved; drafts flagged) with lineage. "
                       "scope: '1', '2_location', '2_market', '3'. category e.g. 'cat1'. "
                       "metric e.g. 'tco2e', 'yield_change_pct', 'eur_at_risk'.",
        "parameters": {"type": "object", "properties": {
            "metric": {"type": "string"}, "scope": {"type": "string"}, "category": {"type": "string"},
            "year": {"type": "integer"}, "scenario": {"type": "string"},
            "text": {"type": "string", "description": "substring of result_id or category"},
            "aggregate": {"type": "string", "enum": ["sum"]}}}}},
    {"type": "function", "function": {
        "name": "search_frameworks",
        "description": "Search the pack's framework digest, source registry and docs. Returns passages with file and section.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
]


@dataclass
class Answer:
    question: str
    markdown: str
    value: float | None = None
    unit: str | None = None
    evidence: list[str] = field(default_factory=list)
    pending: bool = False
    blocked: bool = False
    mode: str = "stub"


# ── evidence ──────────────────────────────────────────────────────────
def evidence_from(results: list[dict]) -> tuple[list[str], bool]:
    ev, pending = [], False
    for r in results:
        for row in r.get("rows", []):
            pending |= row.get("status") == "draft"
            refs = ", ".join(f"{l['source_kind']}:{l['source_ref']}" for l in row.get("lineage", [])[:4])
            ev.append(f"`{row['result_id']}` ({row['status']}) ← {refs}")
        for p in r.get("passages", []):
            ev.append(f"`{p['file']}` § {p['section']}")
    return list(dict.fromkeys(ev)), pending


def finish(question: str, prose: str, results: list[dict], mode: str,
           value: float | None = None, unit: str | None = None) -> Answer:
    bad = e_check.unsupported_numbers(prose, results, question)
    if bad:
        return Answer(question, f"Blocked: the draft answer contained numbers no tool returned ({', '.join(bad)}). "
                                f"{NOT_IN_DATA}", blocked=True, mode=mode)
    ev, pending = evidence_from(results)
    if not ev or prose.strip().startswith(NOT_IN_DATA):
        return Answer(question, prose if prose.strip().startswith(NOT_IN_DATA) else NOT_IN_DATA, mode=mode)
    badge = "\n\n🟠 *Includes draft results, pending expert approval.*" if pending else ""
    md = f"{prose.strip()}{badge}\n\n{e_check.EVIDENCE_MARK}\n" + "\n".join(f"- {e}" for e in ev)
    return Answer(question, md, value, unit, ev, pending, mode=mode)


# ── offline stub ──────────────────────────────────────────────────────
_SCOPE_PATTERNS = [
    (r"\bmarket[- ]based scope 2\b", "2_market", None),
    (r"\blocation[- ]based scope 2\b", "2_location", None),
    (r"\bscope 3 category (\d+)\b", "3", "cat{}"),
    (r"\b(?:total )?scope 1\b", "1", None),
    (r"\b(?:total )?scope 3\b", "3", None),
]
_PLAIN = re.compile(r"^what (?:were|was) (?:the )?(?:total )?(.+?) emissions in (\d{4})(?: \(tco2e\))?\??$")


def parse_plain_numeric(question: str) -> dict | None:
    """Filters for a question that is exactly '<scope phrase> emissions in <year>'; else None."""
    m = _PLAIN.match(question.strip().lower())
    if not m:
        return None
    phrase, year = m.group(1).strip(), int(m.group(2))
    for pat, scope, cat in _SCOPE_PATTERNS:
        g = re.fullmatch(pat, phrase)
        if g:
            return {"metric": "tco2e", "scope": scope, "year": year,
                    "category": cat.format(g.group(1)) if cat else None}
    return None


def stub_answer(con: duckdb.DuckDBPyConnection, question: str, kind: str | None) -> Answer:
    if kind != "rubric":
        f = parse_plain_numeric(question)
        if f is None:
            if kind == "numeric":
                return Answer(question, f"{NOT_IN_DATA} (The offline stub only resolves '<scope> emissions in "
                                        "<year>' questions; this one needs the LLM mode.)")
        else:
            res = e_tools.query_results(con, **{k: v for k, v in f.items() if v is not None}, aggregate="sum")
            if f["category"] is None:  # prefer an explicit total row, else the code-computed sum
                tot = [r for r in res["rows"] if (r["category"] or "total") in ("total", "all")]
                if tot:
                    res = {**res, "rows": tot, "sum": tot[0]["value"], "n_rows": 1}
            if not res["rows"] or "sum" not in res:
                return Answer(question, f"{NOT_IN_DATA} No results match {json.dumps(f)}.")
            v, unit = res["sum"], res.get("sum_unit", "")
            prose = f"{v:,.1f} {unit} (sum of `{res['n_rows']}` result row{'s' * (res['n_rows'] != 1)})."
            return finish(question, prose, [res], "stub", v, unit)
    hits = e_tools.search_frameworks(question, k=3)
    if not hits["passages"]:
        return Answer(question, NOT_IN_DATA)
    prose = "From the pack:\n\n" + "\n\n".join(f"> {p['text']}" for p in hits["passages"])
    return finish(question, prose, [hits], "stub")


# ── LLM mode ──────────────────────────────────────────────────────────
def _run_tool(con, name: str, args: dict) -> dict:
    if name == "query_results":
        allowed = {"metric", "scope", "category", "year", "scenario", "text", "aggregate"}
        return e_tools.query_results(con, **{k: v for k, v in args.items() if k in allowed})
    if name == "search_frameworks":
        return e_tools.search_frameworks(str(args.get("query", "")))
    return {"error": f"unknown tool {name}"}


def llm_answer(con: duckdb.DuckDBPyConnection, question: str, max_steps: int = 4) -> Answer:
    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": question}]
    results: list[dict] = []
    for _ in range(max_steps):
        msg = e_llm.chat(msgs, TOOLS)
        msgs.append(msg)
        if not msg.get("tool_calls"):
            value = next((r["sum"] for r in results if "sum" in r), None)
            return finish(question, msg.get("content", ""), results, "llm", value)
        for call in msg["tool_calls"]:
            try:
                args = json.loads(call["function"]["arguments"] or "{}")
            except json.JSONDecodeError:
                args = {}
            res = _run_tool(con, call["function"]["name"], args)
            results.append(res)
            msgs.append({"role": "tool", "tool_call_id": call["id"], "content": json.dumps(res, default=str)[:12000]})
    return Answer(question, f"{NOT_IN_DATA} (no final answer within {max_steps} tool steps)", mode="llm")


def answer(question: str, kind: str | None = None, con: duckdb.DuckDBPyConnection | None = None) -> Answer:
    """kind: 'numeric' | 'rubric' | None (unknown, e.g. live chat)."""
    if con is None:
        if not db_path().exists():
            return Answer(question, f"{NOT_IN_DATA} (no results database yet: run `make all`)")
        con = connect(read_only=True)
    if e_llm.available():
        return llm_answer(con, question)
    return stub_answer(con, question, kind)
