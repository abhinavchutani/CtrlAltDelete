"""Prediction layer (v2): "is there something better?" and each alert's suggested lever (task #89, V2-7).

A small fixed grid of lever combinations is run for the chosen climate and horizon (same engine, same weather path):
* better option: the combination with the lowest mean € at risk per year, if it beats the scenario by ≥ MIN_GAIN;
  `saves` is a band of the difference; `why` is a template with computed values only. Assumption levers are named.
* suggested lever for an alert: the single lever that cuts that region × crop × year € loss the most.
"""
from __future__ import annotations

import pandas as pd

from src import p_spec as S

MIN_GAIN = 0.05
GRID: dict[str, list[dict]] = {
    "irrigate_pea": [{"type": "irrigate", "crop": "pea", "target": "drought_exposed"}],
    "irrigate_potato": [{"type": "irrigate", "crop": "potato", "target": "drought_exposed"}],
    "irrigate_pea_potato": [{"type": "irrigate", "crop": "pea", "target": "drought_exposed"},
                            {"type": "irrigate", "crop": "potato", "target": "drought_exposed"}],
    "split_50_50": [{"type": "region_split", "crop": "pea", "fi_share": 0.5}],
    "split_70_30": [{"type": "region_split", "crop": "pea", "fi_share": 0.7}],
    "heat_tolerant_pea": [{"type": "heat_tolerant_variety", "crop": "pea", "from_year": 2030, "penalty_cut": 0.3}],
    "irrigate_pea_split_70_30": [{"type": "irrigate", "crop": "pea", "target": "drought_exposed"},
                                 {"type": "region_split", "crop": "pea", "fi_share": 0.7}],
    "irrigate_pea_heat_tolerant": [{"type": "irrigate", "crop": "pea", "target": "drought_exposed"},
                                   {"type": "heat_tolerant_variety", "crop": "pea", "from_year": 2030, "penalty_cut": 0.3}],
    "split_70_30_heat_tolerant": [{"type": "region_split", "crop": "pea", "fi_share": 0.7},
                                  {"type": "heat_tolerant_variety", "crop": "pea", "from_year": 2030, "penalty_cut": 0.3}],
    "irrigate_all_split_heat": [{"type": "irrigate", "crop": "pea", "target": "drought_exposed"},
                                {"type": "irrigate", "crop": "potato", "target": "drought_exposed"},
                                {"type": "region_split", "crop": "pea", "fi_share": 0.7},
                                {"type": "heat_tolerant_variety", "crop": "pea", "from_year": 2030, "penalty_cut": 0.3}]}
SINGLE = ("irrigate_pea", "irrigate_potato", "split_70_30", "heat_tolerant_pea")
LABELS = {"irrigate": "irrigate the driest {crop} fields", "region_split": "move pea sourcing to {pct} % Finland",
          "heat_tolerant_variety": "a heat-tolerant pea from {year} (assumption)"}


def describe(levers: list[dict]) -> str:
    parts = []
    for lv in levers:
        if lv["type"] == "irrigate":
            parts.append(LABELS["irrigate"].format(crop=lv["crop"]))
        elif lv["type"] == "region_split":
            parts.append(LABELS["region_split"].format(pct=round(100 * lv["fi_share"])))
        elif lv["type"] == "heat_tolerant_variety":
            parts.append(LABELS["heat_tolerant_variety"].format(year=lv["from_year"]))
        else:
            parts.append(lv["type"].replace("_", " "))
    return " + ".join(parts) or "the current plan"


def run_grid(run_spec, climate: str, horizon_end: int) -> dict[str, pd.DataFrame]:
    """combo id → region × crop × year cube (run_spec = p_engine.run_spec bound to a context)."""
    return {cid: run_spec({"climate": climate, "horizon_end": horizon_end, "levers": levers, "label": None})[0]
            for cid, levers in GRID.items()}


def mean_eur(cube: pd.DataFrame) -> float:
    return float(cube.groupby("year").eur_loss.sum().mean())


def better(spec: dict, cube: pd.DataFrame, grid: dict[str, pd.DataFrame]) -> dict | None:
    """BetterOption dict, or None when no grid combination beats this scenario by MIN_GAIN."""
    now = mean_eur(cube)
    best = min(grid, key=lambda c: (mean_eur(grid[c]), c))
    gain = now - mean_eur(grid[best])
    if gain <= MIN_GAIN * max(now, 1.0):
        return None
    co2 = float(grid[best].import_tco2e.sum() - cube.import_tco2e.sum())
    levers = GRID[best]
    why = (f"On this weather path, {describe(levers)} lowers the mean € at risk from {S.eur_band(now)} to "
           f"{S.eur_band(mean_eur(grid[best]))} a year over {spec['horizon_end'] - S.FIRST_YEAR + 1} years, and "
           f"replacement-import emissions go {'down' if co2 < 0 else 'up' if co2 > 0 else 'unchanged'}.")
    return {"spec": {"climate": spec["climate"], "horizon_end": spec["horizon_end"], "levers": levers,
                     "label": describe(levers).capitalize()},
            "saves": S.eur_band(gain), "why": why}


def suggester(cube: pd.DataFrame, grid: dict[str, pd.DataFrame]):
    """suggest(region, crop, year, hazard) → the single lever that cuts that cell's € loss most, or None."""
    base = cube.set_index(["region", "crop", "year"]).eur_loss

    def suggest(region: str, crop: str, year: int, hazard: str | None) -> dict | None:
        key = (region, crop, year)
        best, best_gain = None, 0.0
        for cid in SINGLE:
            alt = grid[cid].set_index(["region", "crop", "year"]).eur_loss
            gain = float(base.get(key, 0.0) - alt.get(key, 0.0))
            if gain > best_gain:
                best, best_gain = GRID[cid][0], gain
        return best
    return suggest
