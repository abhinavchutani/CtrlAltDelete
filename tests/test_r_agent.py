"""r_agent: the 5 demo questions answer offline with evidence, in the AskOut contract shape (V2-9 / #86)."""
import pytest

from api.schemas import AskOut
from src import r_docs, serve_db

DEMO = [
    "How did pea deliveries from Swedish farms in 2026 compare with 2021?",
    "Which farms reported peat but were calculated as mineral soil?",
    "Energy use per site per month in 2024 as a report",
    "What is the guarantee of origin rule?",
    "Show farm F0123's yield history",
]


def test_expand_links_abbreviations_to_full_terms():
    assert "guarantee origin" in r_docs.expand("how do we count GoO?")
    assert "goo" in r_docs.expand("What is the guarantee of origin rule?")
    assert r_docs.expand("pea deliveries 2026") == "pea deliveries 2026"


def test_not_in_data_is_contract_shaped():
    from src.r_agent import not_in_data
    out = AskOut.model_validate(not_in_data("nothing", ["raw_x"]))
    assert out.status == "not_in_data" and out.evidence == []


needs_snapshot = pytest.mark.skipif(not serve_db.exists(), reason="out/serve.duckdb missing (run make snapshot)")


@needs_snapshot
@pytest.mark.parametrize("q", DEMO)
def test_demo_questions_answer_with_evidence(q):
    from src.r_agent import ask
    out = AskOut.model_validate(ask(q))
    assert out.status == "answered", out.answer_md
    assert out.evidence


@needs_snapshot
def test_goo_rule_cites_our_stated_rule():
    from src.r_agent import ask
    refs = [e.ref for e in AskOut.model_validate(ask("What is the guarantee of origin rule?")).evidence]
    assert any("REASONING_LOG.md" in r and "R05" in r for r in refs)


@needs_snapshot
def test_unknown_question_is_not_in_data():
    from src.r_agent import ask
    assert ask("What colour is the Säkylä factory roof?")["status"] == "not_in_data"
