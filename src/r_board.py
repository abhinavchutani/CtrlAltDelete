"""Retrieval layer (v2): the adaptation decision board with an expert approval log (task #94, V2-14).

    from src.r_board import board, decide
    board("current_plan_ssp245")                      # list[BoardRow], critical risks first
    decide("current_plan_ssp245-1", Decision(...))    # BoardRow with the human's decision, appended to the log

Run:  python -m src.r_board current_plan_ssp245

Rows (docs/RISK_MITIGATION_AND_ADAPTATION.md §4.3, docs/V2_ARCHITECTURE.md "Decision board"):
* one row per risk on the scenario's alert timeline: alerts are grouped by region × crop × hazard (the same risk
  recurring in several years is one decision), critical before notable, then € band, then first year; at most 8;
* action = the best KB options for that hazard and crop (src.r_options): the alert's suggested lever first, then
  options with a pathway decide-by year, then simulated options (not assumptions), then no-regret ones;
* owner from the options' decision windows (strategic → R&D, Sourcing, CFO; …); decide-by from the adaptation pathways (src.p_pathways) when a
  tipping year exists, else empty;
* evidence = the alert's evidence + the KB rows used.
Decisions are appended to out/v2/decisions.jsonl (never to v1's tables). `decided_by` comes only from the
request body, typed by a human; code never fills it, and a blank name is refused. The latest decision per row wins
when the board is read again, so decisions survive an API restart.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from api.schemas import EUR_BANDS, BoardRow, Decision
from src import r_options
from src.db import REPO_ROOT

DECISIONS_PATH = REPO_ROOT / "out" / "v2" / "decisions.jsonl"
MAX_ROWS = 8
TOP_OPTIONS = 2
OWNERS = {"strategic": "R&D, Sourcing, CFO", "pre_season": "Agronomy, Procurement",
          "in_season": "Procurement, Supply chain"}
HAZARD_RISK = {"H1": "drought at flowering", "H2": "heat at flowering", "H3": "waterlogging after sowing",
               "H4": "rain at harvest", "H5": "short or long season", "H6": "late blight weather", "H7": "pollen beetle"}


def _alerts(scenario_id: str) -> list[dict]:
    from src import p_presets
    sim = p_presets.load(scenario_id)
    return (sim or {}).get("alerts", [])


def _pathways(scenario_id: str) -> list[dict]:
    try:
        from src import p_pathways
        return p_pathways.pathways(scenario_id)
    except Exception:  # noqa: BLE001 — no pathways yet means no decide-by year, not a broken board
        return []


def group_risks(alerts: list[dict]) -> list[dict]:
    """Alerts → one risk per region × crop × hazard, ranked critical first, then € band, then first year."""
    groups: dict[tuple, dict] = {}
    for a in alerts:
        if not (a.get("crop") and a.get("hazard") and a.get("eur_at_risk")):
            continue   # a board row needs a crop, a hazard and a € band
        g = groups.setdefault((a["region"], a["crop"], a["hazard"]), {"alerts": []})
        g["alerts"].append(a)
    out = []
    for (region, crop, hazard), g in groups.items():
        al = sorted(g["alerts"], key=lambda a: a["year"])
        worst = max(al, key=lambda a: (a["severity"] == "critical", EUR_BANDS.index(a["eur_at_risk"])))
        out.append({"region": region, "crop": crop, "hazard": hazard, "alerts": al, "worst": worst,
                    "critical": any(a["severity"] == "critical" for a in al)})
    out.sort(key=lambda r: (not r["critical"], -EUR_BANDS.index(r["worst"]["eur_at_risk"]), r["alerts"][0]["year"],
                            r["region"]))
    return out[:MAX_ROWS]


def pick_options(hazard: str, crop: str, suggested: dict | None, timed: set[str] | frozenset = frozenset()) -> list:
    """Best KB options: the alert's suggested lever, then options with a pathway decide-by year (a decision is
    due), then simulated ones (not assumptions), then no-regret, then the KB's own order."""
    opts = r_options.options(hazard, crop)
    stype = (suggested or {}).get("type")
    key = {o.option_id: i for i, o in enumerate(opts)}
    return sorted(opts, key=lambda o: (not (stype and o.lever and o.lever.type == stype), o.option_id not in timed,
                                       o.simulated == "assumption", o.robustness != "no_regret",
                                       key[o.option_id]))[:TOP_OPTIONS]


def row_id(scenario_id: str, region: str, crop: str, hazard: str) -> str:
    """Stable id: the risk itself (scenario:region:crop:hazard), never its position, so a logged decision can't
    move to another risk when the ranking changes (#122)."""
    return f"{scenario_id}:{region}:{crop}:{hazard}"


def _risk_key(x) -> tuple:
    get = x.get if isinstance(x, dict) else lambda k: getattr(x, k, None)
    return get("scenario_id"), get("region"), get("crop"), get("hazard")


