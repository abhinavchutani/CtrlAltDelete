"""Retrieval layer (v2): the LLM tool loop for questions no offline route answers (task #93, V2-11).

    from src.r_loop import llm_ask
    llm_ask(con, "Which site used the most electricity in 2025?")   # AskOut dict

The model picks tools and phrases; it never supplies a number. Tools (all read-only):
* catalog_search(query, facet)   which tables hold it (src.r_catalog)
* run_sql(sql, params)           SELECT-only, allow-listed tables, 500-row cap, 5 s timeout (src.r_sql)
* search_docs(query)             pack docs + METHOD_NOTE + REASONING_LOG + detector rules (src.r_docs)
* query_results(...)             v1's results table with lineage (src.e_tools)
* make_report(template, params)  the .xlsx with a Sources sheet (src.r_report)
* energy_by_site(year, carrier)  site energy totals with the proposed corrections applied (r_agent.ENERGY_SQL)
* climate_outlook(year, climate) the v2 current-plan outlook for one season: alerts + € bands (out/v2/scenarios)
The system prompt carries a short table guide, so the model can query directly instead of searching for names.
When the step budget runs out, one last call without tools asks for an answer from what was already returned.
The final text goes through the same `finish` as the offline routes (src.r_agent), so every number in it must be
one a tool returned, or the reply is blocked; evidence comes only from the tool results. Every call goes through
src.e_llm.chat (cached, temperature 0). Without a key this module is never called: ask() answers offline.
"""
from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import duckdb

from src import e_llm, e_tools, r_docs
from src import r_sql as S

MAX_STEPS = 8
TOOL_CHARS = 4000   # per tool result sent back to the model (free tiers cap tokens per minute)
TABLE_GUIDE = """Key tables (DuckDB; query them directly with run_sql):
- raw_sites(site_id, name, country, activity, in_group_from, in_group_to): S-SAK Säkylä plant, S-KAN Kantvik mill,
  S-PUD Pudasjärvi plant, S-BJU Bjuv plant (Foodhills, SE), S-HQ Helsinki head office
- raw_energy_meter_readings(site_id, year, month, carrier, value, unit): monthly energy; for totals after the data
  corrections use the energy_by_site tool instead
- raw_fuel_deliveries(site_id, carrier, year, delivery_date, quantity, unit)
- raw_refrigerant_service_log(site_id, system, refrigerant, year, service_date, reason, event_id, kg_added)
- raw_erp_purchase_lines(posting_date, plant, material_id, material_text, supplier_id, quantity, uom, net_amount,
  currency, origin_country, movement_type); raw_suppliers(supplier_id, supplier_name, supplier_type, country, sbti_status)
- country columns use ISO codes: 'FI' Finland, 'SE' Sweden
- clean_farm_registry(farm_id, segment, region, country, organic_certified, livestock, joined_year, contract_crops)
- clean_farm_survey(farm_id, crop, year, area_ha, soil_type_reported, n_mineral_kg_ha, diesel_l_ha, irrigated, yield_t_ha)
- raw_foodhills_odlingsdata_se(odlar_id, skördeår=year, gröda=crop, areal_ha, levererad_mängd_ton=delivered t)
- raw_decarbonisation_levers(lever_id, name, scope, abatement_tco2e_2030_design, capex_eur, earliest_start, confidence)
- raw_headcount(year, site_id, headcount); raw_sales_volumes(year, month, product_group, site_id, market, t_sold, net_sales_eur)
- raw_waste_transfer_notes(site_id, year, month, waste_stream, treatment, quantity, unit)
- issues(table_name, record_key, year, issue_type, confidence, explanation, proposed_fix, status): data-quality flags
- corrections(record_key, field, old_value, new_value, reason, approved_by): proposed fixes to raw values
- results(metric, scope, category, year, scenario, value, unit, status): emissions inventory and climate-risk numbers
  (prefer query_results for emissions)
Other tables exist (catalog_search finds them)."""
SYSTEM = (
    "You are the analyst assistant for a synthetic twin of a Nordic food company's data (energy, fuels, refrigerants, "
    "purchases, contract farms, deliveries, emissions inventory, climate risk). Answer like a helpful analyst: lead "
    "with the direct answer, then one or two sentences of context (what it is compared with, what drives it, what "
    "to do next). Use the tools for every fact. Be efficient: if the table guide below names the table, call run_sql "
    "straight away (let SQL do every sum, count, max, ranking or ratio); use energy_by_site for site energy, "
    "query_results for the emissions inventory, climate_outlook for future seasons, risks and hazards by year, and "
    "search_docs for rules and methods. Do not repeat a search that already failed; try a different table or tool. "
    "Never state a number that a tool did not return, and never compute or convert one yourself: copy numbers "
    "exactly as the tools give them (same unit, same rounding) and quote € bands verbatim, e.g. '€250k–1M'. If the tools return nothing "
    "relevant, reply exactly 'Not in the data.' and say which data would be needed. Keep it to two to five "
    "sentences; the evidence list is added automatically. Call make_report only when the user asks for a report, "
    "Excel or a file. The data is synthetic: never present it as the real company's figures.\n\n" + TABLE_GUIDE
)
FINAL_NUDGE = ("Stop calling tools. Answer the question now using only what the tools returned above. If they did "
               "not return what is needed, reply 'Not in the data.' and say which data would be needed.")
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
    {"type": "function", "function": {
        "name": "energy_by_site", "description": "Energy use per site for one year in MWh, with the proposed data "
        "corrections applied (unit errors, spikes, missing months). Sorted largest first. carrier is optional, e.g. "
        "'electricity', 'district_heat', 'natural_gas', 'biogas', 'wood_chips'.",
        "parameters": {"type": "object", "properties": {
            "year": {"type": "integer"}, "carrier": {"type": "string"}}, "required": ["year"]}}},
    {"type": "function", "function": {
        "name": "climate_outlook", "description": "Climate-risk outlook for contract crops in one season (2026–2040, "
        "2060 for high emissions) under the current plan: alerts (hazard, region, crop, severity, why, € at risk "
        "band, suggested lever) and the region × crop rows (yield change vs baseline %, € at risk band, bad year). "
        "climate: 'ssp126' low emissions, 'ssp245' middle path (default), 'ssp585' high emissions.",
        "parameters": {"type": "object", "properties": {
            "year": {"type": "integer"}, "climate": {"type": "string", "enum": ["ssp126", "ssp245", "ssp585"]},
            "crop": {"type": "string"}, "region": {"type": "string"}}, "required": ["year"]}}},
]
SCENARIOS_DIR = Path(__file__).resolve().parent.parent / "out" / "v2" / "scenarios"
SEVERITY_ORDER = {"critical": 0, "notable": 1}
QR_ARGS = {"metric", "scope", "category", "category_prefix", "year", "scenario", "text", "aggregate"}


