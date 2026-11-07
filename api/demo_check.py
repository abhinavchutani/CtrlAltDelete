"""Walk the demo (docs/V2_AGENT_WORKFLOW.md, "The demo the build must support") through the real API.

    python -m api.demo_check          # needs `make snapshot v2`; API_MOCK=0; ~30 s (model warm-up)

Prints one line per beat: ok / FAIL, what came back, and the time. Exit code 1 if any beat fails.
It calls the same routes the React app calls, in-process (FastAPI TestClient), so no server is needed.
"""
from __future__ import annotations

import os
import sys
import time

os.environ["API_MOCK"] = "0"
os.environ.setdefault("API_WARM", "0")  # we warm synchronously below

from fastapi.testclient import TestClient  # noqa: E402

from api import prediction as P  # noqa: E402
from api.main import app  # noqa: E402

c = TestClient(app)
results: list[bool] = []


def beat(n: str, title: str, fn) -> None:
    t = time.time()
    try:
        ok, note = fn()
    except Exception as e:  # noqa: BLE001 - a failed beat is reported, not raised
        ok, note = False, f"{e.__class__.__name__}: {e}"
    results.append(ok)
    print(f"{'ok  ' if ok else 'FAIL'} {n:>3} {title:52} {time.time() - t:5.2f}s  {note}")


def b1():
    sim = c.get("/api/scenario/current_plan_ssp245").json()
    se = next(r for r in sim["regions"] if r["year"] == 2026 and r["region"] == "SE_SKANE" and r["crop"] == "pea")
    fi = next(r for r in sim["regions"] if r["year"] == 2026 and r["region"] == "FI_SW" and r["crop"] == "pea")
    w = c.get("/api/weather?climate=ssp245&year=2026").json()
    dry = sum(x["drought_index"] for x in w["cells"] if x["region"] == "SE_SKANE") / max(1, sum(x["region"] == "SE_SKANE" for x in w["cells"]))
    return se["change_vs_baseline_pct"] < 0 < fi["change_vs_baseline_pct"], \
        f"2026 pea SE {se['change_vs_baseline_pct']:+.0f} % / FI {fi['change_vs_baseline_pct']:+.0f} %; SE drought index {dry:.2f} ({w['climate']})"


def b2():
    q = "How did pea deliveries from Swedish farms in 2026 compare with 2021?"
    i = c.post("/api/intent", json={"text": q}).json()
    a = c.post("/api/ask", json={"question": q}).json()
    return i["door"] == "ask" and a["status"] == "answered" and bool(a["evidence"]), \
        f"door {i['door']}; {a['status']}, {len(a['evidence'])} evidence, table {'yes' if a.get('table') else 'no'}"


def b2b():
    q = "How did pea deliveries from Swedish farms in 2026 compare with 2021?"
    r = c.post("/api/ask", json={"question": "Make that a report", "history": [{"question": q}]}).json()
    if not r.get("report"):
        return False, "no report in the answer"
    f = c.get(r["report"]["url"])
    return f.status_code == 200 and f.content[:2] == b"PK", f"{r['report']['filename']} ({len(f.content) // 1024} kB)"


def b3():
    sim = c.get("/api/scenario/current_plan_ssp245").json()
    crit = [a for a in sim["alerts"] if a["severity"] == "critical"]
    a = (crit or sim["alerts"] or [None])[0]
    return bool(a), (f"{len(sim['alerts'])} alerts ({len(crit)} critical); first: {a['year']} {a['title']} {a['eur_at_risk']}, "
                     f"lever {a['suggested_lever'] and a['suggested_lever']['type']}" if a else "no alerts")


SPEC4: dict = {}


def b4():
    t = "What if we irrigate the driest pea fields and move to a 70/30 Finland–Sweden split?"
    i = c.post("/api/intent", json={"text": t}).json()
    SPEC4.update(i["spec"] or {})
    s = c.post("/api/simulate", json=i["spec"]).json()
    return i["door"] == "simulate" and "meters" in s, f"heard {i['heard']}; € {s['meters']['eur_at_risk_per_year']}, vs plan {s['meters']['vs_current_plan']}"


def b5():
    s = c.post("/api/simulate", json=SPEC4).json()
    b = s.get("better")
    return True, (f"better: saves {b['saves']}: {b['why'][:90]}…" if b else "no better option on the grid (already best)")


def b6():
    base = c.get("/api/scenario/current_plan_ssp585").json()["spec"]
    pw = c.get("/api/pathways/current_plan_ssp585").json()
    i = c.post("/api/intent", json={"text": "What if we add a heat-tolerant pea from 2030?", "base": base}).json()
    s = c.post("/api/simulate", json=i["spec"]).json()
    decide = [p for p in pw if p["decide_by"]]
    return i["spec"]["climate"] == "ssp585" and s["meters"]["confidence"] == "low", \
        f"{len(pw)} pathway items, {len(decide)} with decide-by; heat-tolerant run: confidence {s['meters']['confidence']}"


def b7():
    h = c.get("/api/hedge?climate=ssp245").json()
    return len(h["points"]) == 21, h["why"]


def b8():
    rows = c.get("/api/board/current_plan_ssp245").json()
    live = c.get("/api/health").json()["layers"].get("live:board")
    return bool(rows), f"{len(rows)} rows ({'live' if live else 'fixture rows: src.r_board not built yet, #94'})"


def main() -> int:
    t = time.time()
    P.warm()
    if P.context_error():
        print(f"FAIL warm-up: {P.context_error()}")
        return 1
    print(f"model warm in {time.time() - t:.1f}s")
    for n, title, fn in [("1", "map on 2026: SE pea red, drought in the weather", b1),
                         ("2", "ask: pea deliveries SE 2026 vs 2021", b2), ("2b", "…make that a report", b2b),
                         ("3", "current plan ssp245: critical alert + lever", b3),
                         ("4", "what-if: irrigate dry pea + 70/30 split", b4), ("5", "better option card", b5),
                         ("6", "ssp585 pathways + heat-tolerant pea (low conf.)", b6),
                         ("7", "hedge frontier", b7), ("8", "decision board", b8)]:
        beat(n, title, fn)
    print(f"{sum(results)}/{len(results)} beats ok")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
