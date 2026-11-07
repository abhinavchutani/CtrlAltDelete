"""Retrieval layer (v2): the LLM tool loop for questions no offline route answers (task #93, V2-11).

    from src.r_loop import llm_ask
    llm_ask(con, "Which site used the most electricity in 2025?")   # AskOut dict

The model picks tools and phrases; it never supplies a number. Tools (all read-only):
* catalog_search(query, facet)   which tables hold it (src.r_catalog)
* run_sql(sql, params)           SELECT-only, allow-listed tables, 500-row cap, 5 s timeout (src.r_sql)
* search_docs(query)             pack docs + METHOD_NOTE + REASONING_LOG + detector rules (src.r_docs)
* query_results(...)             v1's results table with lineage (src.e_tools)
* make_report(template, params)  the .xlsx with a Sources sheet (src.r_report)
The final text goes through the same `finish` as the offline routes (src.r_agent), so every number in it must be
one a tool returned, or the reply is blocked; evidence comes only from the tool results. Every call goes through
src.e_llm.chat (cached, temperature 0). Without a key this module is never called: ask() answers offline.
"""
from __future__ import annotations

import json
from decimal import Decimal

import duckdb

from src import e_llm, e_tools, r_docs
from src import r_sql as S

MAX_STEPS = 6
SYSTEM = (
    "You answer questions about a synthetic twin of a Nordic food company's data (energy, fuels, refrigerants, "
    "purchases, farms, deliveries, emissions inventory, climate risk). Use the tools for every fact: find the table "
    "with catalog_search, then run_sql (DuckDB SQL, SELECT only; let SQL do any sum, count, max or ratio), or "
    "query_results for the emissions inventory, or search_docs for rules and methods. Never state a number that a "
    "tool did not return, and never compute one yourself. If the tools return nothing relevant, reply exactly "
    "'Not in the data.' and say which data would be needed. Answer in one to three sentences; the evidence list is "
    "added automatically. Call make_report only when the user asks for a report, Excel or a file."
)
TOOLS = [
    {"type": "function", "function": {
        "name": "catalog_search", "description": "Find the tables that hold something. Returns table cards "
        "(columns, years, source file, facets).",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string"},
            "facet": {"type": "object", "description": "optional filter, e.g. {\"domain\": \"energy\"}"}},
            "required": ["query"]}}},
    {"type": "function", "function": {
        "name": "run_sql", "description": "Run one read-only DuckDB SELECT over raw_* / clean_* tables, results, "
        "lineage, corrections or issues. Use ? placeholders with params. Max 500 rows.",
        "parameters": {"type": "object", "properties": {
            "sql": {"type": "string"}, "params": {"type": "array", "items": {}}}, "required": ["sql"]}}},
    {"type": "function", "function": {
        "name": "search_docs", "description": "Search framework docs, our method note, reasoning log (rules R01–R34) "
        "and data-quality rules. Returns passages with file and section.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {
        "name": "query_results", "description": "Emissions inventory and model results with lineage. Inventory: "
        "metric='tco2e' (scope 'scope1' | 'scope2_market' | 'scope2_location' | 'scope3' | 'total'), line items "
        "metric='tco2e_line'. aggregate='sum' returns a code-computed total.",
        "parameters": {"type": "object", "properties": {
            "metric": {"type": "string"}, "scope": {"type": "string"}, "category": {"type": "string"},
            "category_prefix": {"type": "string"}, "year": {"type": "integer"}, "scenario": {"type": "string"},
            "text": {"type": "string"}, "aggregate": {"type": "string", "enum": ["sum"]}}}}},
    {"type": "function", "function": {
        "name": "make_report", "description": "Write an Excel report with a Sources sheet. Templates: "
        "deliveries_by_farm_year {region, crop, years}, energy_by_site_month {year}, farm_yield_history {farm_id}, "
        "inventory_summary {years}.",
        "parameters": {"type": "object", "properties": {
            "template": {"type": "string"}, "params": {"type": "object"}}, "required": ["template"]}}},
]
QR_ARGS = {"metric", "scope", "category", "category_prefix", "year", "scenario", "text", "aggregate"}


