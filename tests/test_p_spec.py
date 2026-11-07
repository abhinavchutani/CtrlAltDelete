"""p_spec: lever bounds and problems (no data needed)."""
from src import p_spec as S


def test_eur_bands():
    assert [S.eur_band(x) for x in (0, 49_999, 50_000, 120_000, 300_000, 2e6)] == \
        ["< €50k", "< €50k", "€50–100k", "€100–250k", "€250k–1M", "> €1M"]


def test_validate_keeps_good_levers_and_reports_bad_ones_without_fixing():
    spec, problems = S.validate({"climate": "ssp585", "horizon_end": 2050, "levers": [
        {"type": "region_split", "fi_share": 0.7},
        {"type": "region_split", "fi_share": 0.95},          # out of range → problem, dropped
        {"type": "teleport", "crop": "pea"},                 # unknown lever → problem
        {"type": "heat_tolerant_variety"}]})                 # defaults (from_year 2030, cut 0.3)
    assert spec["climate"] == "ssp585" and spec["horizon_end"] == 2050
    assert [l["type"] for l in spec["levers"]] == ["region_split", "heat_tolerant_variety"]
    assert spec["levers"][1] == {"type": "heat_tolerant_variety", "crop": "pea", "from_year": 2030, "penalty_cut": 0.3}
    assert any("0.95" in p for p in problems) and any("teleport" in p for p in problems)


def test_bad_climate_is_reported_and_default_kept():
    spec, problems = S.validate({"climate": "ssp999"})
    assert spec["climate"] == "ssp245" and problems


def test_scenario_id_is_stable_and_label_free():
    a, _ = S.validate({"levers": [{"type": "irrigate", "crop": "pea"}], "label": "x"})
    b, _ = S.validate({"levers": [{"type": "irrigate", "crop": "pea"}], "label": "y"})
    assert S.scenario_id(a) == S.scenario_id(b) and S.scenario_id(a).startswith("s_")
