"""p_parse offline rules: 12 phrasings → door, spec and problems (no data, no LLM key needed)."""
import pytest

from src import p_parse as P

L = lambda **k: k  # noqa: E731


@pytest.mark.parametrize("text, door, climate, horizon, levers", [
    ("How did pea deliveries from Swedish farms in 2026 compare with 2021?", "ask", None, None, None),
    ("Make that a report", "ask", None, None, None),
    ("Show the current plan on the middle path to 2040", "simulate", "ssp245", 2040, []),
    ("What if we irrigate the driest pea fields and move to a 70/30 Finland–Sweden split?", "simulate", "ssp245", 2040,
     [L(type="irrigate", crop="pea", target="drought_exposed"), L(type="region_split", crop="pea", fi_share=0.7)]),
    ("Switch to SSP5-8.5 out to 2060", "simulate", "ssp585", 2060, []),
    ("Add a heat-tolerant pea from 2030", "simulate", "ssp245", 2040,
     [L(type="heat_tolerant_variety", crop="pea", from_year=2030, penalty_cut=0.3)]),
    ("What if we irrigate all potato fields in the worst case?", "simulate", "ssp585", 2040,
     [L(type="irrigate", crop="potato", target="all")]),
    ("Try sowing peas earlier", "simulate", "ssp245", 2040, [L(type="earlier_sowing", crop="pea")]),
    ("Cut Swedish pea area by 20 % by 2050", "simulate", "ssp245", 2050,
     [L(type="crop_area", crop="pea", region="SE_SKANE", change_pct=-20)]),
    ("Simulate a 50/50 split with low emissions", "simulate", "ssp126", 2040, [L(type="region_split", crop="pea", fi_share=0.5)]),
])
def test_phrasings(text, door, climate, horizon, levers):
    out = P.offline(text)
    assert out["door"] == door, out
    if door == "simulate":
        assert out["spec"]["climate"] == climate and out["spec"]["horizon_end"] == horizon, out
        assert out["spec"]["levers"] == levers, out
        assert out["heard"], out
    else:
        assert out["spec"] is None


def test_out_of_range_split_is_a_problem_not_clamped():
    out = P.offline("What if we go to a 95/5 Finland–Sweden split?")
    assert out["door"] == "simulate" and out["spec"]["levers"] == []
    assert any("0.95" in p for p in out["problems"])


def test_unknown_lever_is_reported_never_invented():
    out = P.offline("What if we buy weather insurance for the Swedish peas?")
    assert out["door"] == "simulate" and out["spec"]["levers"] == []
    assert any("weather-index" in p for p in out["problems"]) and any("no lever" in p for p in out["problems"])


def test_base_spec_is_extended():
    base = {"climate": "ssp585", "horizon_end": 2060, "levers": [{"type": "region_split", "crop": "pea", "fi_share": 0.7}],
            "label": None}
    out = P.offline("and add a heat-tolerant pea from 2032", base=base)
    assert [l["type"] for l in out["spec"]["levers"]] == ["region_split", "heat_tolerant_variety"]
    assert out["spec"]["levers"][1]["from_year"] == 2032 and out["spec"]["climate"] == "ssp585"


def test_validates_against_the_contract():
    from api import schemas
    schemas.IntentOut.model_validate(P.parse("What if we irrigate the driest pea fields and move to a 70/30 Finland–Sweden split?"))
