"""r_entity + catalog facets: entity view and lineage trace inside AskOut, faceted tags (#111)."""
import pytest

from api.schemas import AskOut
from src import r_catalog as C
from src import r_entity as E
from src import serve_db


# ── no data needed ───────────────────────────────────────────────────
@pytest.mark.parametrize("eid,kind", [("S-SAK", "site"), ("SUP073", "supplier"), ("M110", "material"),
                                      ("F0123", "farm"), ("F0123-P01", "parcel"), ("CA28", "catchment"),
                                      ("S0381", "farm"), ("EF-RAP-EE", "emission factor")])
def test_classify_ids(eid, kind):
    assert E.classify(eid)[0] == kind


def test_unknown_id_is_none():
    assert E.classify("hello") is None


def test_facets_are_controlled_values():
    f = C.facets("raw_refrigerant_service_log", ["record_key", "site_id", "year"], [2023, 2024])
    assert f == {"domain": ["refrigerants"], "entity": ["site"], "time": ["year:2023", "year:2024"],
                 "ghg": ["scope:1"], "owner": ["owner:site-maintenance"]}
    assert C.facets("raw_foodhills_odlingsdata_se", ["odlar_id"], None)["geo"] == ["SE", "SE_SKANE"]


def test_facet_filter_keeps_only_matching_cards():
    cards = [{"table": "raw_energy_meter_readings", "columns": [{"name": "site_id"}], "facets": {"domain": ["energy"]}},
             {"table": "raw_waste_transfer_notes", "columns": [{"name": "site_id"}], "facets": {"domain": ["waste"]}}]
    hits = C.catalog_search("site", cards=cards, facet={"domain": "energy"})["tables"]
    assert [h["table"] for h in hits] == ["raw_energy_meter_readings"]


# ── with the snapshot ────────────────────────────────────────────────
needs_snapshot = pytest.mark.skipif(not serve_db.exists(), reason="out/serve.duckdb missing (run make snapshot)")


@needs_snapshot
def test_everything_about_a_site_answers_with_evidence_and_separates_legitimate_cases():
    from src.r_agent import ask
    out = AskOut.model_validate(ask("Show me everything about S-SAK"))
    assert out.status == "answered" and out.evidence and out.table["rows"]
    assert "raw_energy_meter_readings" in [r[0] for r in out.table["rows"]]
    assert "ammonia" in out.answer_md            # the allow-listed ammonia systems are reported as not errors


@needs_snapshot
def test_supplier_with_digits_in_its_name_passes_the_number_check():
    from src.r_agent import ask
    assert ask("Tell me about SUP073")["status"] == "answered"


@needs_snapshot
def test_lineage_trace_matches_the_reported_total():
    from src.r_agent import ask
    trace = AskOut.model_validate(ask("Where does the 2024 Scope 1 number come from?"))
    total = ask("What were total Scope 1 emissions in 2024?")
    assert trace.status == "answered" and any(e.kind == "lineage" for e in trace.evidence)
    assert "6,399.9" in trace.answer_md and "6,399.9" in total["answer_md"]   # same number both ways


@needs_snapshot
def test_yield_history_still_wins_for_a_farm_yield_question():
    from src.r_agent import ask
    assert ask("Show farm F0123's yield history")["table"]["columns"][0] == "year"
