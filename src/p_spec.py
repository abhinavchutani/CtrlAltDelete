"""Prediction layer (v2): ScenarioSpec validation, lever bounds, ids and € bands (task #84, V2-5).

Plain dicts shaped like `ScenarioSpec` / `Lever` in docs/V2_ARCHITECTURE.md until `api/schemas.py` (#83) lands.
`validate(spec)` never fixes a value silently: out-of-range or unknown levers come back in `problems`
(shown to the user as chips), and the cleaned spec keeps only the valid levers.
"""
from __future__ import annotations

import hashlib
import json

CLIMATES = ("ssp126", "ssp245", "ssp585")
HORIZONS = (2031, 2040, 2050, 2060)
REGIONS = ("FI_SW", "SE_SKANE")
CROPS = ("pea", "potato", "carrot", "spinach", "wheat", "barley", "oats", "turnip_rape", "grass_ley", "fallow")
FIRST_YEAR = 2026                     # last observed year (the Swedish drought) = timeline start
BOUNDS = {"fi_share": (0.2, 0.9), "penalty_cut": (0.0, 0.6), "change_pct": (-50.0, 50.0), "from_year": (2027, 2060)}
LEVER_FIELDS = {
    "irrigate": {"crop": ("pea", "potato"), "target": ("drought_exposed", "all")},
    "earlier_sowing": {"crop": CROPS + ("all",)},
    "region_split": {"crop": ("pea",), "fi_share": None},
    "heat_tolerant_variety": {"crop": ("pea",), "from_year": None, "penalty_cut": None},
    "crop_area": {"crop": CROPS, "region": REGIONS, "change_pct": None},
}
DEFAULTS = {"irrigate": {"target": "drought_exposed"}, "earlier_sowing": {"crop": "all"}, "region_split": {"crop": "pea"},
            "heat_tolerant_variety": {"crop": "pea", "from_year": 2030, "penalty_cut": 0.3}}
ASSUMPTION_LEVERS = {"heat_tolerant_variety"}      # RISK_MITIGATION §9: an assumption, said out loud
EUR_BANDS = ((50_000, "< €50k"), (100_000, "€50–100k"), (250_000, "€100–250k"), (1_000_000, "€250k–1M"))


def eur_band(eur: float) -> str:
    """The only form in which € leaves the API."""
    for upper, label in EUR_BANDS:
        if eur < upper:
            return label
    return "> €1M"


def default_spec() -> dict:
    return {"climate": "ssp245", "horizon_end": 2040, "levers": [], "label": None}


def validate_lever(lever: dict) -> tuple[dict | None, list[str]]:
    kind = lever.get("type")
    if kind not in LEVER_FIELDS:
        return None, [f"unknown lever '{kind}' (allowed: {', '.join(LEVER_FIELDS)})"]
    out, problems = {"type": kind, **DEFAULTS.get(kind, {})}, []
    for k, v in lever.items():
        if k == "type":
            continue
        if k not in LEVER_FIELDS[kind]:
            problems.append(f"{kind}: unknown field '{k}'")
            continue
        allowed = LEVER_FIELDS[kind][k]
        if allowed is not None and v not in allowed:
            problems.append(f"{kind}: {k}={v!r} not in {list(allowed)}")
            continue
        if k in BOUNDS:
            lo, hi = BOUNDS[k]
            if not isinstance(v, (int, float)) or not lo <= v <= hi:
                problems.append(f"{kind}: {k}={v!r} outside {lo}–{hi}")
                continue
        out[k] = v
    missing = [k for k in LEVER_FIELDS[kind] if k not in out]
    if missing:
        problems.append(f"{kind}: missing {', '.join(missing)}")
    return (None if problems else out), problems


def validate(spec: dict) -> tuple[dict, list[str]]:
    """Cleaned spec (valid parts only) + the problems found. Nothing is silently changed."""
    clean, problems = default_spec(), []
    for k, allowed in (("climate", CLIMATES), ("horizon_end", HORIZONS)):
        if k in spec:
            if spec[k] in allowed:
                clean[k] = spec[k]
            else:
                problems.append(f"{k}={spec[k]!r} not in {list(allowed)}; kept {clean[k]}")
    clean["label"] = spec.get("label")
    for lv in spec.get("levers", []) or []:
        ok, p = validate_lever(lv if isinstance(lv, dict) else {})
        problems += p
        if ok is not None:
            clean["levers"].append(ok)
    return clean, problems


def scenario_id(spec: dict) -> str:
    """Stable hash of the cleaned spec (presets use readable ids instead)."""
    body = {k: spec[k] for k in ("climate", "horizon_end", "levers")}
    return "s_" + hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()[:10]


def has_assumption(spec: dict) -> bool:
    return any(lv["type"] in ASSUMPTION_LEVERS for lv in spec.get("levers", []))
