"""r_knowledge + r_gaps: tacit knowledge with human review, and the missing-data chaser (#112)."""
import pytest
from pydantic import ValidationError

from src import r_knowledge as K
from src import serve_db


@pytest.fixture()
def store(tmp_path, monkeypatch):
    p = tmp_path / "knowledge.jsonl"
    monkeypatch.setattr(K, "STORE", p)
    return p


def _item(**kw):
    base = dict(statement="Old freezer line at Säkylä decommissioned March 2025", tags=["site:S-SAK"],
                linked_refs=["S-SAK"], contributed_by="Matti", role="energy manager")
    return K.KnowledgeIn(**(base | kw))


# ── no data needed ───────────────────────────────────────────────────
def test_new_items_start_pending_and_get_sequential_ids(store):
    a, b = K.add(_item()), K.add(_item(statement="Ask Liisa about Kantvik steam meters", type="contact"))
    assert (a.knowledge_id, a.status, b.knowledge_id) == ("K-0001", "pending_review", "K-0002")


def test_no_contributor_no_save(store):
    with pytest.raises(ValidationError):
        _item(contributed_by="")
    with pytest.raises(ValueError):
        K.add(K.KnowledgeIn.model_construct(**_item().model_dump() | {"contributed_by": "  "}))
    assert not store.exists()


def test_decision_needs_a_human_reviewer(store):
    k = K.add(_item())
    with pytest.raises(ValidationError):
        K.KnowledgeDecision(decision="approve", reviewer="")
    with pytest.raises(ValueError):
        K.decide(k.knowledge_id, K.KnowledgeDecision.model_construct(decision="approve", reviewer=" ", note=""))
    assert K.items()[0].status == "pending_review"


def test_approve_then_cite_with_contributor_and_reviewer(store):
    k = K.add(_item())
    line, ev = K.cite(k)
    assert line.startswith("According to Matti (energy manager) (unreviewed)")
    K.decide(k.knowledge_id, K.KnowledgeDecision(decision="approve", reviewer="Anna", note="checked"))
    line, ev = K.cite(K.items("approved")[0])
    assert "stated by Matti (energy manager), approved by Anna" in line and ev.ref == "knowledge:K-0001"


def test_rejected_items_never_come_back(store):
    k = K.add(_item())
    K.decide(k.knowledge_id, K.KnowledgeDecision(decision="reject", reviewer="Anna", note="wrong line"))
    assert K.for_entities(["S-SAK"]) == [] and K.items("rejected")[0].reviewer == "Anna"


def test_state_survives_a_restart(store):
    k = K.add(_item())
    K.decide(k.knowledge_id, K.KnowledgeDecision(decision="approve", reviewer="Anna"))
    assert [(x.knowledge_id, x.status) for x in K.items(path=store)] == [("K-0001", "approved")]   # replayed from disk


def test_unknown_id_is_none(store):
    assert K.decide("K-9999", K.KnowledgeDecision(decision="approve", reviewer="Anna")) is None


def test_links_match_ids_and_tags(store):
    K.add(_item(linked_refs=[], tags=["site:S-SAK", "domain:refrigerants"]))
    assert len(K.for_entities(["s-sak"])) == 1 and K.for_entities(["S-KAN"]) == []


# ── with the snapshot ────────────────────────────────────────────────
needs_snapshot = pytest.mark.skipif(not serve_db.exists(), reason="out/serve.duckdb missing (run make snapshot)")


@needs_snapshot
def test_conflict_check_flags_a_stop_statement_while_data_continues(store):
    from src import r_sql as S
    k = K.add(_item(valid_from="2025-03-01"), con=S.connect())
    assert k.conflicts and all("check before approving" in c.label for c in k.conflicts)


@needs_snapshot
def test_entity_answer_cites_approved_knowledge(store):
    from src.r_agent import ask
    k = K.add(_item())
    K.decide(k.knowledge_id, K.KnowledgeDecision(decision="approve", reviewer="Anna"))
    out = ask("everything about S-SAK")
    assert out["status"] == "answered" and "approved by Anna" in out["answer_md"]
    assert any(e["ref"] == "knowledge:K-0001" for e in out["evidence"])


@needs_snapshot
def test_gaps_have_owner_draft_and_evidence():
    from src import r_gaps as G
    from src import r_sql as S
    gs = G.gaps(S.connect(), 2025)["gaps"]
    assert gs and all(g["owner"] and g["record_key"] in g["draft_message"] and g["evidence"] for g in gs)
    assert not any(g["site_id"] == "S-BJU" for g in gs)          # Bjuv before Dec 2025 is a boundary, not a gap


@needs_snapshot
def test_missing_data_question_answers_with_drafts():
    from src.r_agent import ask
    out = ask("What data is missing for 2025?")
    assert out["status"] == "answered" and out["table"]["columns"][-1] == "draft_message"