def build_rows(scenario_id: str, alerts: list[dict], pathways: list[dict]) -> list[BoardRow]:
    rows = []
    for r in group_risks(alerts):
        w = r["worst"]
        timed = {p["option_id"] for p in pathways
                 if p["crop"] == r["crop"] and p["region"] == r["region"] and p.get("decide_by")}
        opts = pick_options(r["hazard"], r["crop"], w.get("suggested_lever"), timed)
        if not opts:
            continue
        ids = [o.option_id for o in opts]
        paths = [p for p in pathways if p["crop"] == r["crop"] and p["region"] == r["region"] and p["option_id"] in ids]
        decide_by = min((p["decide_by"] for p in paths if p.get("decide_by")), default=None)
        years = [a["year"] for a in r["alerts"]]
        trigger = next((p["signpost"] for p in paths if p.get("signpost")), None) or (
            f"{len(years)} alert{'s' if len(years) > 1 else ''} on this weather path ({', '.join(map(str, years))}); "
            f"worst: {w['why']}")
        evidence = [*w.get("evidence", [])]
        evidence += [{"kind": "doc", "ref": f"kb/adaptation_options.csv#{o.option_id}",
                      "label": f"kb/adaptation_options.csv · {o.option_id} (not yet reviewed by an agronomist)"}
                     for o in opts]
        rows.append(BoardRow(
            row_id=row_id(scenario_id, r["region"], r["crop"], r["hazard"]), scenario_id=scenario_id,
            risk=f"{r['crop'].replace('_', ' ').capitalize()} {HAZARD_RISK[r['hazard']]}, {r['region']}"
                 f" (first {years[0]}{', critical' if r['critical'] else ''})",
            crop=r["crop"], region=r["region"], hazard=r["hazard"], eur_at_risk=w["eur_at_risk"], eur_tail=None,
            action=" + ".join(o.option for o in opts), option_ids=ids,
            owner="; ".join(dict.fromkeys(OWNERS[o.window] for o in opts)),
            decide_by=decide_by, trigger=trigger, evidence=evidence, robustness=opts[0].robustness.replace("_", "-"),
            simulated=opts[0].simulated))
    return rows


# ── the approval log ─────────────────────────────────────────────────
def read_decisions(path: Path | None = None) -> dict[str, dict]:
    """Latest decision per row_id from the append-only log."""
    p = path or DECISIONS_PATH
    latest: dict[str, dict] = {}
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                d = json.loads(line)
                latest[d["row_id"]] = d
    return latest


def apply_decisions(rows: list[BoardRow], path: Path | None = None) -> list[BoardRow]:
    """Apply a logged decision only when its stored risk (scenario, region, crop, hazard) is this row's risk.
    Entries from before #122 (positional ids like 'scenario-1', no risk key) never match, so they apply to nothing."""
    dec = read_decisions(path)
    out = []
    for r in rows:
        d = dec.get(r.row_id)
        if d is not None and _risk_key(d) == _risk_key(r):
            r = r.model_copy(update={k: d[k] for k in ("status", "decided_by", "decided_at", "reason", "action")
                                     if d.get(k) is not None})
        out.append(r)
    return out


# ── API entry points (api/layers.py) ─────────────────────────────────
def board(scenario_id: str) -> list[BoardRow]:
    """GET /api/board/{scenario_id}: rows with the latest human decision applied; unknown ids → []."""
    if "/" in scenario_id or ".." in scenario_id:
        return []
    return apply_decisions(build_rows(scenario_id, _alerts(scenario_id), _pathways(scenario_id)))


def decide(row_id: str, d: Decision, path: Path | None = None) -> BoardRow | None:
    """POST /api/board/{row_id}/decision: log the human's decision and return the updated row (None → 404)."""
    if not d.decided_by or not d.decided_by.strip():
        raise ValueError("decided_by is required: a person types their name; code never fills it")
    scenario_id = row_id.rsplit(":", 3)[0]
    row = next((r for r in board(scenario_id) if r.row_id == row_id), None)
    if row is None:
        return None
    entry = {"row_id": row_id, "scenario_id": scenario_id, "region": row.region, "crop": row.crop,
             "hazard": row.hazard, "status": d.status, "decided_by": d.decided_by.strip(),
             "reason": d.reason, "action": d.action or row.action,
             "decided_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
             "risk": row.risk, "option_ids": row.option_ids, "eur_at_risk": row.eur_at_risk}
    p = path or DECISIONS_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return apply_decisions([row], p)[0]


def main() -> None:
    sid = sys.argv[1] if len(sys.argv) > 1 else "current_plan_ssp245"
    for r in board(sid):
        print(r.row_id, "|", r.risk, "|", r.eur_at_risk, "|", r.action, "|", r.owner, "| decide by", r.decide_by,
              "|", r.status)


if __name__ == "__main__":
    main()