def run_tool(con: duckdb.DuckDBPyConnection, name: str, args: dict) -> dict:
    """One tool call → a JSON-able result (errors come back as {'error': ...}, never raised to the model)."""
    try:
        if name == "catalog_search":
            from src.r_catalog import catalog_search
            return {"tool": name, **catalog_search(str(args.get("query", "")), k=5, facet=args.get("facet") or None)}
        if name == "run_sql":
            res = S.run_sql(str(args.get("sql", "")), list(args.get("params") or []), con=con)
            # DuckDB DECIMAL → float, so the number post-check (which reads int/float) sees every returned value
            res["rows"] = [[float(v) if isinstance(v, Decimal) else v for v in row] for row in res["rows"]]
            return {"tool": name, **res}
        if name == "search_docs":
            return {"tool": name, **r_docs.search_docs(str(args.get("query", "")), k=4, con=con)}
        if name == "query_results":
            return {"tool": name, **e_tools.query_results(con, **{k: v for k, v in args.items() if k in QR_ARGS})}
        if name == "make_report":
            from src.r_report import make_report
            return {"tool": name, "report": make_report(con, str(args.get("template", "")), args.get("params") or {})}
    except S.SqlRefused as e:
        return {"tool": name, "error": f"refused: {e}"}
    except Exception as e:  # noqa: BLE001 — the model sees the error and can try another tool
        return {"tool": name, "error": str(e).splitlines()[0][:300]}
    return {"tool": name, "error": f"unknown tool {name}"}


def evidence_of(results: list[dict]) -> list[dict]:
    from src.r_agent import doc_evidence, ev, sql_evidence
    out: list[dict] = []
    for r in results:
        if r.get("error"):
            continue
        if r["tool"] == "run_sql":
            out += sql_evidence(r)
        elif r["tool"] == "search_docs":
            out += doc_evidence(r)
        elif r["tool"] == "query_results":
            out += [ev("result", row["result_id"], f"results · {row['result_id']} ({row['status']})")
                    for row in r.get("rows", [])[:10]]
    return out


def llm_ask(con: duckdb.DuckDBPyConnection, question: str, history: list[dict] | None = None,
            max_steps: int = MAX_STEPS) -> dict:
    """AskOut dict from the tool loop, after the shared number post-check."""
    from src.r_agent import finish, not_in_data, table_of
    msgs = [{"role": "system", "content": SYSTEM}]
    msgs += [{"role": "user", "content": str(h.get("question") or h.get("content"))} for h in (history or [])[-3:]
             if h.get("question") or (h.get("role", "user") == "user" and h.get("content"))]
    msgs.append({"role": "user", "content": question})
    results: list[dict] = []
    for _ in range(max_steps):
        msg = e_llm.chat(msgs, TOOLS)
        msgs.append(msg)
        if not msg.get("tool_calls"):
            text = (msg.get("content") or "").strip()
            if not text or text.startswith("Not in the data"):
                return not_in_data(text.removeprefix("Not in the data.").strip())
            sql = [r for r in results if r["tool"] == "run_sql" and not r.get("error") and r.get("rows")]
            report = next((r["report"] for r in reversed(results) if r["tool"] == "make_report" and "report" in r), None)
            pending = any(row.get("status") == "draft" for r in results if r["tool"] == "query_results"
                          for row in r.get("rows", []))
            return finish(question, text, results, evidence_of(results), table_of(sql[-1]) if sql else None,
                          report=report, pending=pending)
        for call in msg["tool_calls"]:
            try:
                args = json.loads(call["function"]["arguments"] or "{}")
            except json.JSONDecodeError:
                args = {}
            res = run_tool(con, call["function"]["name"], args)
            results.append(res)
            msgs.append({"role": "tool", "tool_call_id": call["id"], "content": json.dumps(res, default=str)[:12000]})
    return not_in_data(f"No final answer within {max_steps} tool steps.")
