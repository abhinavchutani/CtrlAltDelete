"""Cited solutions (kb/solutions.json, src.r_solutions): integrity, matching, and answers that only quote sources."""
from __future__ import annotations

import re

from src import r_solutions as R


def test_every_citation_points_at_a_source_with_a_url_and_a_quote():
    kb = R._kb()  # noqa: SLF001 - validates source ids on load
    assert kb["solutions"], "the solutions base is empty"
    for s in kb["solutions"]:
        assert s["evidence"], f"{s['id']} has no citation"
        assert set(s["hazards"]) <= {"H1", "H2"}, "only the hazards the twin shows (drought, heat at flowering)"
        for e in s["evidence"]:
            assert e["quote"].strip() and e["locator"].strip()
    for src in kb["sources"]:
        assert re.match(r"^https://", src["url"]) and src["kind"] in ("research", "guide")


def test_matcher_finds_solution_questions_only():
    assert R.match("What helps against drought at flowering in pea?") == ["H1"]
    assert R.match("what can we do about heat?") == ["H2"]
    assert R.match("How did Swedish pea deliveries in 2026 compare with 2021?") is None
    assert R.match("Where does the 2024 Scope 1 number come from?") is None


def test_problem_lists_model_levers_first_and_resolves_sources():
    sols = R.for_problem(["H1"], "pea")
    assert sols and all("H1" in s["hazards"] for s in sols)
    levers = [s["lever"] is not None for s in sols]
    assert levers == sorted(levers, reverse=True), "measures the model can run come first"
    assert all(e["url"] and e["publisher"] for s in sols for e in s["evidence"])
    assert all(s["reviewed"] is False for s in sols), "code never marks a measure reviewed"


def test_answer_is_built_from_the_base_with_evidence():
    a = R.answer("What would help with heat at flowering in pea?")
    assert a and a["status"] == "answered" and a["pending_approval"] is True
    assert {e["ref"].split("#")[0] for e in a["evidence"]} == {f"solutions:{s['id']}" for s in a["solutions"]}
    assert R.answer("How many farms are there?") is None