def energy_by_site(con: duckdb.DuckDBPyConnection, year: int, carrier: str | None = None) -> dict:
    """Site totals from the same corrected-energy SQL the offline energy route uses (r_agent.ENERGY_SQL)."""
    from src.r_agent import ENERGY_SQL
    where, params = ("WHERE carrier = ?", [year, year, carrier]) if carrier else ("", [year, year])
    res = S.run_sql(f"SELECT site_id, round(sum(mwh), 1) AS mwh, sum(corrected::INT) AS corrected_readings "
                    f"FROM ({ENERGY_SQL}) {where} GROUP BY 1 ORDER BY 2 DESC", params, con=con)
    res["rows"] = [[float(v) if isinstance(v, Decimal) else v for v in row] for row in res["rows"]]
    return {"year": year, "carrier": carrier or "all carriers", "unit": "MWh", **res}


def _singular(crop: str) -> str:
    """'Peas' → 'pea', 'potatoes' → 'potato': the outlook keys crops in the singular."""
    c = crop.strip().lower()
    return c[:-2] if c.endswith("oes") else c.rstrip("s")


def lever_text(lever: dict | None) -> str | None:
    """A suggested lever in words, with its numbers already in the form an answer would quote."""
    if not lever:
        return None
    crop = lever.get("crop") or "all crops"
    t = lever.get("type")
    if t == "region_split":
        fi = round(lever["fi_share"] * 100)
        return f"split {crop} sourcing {fi} % Finland / {100 - fi} % Sweden"
    if t == "irrigate":
        return f"irrigate {'all' if lever.get('target') == 'all' else 'the driest'} {crop} fields"
    if t == "heat_tolerant_variety":
        return f"heat-tolerant {crop} varieties from {lever.get('from_year', 2030)}"
    if t == "earlier_sowing":
        return f"earlier sowing of {crop}"
    if t == "crop_area":
        return f"change {crop} area by {lever.get('change_pct')} % in {lever.get('region')}"
    return t


