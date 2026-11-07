"""Retrieval layer (v2): the adaptation options knowledge base (task #87, V2-12).

    from src.r_options import options
    options("H2", "pea")          # list[AdaptationOption], best first

Run:  python -m src.r_options H2 pea

The KB is `kb/adaptation_options.csv`, seeded from docs/RISK_MITIGATION_AND_ADAPTATION.md §7 with the §6
side-effect columns. Lead times, costs and labels the doc does not give are indicative assumptions, stated per
row in `assumption_note`. `reviewed_by` stays empty until an Apetit agronomist fills it (humans only).

Ranking (human decision, 7 Nov): hazard-specific options before all-hazard ones. Within that: options for the
asked crop before "all crops", then fewer hazards (more targeted) first, then option_id. Deterministic.
"""
from __future__ import annotations

import csv
import json
import re
import sys
from functools import lru_cache
from pathlib import Path

from api.schemas import AdaptationOption
from src.db import REPO_ROOT

KB_PATH = REPO_ROOT / "kb" / "adaptation_options.csv"
ALL_HAZARDS = ("H1", "H2", "H3", "H4", "H5", "H6", "H7")
HAZARD_NAMES = {
    "H1": "drought in sensitive stages", "H2": "heat at flowering", "H3": "waterlogging after sowing on clay",
    "H4": "rain at harvest", "H5": "season length / immaturity", "H6": "potato late blight", "H7": "pollen beetle",
}
# Plain-language cues → hazard (for questions like "what can we do about heat at flowering?").
HAZARD_CUES = (
    ("H2", r"heat|hot|flowering|high temperature"),
    ("H1", r"drought|dry|water shortage|lack of rain"),
    ("H3", r"waterlog|wet soil|flood|poorly drained|clay"),
    ("H4", r"harvest rain|rain at harvest|wet harvest"),
    ("H5", r"season length|immatur|maturity|short season|long season"),
    ("H6", r"blight"),
    ("H7", r"pollen beetle|beetle|pest"),
)
CROP_CUES = (("pea", r"\bpeas?\b"), ("potato", r"potato"), ("carrot", r"carrot"), ("spinach", r"spinach"),
             ("turnip_rape", r"turnip|rape"), ("wheat", r"wheat"), ("barley", r"barley"), ("oats", r"\boats?\b"))


def _split(cell: str) -> list[str]:
    return [x.strip() for x in cell.split(";") if x.strip()]


def row_to_option(r: dict) -> AdaptationOption:
    """One CSV row → the contract shape (`all` hazards expand to H1–H7)."""
    hazards = list(ALL_HAZARDS) if r["hazard_ids"].strip() == "all" else _split(r["hazard_ids"])
    return AdaptationOption(
        option_id=r["option_id"], hazards=hazards, crops=_split(r["crops"]), option=r["option"],
        window=r["decision_window"], lead_time_yrs=(int(r["lead_time_yrs_min"]), int(r["lead_time_yrs_max"])),
        cost_level=r["cost_level"], ghg=r["ghg_effect"], nutrients=r["nutrient_effect"], water=r["water_effect"],
        robustness=r["robustness"], simulated=r["in_yield_model"],
        lever=json.loads(r["lever"]) if r["lever"].strip() else None,
        source_name=r["source_name"], source_url=r["source_url"] or None, reviewed_by=r["reviewed_by"] or None)


@lru_cache(maxsize=1)
def _kb(path: str = str(KB_PATH)) -> tuple[tuple[dict, AdaptationOption], ...]:
    with open(path, newline="", encoding="utf-8") as f:
        return tuple((r, row_to_option(r)) for r in csv.DictReader(f))


def load_kb(path: Path = KB_PATH) -> list[AdaptationOption]:
    return [o for _, o in _kb(str(path))]


def notes(path: Path = KB_PATH) -> dict[str, str]:
    return {r["option_id"]: r["assumption_note"] for r, _ in _kb(str(path))}


def rank_key(o: AdaptationOption, crop: str | None) -> tuple:
    all_hazard = len(o.hazards) == len(ALL_HAZARDS)
    crop_specific = crop is not None and crop in o.crops
    return (all_hazard, not crop_specific, len(o.hazards), o.option_id)


