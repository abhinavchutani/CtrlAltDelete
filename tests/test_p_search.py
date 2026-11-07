"""The plan finder (src/p_search.py) on a fake engine: no data needed."""
import pandas as pd

from src import p_search as PS

YEARS = range(2026, 2041)


def fake_run(cuts: dict[str, float], base: float = 200_000.0, costly=(2026, 2032)):
    """A cube whose yearly € loss is `base` minus a cut per lever (keyed by p_search.describe), costly years +100k."""
    def run(spec: dict) -> pd.DataFrame:
        cut = sum(cuts.get(PS.describe(lv), 0.0) for lv in spec["levers"])
        rows = [{"year": y, "eur_loss": base + (100_000 if y in costly else 0) - cut, "import_tco2e": 100 - cut / 1000,
                 "bad_year": False} for y in YEARS]
        return pd.DataFrame(rows)
    return run


def events(run, climate="ssp245"):
    return list(PS.search(run, climate, 2040))


def test_search_runs_singles_then_combinations_then_stress():
    ev = events(fake_run({"irrigate all pea fields": 40_000, "heat-tolerant pea from 2028 (assumption)": 20_000}))
    kinds = [e["type"] for e in ev]
    singles = sum(len(o) for o in PS.FAMILIES.values())
    assert kinds[0] == "start" and ev[0]["total"] == singles and ev[0]["years"] == 15
    assert kinds[1:singles + 1] == ["candidate"] * singles
    phase = ev[singles + 1]
    assert phase["type"] == "phase" and phase["helped"] == ["irrigate_pea_all", "heat_pea_2028"]
    combo = ev[singles + 2]["candidate"]
    assert combo["phase"] == "combo" and combo["id"] == "irrigate_pea_all+heat_pea_2028"
    assert kinds.count("stress") == PS.STRESS_TOP and kinds[-1] == "done"
    done = ev[-1]
    assert done["best"] == "irrigate_pea_all+heat_pea_2028" and done["ranking"][0] == done["best"]
    assert done["tested"] == singles + 1


def test_only_bands_leave_and_metrics_are_counted():
    ev = events(fake_run({"irrigate the driest pea fields": 60_000}))
    for e in ev:
        if e["type"] == "candidate":
            assert not any(k.startswith("_") for k in e["candidate"])
    c = next(e["candidate"] for e in ev if e["type"] == "candidate" and e["candidate"]["id"] == "irrigate_pea")
    assert c["vs_current_plan"] == "better" and c["saves"] == "€50–100k" and c["eur_at_risk_per_year"] == "€100–250k"
    # the €60k cut takes both €300k years under the €250k line
    assert c["plan_costly_years"] == 2 and c["costly_years"] == 0 and c["worst_year"] == "€100–250k"
    assert ev[0]["plan"] == {"eur_at_risk_per_year": "€100–250k", "costly_years": 2, "worst_year": "€250k–1M"}


def test_nothing_helps_means_no_best_and_no_combinations():
    ev = events(fake_run({}))
    phase = next(e for e in ev if e["type"] == "phase")
    assert phase["helped"] == [] and ev[-1]["best"] is None
    assert all(e["candidate"]["vs_current_plan"] == "same" for e in ev if e["type"] == "candidate")


def test_ties_prefer_fewer_changes_then_no_assumption():
    results = {"a+b": {"_eur": 1.0, "levers": [1, 2], "assumption": False},
               "heat": {"_eur": 1.0, "levers": [1], "assumption": True},
               "irr": {"_eur": 1.0, "levers": [1], "assumption": False}}
    assert PS.rank(results) == ["irr", "heat", "a+b"]


def test_stress_test_reruns_the_top_plans_in_the_other_futures():
    seen = []
    run = fake_run({"irrigate all pea fields": 40_000})
    ev = events(lambda spec: seen.append(spec["climate"]) or run(spec))
    stress = [e for e in ev if e["type"] == "stress"]
    assert all(set(s["futures"]) == {"ssp126", "ssp585"} for s in stress)
    assert {"ssp126", "ssp585"} <= set(seen)
