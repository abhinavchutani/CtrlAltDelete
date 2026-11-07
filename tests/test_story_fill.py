"""story_fill: every filled value has a source; unfilled ones say why. Data tests skip without the pack."""
import os
import re

import pytest

from src import a_clean, load, story_fill
from src import lineage as L
from src.db import connect


def test_fmt():
    assert story_fill.fmt(14356.06) == "14,356" and story_fill.fmt(91.317, 1) == "91.3"


@pytest.fixture(scope="module")
def con(tmp_path_factory):
    if not (load.pack_dir() / "data").is_dir():
        pytest.skip("data pack not available (set DATA_DIR)")
    os.environ["NAVIGATOR_DEV_ASSUME"] = "1"
    c = connect(tmp_path_factory.mktemp("db") / "t.duckdb")
    load.load_all(c)
    L.init_schema(c)
    a_clean.propose_and_assume(c)
    a_clean.build_clean(c)
    return c


def test_every_value_has_a_source_or_reason(con):
    vals = story_fill.compute_values(con)
    placeholders = set()
    for src in story_fill.SOURCES:
        placeholders |= set(re.findall(r"\{\{([A-Z0-9_]+)\}\}", (story_fill.REPO_ROOT / src).read_text()))
    assert placeholders <= set(vals), placeholders - set(vals)
    for name, x in vals.items():
        assert x["source"], name
        assert x["value"] is not None or x["pending"], name
    assert vals["A1_DEV_SCORE"]["value"] and vals["FLAG_SHARE_AFTER"]["value"]


def test_c2_values_are_signed_yield_changes(con):
    for cat, v in [("FI_SW:potato", -7.08), ("FI_SW:turnip_rape", -4.37), ("SE_SKANE:pea", 2.69)]:
        L.write_result(con, f"C2:ssp585:{cat}:yield_change_pct", metric="yield_change_pct", value=v, unit="%",
                       method="test", produced_by="test", category=cat, scenario="ssp585",
                       lineage=[L.src("doc", "test")])
    vals = story_fill.compute_values(con)
    assert [vals[k]["value"] for k in ("C2_POTATO_FI_585_PCT", "C2_RAPE_FI_585_PCT", "C2_PEA_SE_585_PCT")] == \
        ["-7.1", "-4.4", "+2.7"]
