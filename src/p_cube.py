"""Prediction layer (v2): farm × year rows of a scenario cube (task #89 wiring; GET /api/cube/{id}/farms)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.db import REPO_ROOT

CUBE_DIR = REPO_ROOT / "out" / "v2" / "cube"


def farms(scenario_id: str, year: int | None = None, cube_dir: Path = CUBE_DIR) -> list[dict]:
    """FarmYear dicts (farm_id, year, change_vs_baseline_pct, risk) from out/v2/cube/{id}_farms.parquet."""
    if "/" in scenario_id or ".." in scenario_id:
        return []
    f = cube_dir / f"{scenario_id}_farms.parquet"
    if not f.exists():
        return []
    d = pd.read_parquet(f)
    if year is not None:
        d = d[d.year == int(year)]
    return [{"farm_id": r.farm_id, "year": int(r.year), "change_vs_baseline_pct": float(round(r.change_pct, 1)), "risk": r.risk}
            for r in d.itertuples(index=False)]
