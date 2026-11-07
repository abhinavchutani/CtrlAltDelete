"""Deterministic resolvers (#59): one test per phrase rule, on fixture rows shaped like Track A's results."""
import pytest

from src import e_agent, e_check, e_llm, e_resolve
from src import lineage as L
from src.db import connect

LINES = {  # Track A line-item ids (#44 naming), fixture values
    "scope1:stationary_and_mobile_combustion:S-SAK:lng": 1500.0,
    "scope1:stationary_and_mobile_combustion:S-SAK:lpg": 600.0,
    "scope1:stationary_and_mobile_combustion:S-SAK:biogas": 0.0,
    "scope1:fugitive_refrigerants:S-SAK:R404A": 700.0,
    "scope1:fugitive_refrigerants:S-KAN:R134a": 27.0,
    "scope2_location:purchased_electricity:S-KAN": 325.0,
    "scope3:cat04_upstream_transport:inbound:EF-TKM-SHIP-BULK": 570.0,
    "scope3:cat04_upstream_transport:inbound:EF-TKM-SHIP-REEFER": 220.0,
    "scope3:cat04_upstream_transport:inbound:EF-TKM-TRUCK": 2300.0,
}


@pytest.fixture
def con(tmp_path, monkeypatch):
    monkeypatch.setenv("NAVIGATOR_DEV_ASSUME", "1")
    monkeypatch.setattr(e_llm, "available", lambda: False)
    c = connect(tmp_path / "r.duckdb")
    L.init_schema(c)
    c.execute("CREATE TABLE raw_sites AS SELECT * FROM (VALUES ('S-SAK', 'Säkylä plant'), ('S-KAN', 'Kantvik oilseed mill'), "
              "('S-HQ', 'Helsinki head office')) t(site_id, name)")
    for rid, v in LINES.items():
        scope, cat = rid.split(":")[:2]
        L.write_result(c, f"A2:2025:actual:{rid}", metric="tco2e_line", value=v, unit="t CO2e", scope=scope,
                       category=cat, year=2025, method="fixture", produced_by="test", lineage=[L.src("record", f"x:{rid}")])
    for cat, v in [("scope1_total", 4400.0), ("scope2_market_total", 60.0)]:
        L.write_result(c, f"A2:2025:actual:total:{cat}", metric="tco2e", value=v, unit="t CO2e", scope="total",
                       category=cat, year=2025, method="fixture", produced_by="test", lineage=[L.src("doc", "x")])
    L.write_result(c, "PEAT:2025:extra_from_peat", metric="tco2e", value=1000.0, unit="t CO2e", scope="3",
                   category="peat_reveal", year=2025, scenario="with_organic_soils", method="fixture", produced_by="test",
                   lineage=[L.src("doc", "x")])
    L.write_result(c, "PEAT:2025:with_organic_soils:all_farms", metric="farm_tco2e", value=4000.0, unit="t CO2e",
                   scope="3", category="all_farms", year=2025, scenario="with_organic_soils", method="fixture",
                   produced_by="test", lineage=[L.src("doc", "x")])
    return c


def _ask(con, q):
    a = e_agent.answer(q, kind="numeric", con=con)
    assert not a.blocked, a.markdown
    return a


@pytest.mark.parametrize("q,expected", [
    ("What were Scope 1 emissions from LNG and LPG combustion at the Säkylä plant in 2025 (tCO2e)?", 2100.0),
    ("What were refrigerant (fugitive) emissions at the Säkylä plant in 2025 (tCO2e)?", 700.0),
    ("What were location-based Scope 2 emissions of the Kantvik site in 2025 (tCO2e)?", 325.0),
    ("What were 2025 category 4 emissions from the sea legs of inbound shipments (bulk and reefer vessels), in tCO2e?", 790.0),
    ("What share (%) of 2025 Finnish contract-farm cradle-to-gate emissions comes from drained organic soils?", 25.0),
    ("Illustrative: with 2025 as base year and the SBTi minimum 4.2 %/yr linear rate for Scope 1+2, what is a 2032 "
     "absolute Scope 1+2 (market-based) target in tCO2e?", 4460.0 * (1 - 0.042 * 7)),
    ("What were market-based Scope 2 emissions in 2025 after reconciling the internal GoO log with the registry "
     "statement (tCO2e)?", 60.0),
])
def test_rules_answer_from_results(con, q, expected):
    a = _ask(con, q)
    assert a.value == pytest.approx(expected) and a.evidence


def test_derived_numbers_show_their_formula(con):
    a = _ask(con, "What share (%) of 2025 Finnish contract-farm cradle-to-gate emissions comes from drained organic soils?")
    assert any(e.startswith("derived in code:") for e in a.evidence)


@pytest.mark.parametrize("q", [
    "What was biogenic CO2 from combustion at the Kantvik site in 2025 (t)?",            # no rule: memo is group-only
    "What were Scope 1 emissions from diesel at the Säkylä plant in 2025 (tCO2e)?",      # carrier not in the lines
    "What were Scope 1 emissions at the Säkylä and Kantvik plants in 2025 (tCO2e)?",     # two sites: ambiguous
    "Illustrative: with 2025 as base year and the SBTi FLAG minimum 3.03 %/yr linear rate, what is a 2032 FLAG target?",
])
def test_ambiguous_or_unsupported_questions_stay_unanswered(con, q):
    assert e_resolve.resolve(con, q) is None
    assert e_agent.answer(q, kind="numeric", con=con).value is None


def test_method_clause_stripping():
    assert e_resolve.strip_method_clause("What were X emissions in 2025 after reconciling A with B (tCO2e)?") == \
        "What were X emissions in 2025 (tCO2e)?"
