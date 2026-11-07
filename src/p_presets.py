"""Prediction layer (v2): the 6 preset scenarios → out/v2/ (task #84, V2-5).

Run:  python -m src.p_presets        (reads out/serve.duckdb; ~20 s context + < 1 s per preset)

Writes, per preset: out/v2/scenarios/{id}.json (SimResult), out/v2/cube/{id}.parquet (region × crop × year, exact € —
internal only) and out/v2/cube/{id}_farms.parquet (FarmYear rows), plus out/v2/scenarios/index.json
([{scenario_id, label, spec}]) for GET /api/scenarios. Levered presets are compared with the current plan of the
same climate for the meters.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from src import p_engine as P
from src.db import REPO_ROOT

OUT = REPO_ROOT / "out" / "v2"
PRESETS: dict[str, dict] = {
    "current_plan_ssp126": {"climate": "ssp126", "horizon_end": 2040, "levers": [], "label": "Current plan, low emissions"},
    "current_plan_ssp245": {"climate": "ssp245", "horizon_end": 2040, "levers": [], "label": "Current plan, middle path"},
    "current_plan_ssp585": {"climate": "ssp585", "horizon_end": 2060, "levers": [], "label": "Current plan, high emissions"},
    "irrigate_dry_pea_ssp245": {"climate": "ssp245", "horizon_end": 2040, "label": "Irrigate dry pea fields",
                                "levers": [{"type": "irrigate", "crop": "pea", "target": "drought_exposed"}]},
    "split_70_30_ssp245": {"climate": "ssp245", "horizon_end": 2040, "label": "70/30 Finland–Sweden pea split",
                           "levers": [{"type": "region_split", "crop": "pea", "fi_share": 0.7}]},
    "heat_tolerant_pea_ssp585": {"climate": "ssp585", "horizon_end": 2060, "label": "Heat-tolerant pea from 2030",
                                 "levers": [{"type": "heat_tolerant_variety", "crop": "pea", "from_year": 2030, "penalty_cut": 0.3}]},
}


def build(ctx: P.Ctx | None = None, out: Path = OUT) -> dict[str, dict]:
    ctx = ctx or P.load_context()
    (out / "scenarios").mkdir(parents=True, exist_ok=True)
    (out / "cube").mkdir(parents=True, exist_ok=True)
    plans, report = {}, {}
    for sid in sorted(PRESETS, key=lambda s: not s.startswith("current_plan")):   # plans first, for the meters
        spec = PRESETS[sid]
        t = time.time()
        sim, cube = P.run_sim(ctx, spec, sid=sid, plan=plans.get((spec["climate"], spec["horizon_end"])),
                              grid=P.grid_for(ctx, spec["climate"], spec["horizon_end"]))
        if not spec["levers"]:
            plans[(spec["climate"], spec["horizon_end"])] = cube["regions"]
        (out / "scenarios" / f"{sid}.json").write_text(json.dumps(sim, indent=1, ensure_ascii=False))
        cube["regions"].to_parquet(out / "cube" / f"{sid}.parquet", index=False)
        cube["farms"].to_parquet(out / "cube" / f"{sid}_farms.parquet", index=False)
        report[sid] = {"seconds": round(time.time() - t, 2), "meters": sim["meters"], "problems": cube["problems"]}
    idx = [{"scenario_id": sid, "label": s["label"], "spec": {k: s[k] for k in ("climate", "horizon_end", "levers", "label")}}
           for sid, s in PRESETS.items()]
    (out / "scenarios" / "index.json").write_text(json.dumps(idx, indent=1, ensure_ascii=False))
    return report


def get_scenario(sid: str, out: Path = OUT) -> dict:
    return json.loads((out / "scenarios" / f"{sid}.json").read_text())


# ── API entry points (api/layers.py) ─────────────────────────────────
def list_presets(out: Path = OUT) -> list[dict]:
    """GET /api/scenarios: [{scenario_id, label, spec}] (from out/v2, else the PRESETS table)."""
    f = out / "scenarios" / "index.json"
    if f.exists():
        return json.loads(f.read_text())
    return [{"scenario_id": sid, "label": s["label"], "spec": {k: s[k] for k in ("climate", "horizon_end", "levers", "label")}}
            for sid, s in PRESETS.items()]


def load(scenario_id: str, out: Path = OUT) -> dict | None:
    """GET /api/scenario/{id}: the precomputed SimResult, or None (→ 404)."""
    if "/" in scenario_id or ".." in scenario_id:
        return None
    f = out / "scenarios" / f"{scenario_id}.json"
    return json.loads(f.read_text()) if f.exists() else None


def main() -> None:
    t = time.time()
    ctx = P.warm()
    print(f"context {time.time() - t:.1f}s")
    for sid, r in build(ctx).items():
        m = r["meters"]
        print(f"{sid:26} {r['seconds']:5.2f}s  € {m['eur_at_risk_per_year']:10} vs plan {m['vs_current_plan']:6} "
              f"CO2e {m['co2e_direction']:6} confidence {m['confidence']}")


if __name__ == "__main__":
    main()