def climate_outlook(year: int, climate: str = "ssp245", crop: str | None = None, region: str | None = None,
                    scenarios_dir: Path = SCENARIOS_DIR) -> dict:
    """One season of the precomputed current-plan scenario (src.p_presets output), filtered and ranked."""
    path = scenarios_dir / f"current_plan_{climate}.json"
    if not path.exists():
        return {"error": f"no outlook for {climate} (run `make v2`)"}
    sim = json.loads(path.read_text())
    if year not in sim["years"]:
        return {"error": f"{year} is outside the outlook ({sim['years'][0]}–{sim['years'][-1]} for {climate})"}

    crop = _singular(crop) if crop else None

    def keep(r: dict) -> bool:
        return (r["year"] == year and (not crop or r["crop"] == crop)
                and (not region or r["region"].lower() == region.lower()))
    alerts = sorted((a for a in sim["alerts"] if keep(a)), key=lambda a: SEVERITY_ORDER.get(a["severity"], 9))
    rows = sorted((r for r in sim["regions"] if keep(r)), key=lambda r: r["change_vs_baseline_pct"])
    return {"scenario": sim["spec"]["label"], "climate": climate, "year": year, "synthetic": True,
            "note": "one synthetic weather path per climate, not a forecast",
            "alerts": [{**{k: a[k] for k in ("region", "crop", "severity", "hazard", "kind", "title", "why",
                                             "eur_at_risk") if k in a},
                        "suggested_action": lever_text(a.get("suggested_lever"))} for a in alerts],
            "region_crop": rows, "plan_eur_at_risk_per_year": sim["meters"].get("eur_at_risk_per_year")}


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
        if name == "energy_by_site":
            return {"tool": name, **energy_by_site(con, int(args["year"]), args.get("carrier") or None)}
        if name == "climate_outlook":
            return {"tool": name, **climate_outlook(int(args["year"]), args.get("climate") or "ssp245",
                                                    args.get("crop") or None, args.get("region") or None)}
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
        elif r["tool"] == "energy_by_site":
            out.append(ev("table_row", "raw_energy_meter_readings",
                          "raw_energy_meter_readings + corrections (proposed fixes applied)"))
        elif r["tool"] == "climate_outlook":
            out.append(ev("result", f"scenario:current_plan_{r['climate']}:{r['year']}",
                          f"{r['scenario']} · {r['year']} (one synthetic weather path)"))
        elif r["tool"] == "query_results":
            out += [ev("result", row["result_id"], f"results · {row['result_id']} ({row['status']})")
                    for row in r.get("rows", [])[:10]]
    return out


def llm_ask(con: duckdb.DuckDBPyConnection, question: str, history: list[dict] | None = None,
            max_steps: int = MAX_STEPS) -> dict:
    """AskOut dict from the tool loop, after the shared number post-check."""
    from src.r_agent import not_in_data
    msgs = [{"role": "system", "content": SYSTEM}]
    msgs += [{"role": "user", "content": str(h.get("question") or h.get("content"))} for h in (history or [])[-3:]
             if h.get("question") or (h.get("role", "user") == "user" and h.get("content"))]
    msgs.append({"role": "user", "content": question})
    results: list[dict] = []
    for _ in range(max_steps):
        msg = e_llm.chat(msgs, TOOLS)
        msgs.append(msg)
        if not msg.get("tool_calls"):
            return _final(question, msg, results)
        for call in msg["tool_calls"]:
            try:
                args = json.loads(call["function"]["arguments"] or "{}")
            except json.JSONDecodeError:
                args = {}
            res = run_tool(con, call["function"]["name"], args)
            results.append(res)
            msgs.append({"role": "tool", "tool_call_id": call["id"], "content": json.dumps(res, default=str, ensure_ascii=False)[:TOOL_CHARS]})
    # out of steps: one last call without tools, so what the tools did return still becomes an answer
    msg = e_llm.chat(msgs + [{"role": "user", "content": FINAL_NUDGE}], None)
    if msg.get("tool_calls") or not (msg.get("content") or "").strip():
        return not_in_data(f"No final answer within {max_steps} tool steps.")
    return _final(question, msg, results)


def _final(question: str, msg: dict, results: list[dict]) -> dict:
    """The model's text → AskOut dict, after the shared number post-check."""
    from src.r_agent import finish, not_in_data, table_of
    text = (msg.get("content") or "").strip()
    if not text or text.startswith("Not in the data"):
        return not_in_data(text.removeprefix("Not in the data.").strip())
    sql = [r for r in results if r["tool"] in ("run_sql", "energy_by_site") and not r.get("error") and r.get("rows")]
    report = next((r["report"] for r in reversed(results) if r["tool"] == "make_report" and "report" in r), None)
    pending = any(row.get("status") == "draft" for r in results if r["tool"] == "query_results"
                  for row in r.get("rows", []))
    return finish(question, text, results, evidence_of(results), table_of(sql[-1]) if sql else None,
                  report=report, pending=pending)
