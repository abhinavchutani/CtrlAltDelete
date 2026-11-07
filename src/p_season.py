"""Prediction layer (v2): month-by-month weather of one region in one year (`GET /api/weather/months`, UI v3).

The map's weather effects (rain, heat, drought) and the alert cards read this. Region means over the region's
grid cells from the pack's `raw_weather_monthly`: 'historical' up to 2026, then the chosen SSP path (one synthetic
realisation, not a forecast). Anomalies are against the same months of 1991–2020. Deterministic.
"""
from __future__ import annotations

import duckdb

LAST_OBSERVED = 2026
NORMAL = (1991, 2020)


def months(con: duckdb.DuckDBPyConnection, climate: str, year: int, region: str) -> dict:
    scenario = "historical" if year <= LAST_OBSERVED else climate
    rows = con.execute(
        """WITH cells AS (SELECT cell_id FROM raw_climate_grid_cells WHERE region = $region),
           m AS (SELECT month, avg(precip_mm) AS p, avg(tmean_c) AS t, avg(hot_days_tmax_ge_27) AS hot
                 FROM raw_weather_monthly WHERE scenario = $scenario AND year = $year
                   AND cell_id IN (SELECT cell_id FROM cells) GROUP BY month),
           n AS (SELECT month, avg(precip_mm) AS p, avg(tmean_c) AS t
                 FROM raw_weather_monthly WHERE scenario = 'historical' AND year BETWEEN $y0 AND $y1
                   AND cell_id IN (SELECT cell_id FROM cells) GROUP BY month)
           SELECT m.month, m.p, n.p, m.t, n.t, m.hot FROM m JOIN n USING (month) ORDER BY m.month""",
        {"region": region, "scenario": scenario, "year": year, "y0": NORMAL[0], "y1": NORMAL[1]},
    ).fetchall()
    return {
        "climate": scenario, "year": year, "region": region,
        "months": [{"month": int(mo), "precip_mm": round(p, 1),
                    "precip_anom_pct": round(100 * (p / np_ - 1)) if np_ else 0,
                    "tmean_c": round(t, 1), "tmean_anom_c": round(t - nt, 1), "hot_days": round(hot, 1)}
                   for mo, p, np_, t, nt, hot in rows],
    }
