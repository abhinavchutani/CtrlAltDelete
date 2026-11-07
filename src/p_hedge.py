"""Prediction layer (v2): the pea sourcing hedge frontier, Finland vs Sweden (task #91, RISK_MITIGATION §4.1).

GET /api/hedge?climate=  →  Hedge dict (api.schemas.Hedge)

Over the 30 delta-method ensemble years of the chosen SSP (c_ensemble, 2041–60 signal on 1991–2020 weather, 2025 mix):
* contracted pea volume V is fixed in total (the baseline mean); a Finland share s splits it s·V / (1 − s)·V;
* each region's production scales with its contracted volume (same yields, more or less area), as in c_euro.rebalance
  (re-implemented here, not edited there);
* one pooled contract: a year's shortfall = max(0, V − FI − SE production), costed at the volume-weighted
  contract price × replacement premium of that mix;
* expected loss = mean over the years; tail loss = CVaR10, the mean of the worst 10 % of years.
"today" = the current share; "best" = the lowest tail loss among the shares whose expected loss is within
BEST_TOLERANCE of the lowest one. € leaves only as bands; the why sentence is built from those bands.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src import c_ensemble as E
from src import c_euro as C
from src import p_spec as S

STEP = 0.05
TAIL = 0.10
BEST_TOLERANCE = 0.05


def pea_years(ctx, climate: str) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    """(year × region production t, contracted t per region, replacement €/t per region) for the SSP ensemble."""
    base = E.production(ctx.e, "baseline")
    prod = E.production(ctx.e, f"delta_{climate}")
    loss = C.losses(base, prod, ctx.prices)
    p = loss[loss.crop == "pea"].pivot_table(index="year", columns="region", values=["t", "contracted_t", "price", "premium"])
    return p["t"], p["contracted_t"].iloc[0], (p["price"] * p["premium"]).iloc[0]


def cvar(x: np.ndarray, q: float = TAIL) -> float:
    k = max(1, int(round(q * len(x))))
    return float(np.sort(x)[-k:].mean())


def frontier(t: pd.DataFrame, v: pd.Series, unit: pd.Series, step: float = STEP) -> pd.DataFrame:
    """Exact € (internal): expected and CVaR10 pooled loss per Finland share."""
    v_tot = float(v.sum())
    rows = []
    for s in np.round(np.arange(0.0, 1.0 + 1e-9, step), 4):
        new_v = pd.Series({"FI_SW": s * v_tot, "SE_SKANE": (1 - s) * v_tot})
        prod = t["FI_SW"] * new_v["FI_SW"] / v["FI_SW"] + t["SE_SKANE"] * new_v["SE_SKANE"] / v["SE_SKANE"]
        cost = float((new_v * unit).sum() / v_tot)
        yearly = ((v_tot - prod).clip(lower=0) * cost).to_numpy()
        rows.append({"fi_share": float(s), "expected": float(yearly.mean()), "tail_eur": cvar(yearly)})
    return pd.DataFrame(rows)


def mark(f: pd.DataFrame, now: float) -> pd.DataFrame:
    f = f.copy()
    f["is_now"] = False
    f.loc[(f.fi_share - now).abs().idxmin(), "is_now"] = True
    ok = f[f.expected <= f.expected.min() * (1 + BEST_TOLERANCE) + 1e-9]
    f["is_best"] = False
    f.loc[ok.tail_eur.idxmin(), "is_best"] = True
    return f


def why(f: pd.DataFrame) -> str:
    now, best = f[f.is_now].iloc[0], f[f.is_best].iloc[0]
    if now.fi_share == best.fi_share:
        return (f"Today's split ({round(100 * now.fi_share)} % Finland) is already the most robust on this ensemble: "
                f"expected loss {S.eur_band(now.expected)} a year, 1-in-10-year loss {S.eur_band(now.tail_eur)}.")
    pp = round(100 * (best.fi_share - now.fi_share))
    direction = "to FI_SW" if pp > 0 else "to SE_SKANE"
    cut = round(100 * (1 - best.tail_eur / now.tail_eur))
    b_now, b_best = S.eur_band(now.tail_eur), S.eur_band(best.tail_eur)
    move = f"from {b_now} to {b_best}" if b_now != b_best else f"by {cut} % (still {b_now})"
    return (f"Moving {abs(pp)} pp of pea volume {direction} cuts the 1-in-10-year loss {move}; "
            f"expected loss stays {S.eur_band(best.expected)} a year.") if S.eur_band(now.expected) == S.eur_band(best.expected) \
        else (f"Moving {abs(pp)} pp of pea volume {direction} cuts the 1-in-10-year loss {move}; expected loss "
              f"{S.eur_band(now.expected)} → {S.eur_band(best.expected)} a year.")


def build(ctx, climate: str) -> dict:
    t, v, unit = pea_years(ctx, climate)
    f = mark(frontier(t, v, unit), float(v["FI_SW"] / v.sum()))
    points = [{"fi_share": round(r.fi_share, 2), "expected_loss": S.eur_band(r.expected), "tail_loss": S.eur_band(r.tail_eur),
               "is_now": bool(r.is_now), "is_best": bool(r.is_best)} for r in f.itertuples(index=False)]
    return {"climate": climate, "points": points, "why": why(f)}


_CACHE: dict[str, dict] = {}


def hedge(climate: str) -> dict:
    """GET /api/hedge (api/layers.py), on the warm prediction context; cached per climate."""
    if climate not in S.CLIMATES:
        raise ValueError(f"climate must be one of {S.CLIMATES}")
    if climate not in _CACHE:
        from src import p_engine
        _CACHE[climate] = build(p_engine.warm(), climate)
    return _CACHE[climate]


if __name__ == "__main__":
    import json
    import sys
    print(json.dumps(hedge(sys.argv[1] if len(sys.argv) > 1 else "ssp245"), indent=1, ensure_ascii=False))