def options(hazard: str | None = None, crop: str | None = None, path: Path = KB_PATH) -> list[AdaptationOption]:
    """KB rows matching the hazard and crop, best first (see the module docstring for the ranking)."""
    rows = [o for o in load_kb(path)
            if (hazard is None or hazard in o.hazards) and (crop is None or crop in o.crops or "all" in o.crops)]
    return sorted(rows, key=lambda o: rank_key(o, crop))


# ── copilot answer ("what can we do about heat at flowering?") ──────
def parse_question(q: str) -> tuple[str | None, str | None]:
    q = q.lower()
    hazard = next((h for h, pat in HAZARD_CUES if re.search(pat, q)), None)
    crop = next((c for c, pat in CROP_CUES if re.search(pat, q)), None)
    return hazard, crop


def lead_text(lead: tuple[int, int]) -> str:
    lo, hi = lead
    if hi == 0:
        return "immediate"
    if lo == hi:
        return f"{lo} yr" if lo == 1 else f"{lo} yrs"
    return f"{lo}–{hi} yrs"


def is_options_question(q: str) -> bool:
    return bool(re.search(r"what can we do|what (options|measures)|how (can|do|could) we (adapt|cope|protect|reduce|prepare)"
                          r"|adaptation options?|options? (for|against)|what should we (do|start)", q.lower()))


def answer(q: str, k: int = 5) -> dict | None:
    """AskOut-shaped dict from the KB, or None when the question isn't about adaptation options."""
    if not is_options_question(q):
        return None
    hazard, crop = parse_question(q)
    if hazard is None:
        return None
    rows = options(hazard, crop)[:k]
    if not rows:
        return None
    nts = notes()
    lines = [f"- **{o.option}** ({o.option_id}): {o.window.replace('_', '-')}, lead time "
             f"{lead_text(o.lead_time_yrs)}, cost {o.cost_level.replace('_', '–')}, "
             f"{o.robustness.replace('_', '-')}; {'the yield model can re-run it' if o.lever else o.simulated.replace('_', ' ')}"
             for o in rows]
    who = f" for {crop.replace('_', ' ')}" if crop else ""
    md = (f"Options against **{HAZARD_NAMES[hazard]}** ({hazard}){who}, best first:\n\n" + "\n".join(lines) +
          "\n\n*From our adaptation options knowledge base (seeded from LIFE AgriAdapt and the package's C3 hints). "
          "Lead times and costs are indicative assumptions, not yet reviewed by an Apetit agronomist.*")
    table = {"columns": ["option_id", "option", "window", "lead_min_yrs", "lead_max_yrs", "cost", "robustness",
                         "ghg", "nutrients", "water", "simulated", "note"],
             "rows": [[o.option_id, o.option, o.window, o.lead_time_yrs[0], o.lead_time_yrs[1], o.cost_level,
                       o.robustness, o.ghg, o.nutrients, o.water, o.simulated, nts.get(o.option_id, "")] for o in rows]}
    evidence = [{"kind": "doc", "ref": f"kb/adaptation_options.csv#{o.option_id}",
                 "label": f"kb/adaptation_options.csv · {o.option_id} ({o.source_name})"} for o in rows]
    evidence.append({"kind": "doc", "ref": "docs/RISK_MITIGATION_AND_ADAPTATION.md#7",
                     "label": "RISK_MITIGATION_AND_ADAPTATION.md § 7 Adaptation options knowledge base"})
    return {"status": "answered", "answer_md": md, "table": table, "evidence": evidence, "report": None,
            "pending_approval": any(o.reviewed_by is None for o in rows)}


def main() -> None:
    hazard = sys.argv[1] if len(sys.argv) > 1 else "H2"
    crop = sys.argv[2] if len(sys.argv) > 2 else "pea"
    for o in options(hazard, crop):
        print(o.option_id, o.option, "|", o.window, o.robustness, "| lever" if o.lever else "")


if __name__ == "__main__":
    main()
