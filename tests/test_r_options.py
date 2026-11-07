"""r_options: the adaptation options KB loads into the contract and ranks as agreed (#87, V2-12). No data needed."""
from api.schemas import AdaptationOption, AskOut
from src import r_options as R


def test_every_row_validates_and_ids_are_unique():
    rows = R.load_kb()
    assert len(rows) == 20 and all(isinstance(o, AdaptationOption) for o in rows)
    assert len({o.option_id for o in rows}) == 20


def test_nobody_reviewed_yet():
    assert all(o.reviewed_by is None for o in R.load_kb())   # only a human fills reviewed_by


def test_engine_levers_on_the_five_rerunnable_options():
    levers = {o.option_id: o.lever.type for o in R.load_kb() if o.lever}
    assert levers == {"A01": "irrigate", "A04": "heat_tolerant_variety", "A06": "earlier_sowing",
                      "A07": "region_split", "A08": "crop_area"}


def test_heat_at_flowering_for_pea_lists_a04_and_a06_first():
    assert [o.option_id for o in R.options("H2", "pea")][:2] == ["A04", "A06"]


def test_hazard_specific_before_all_hazard():
    ids = [len(o.hazards) == 7 for o in R.options("H1", "potato")]
    assert ids == sorted(ids)            # all False first, then all True


def test_filters_by_crop():
    assert all("potato" in o.crops or "all" in o.crops for o in R.options(None, "potato"))
    assert "A13" not in [o.option_id for o in R.options(None, "pea")]   # IPM is for turnip rape


def test_lead_text():
    assert R.lead_text((1, 1)) == "1 yr" and R.lead_text((0, 0)) == "immediate" and R.lead_text((8, 12)) == "8–12 yrs"


def test_copilot_answer_comes_from_the_kb_with_sources():
    out = AskOut.model_validate(R.answer("What can we do about heat at flowering for peas?"))
    assert out.status == "answered" and out.table["rows"][0][0] == "A04"
    assert any(e.ref == "kb/adaptation_options.csv#A04" for e in out.evidence)


def test_non_options_question_is_left_to_other_routes():
    assert R.answer("How did pea deliveries change?") is None
