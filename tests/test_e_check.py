"""The number post-check: a number in an answer must equal a tool-returned number."""
from src.e_check import EVIDENCE_MARK, numbers_in, tool_numbers, unsupported_numbers

TOOL = [{"rows": [{"value": 6399.94, "unit": "t CO2e"}], "sum": 6399.94}]


def test_parses_thousands_separators_and_decimals():
    assert [(v, d) for _, v, d in numbers_in("6,399.9 t and 172 085 t and 4.2 %")] == [(6399.9, 1), (172085.0, 0), (4.2, 1)]


def test_ignores_numbers_glued_to_words_codes_and_evidence():
    text = "R717 under SSP2-4.5 in tCO2e, see `erp:0042:3`.\n\n" + EVIDENCE_MARK + "\n- result 999999"
    assert numbers_in(text) == []


def test_rounded_tool_number_passes():
    for ok in ["6,399.9 t CO2e", "6,400 t CO2e", "6399.94 t", "about 6 400 t"]:
        assert unsupported_numbers(ok, TOOL) == [], ok


def test_invented_or_computed_number_is_blocked():
    assert unsupported_numbers("6,500 t CO2e", TOOL) == ["6,500"]
    assert unsupported_numbers("6,399.94 t, which is 3.7 % of the total", TOOL) == ["3.7"]


def test_small_integers_and_question_numbers_are_allowed():
    assert unsupported_numbers("Scope 1 in 2024, step 3", TOOL) == ["2024"]
    assert unsupported_numbers("Scope 1 in 2024", TOOL, question="What were Scope 1 emissions in 2024?") == []


def test_numbers_inside_returned_passages_count():
    passages = [{"passages": [{"text": "Scope 1+2: at least 4.2 % per year linear"}]}]
    assert tool_numbers(passages) >= {4.2}
    assert unsupported_numbers("The minimum is 4.2 % per year.", passages) == []
