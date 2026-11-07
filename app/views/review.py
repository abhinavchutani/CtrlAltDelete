"""Review & publish: the human expert's page. Logic lives in app/review.py."""
import json

import streamlit as st

from app import data, review, ui

st.title("Review & publish")
st.caption("Agents only propose. Every decision here is signed with the reviewer's name and logged in `corrections`.")

name = st.text_input("Reviewer name (required, typed by you)", key="reviewer")
err = review.reviewer_error(name) if name else "enter your name to make decisions"
if err:
    st.info(f"Read-only: {err}.")
can_act = err is None
con = data.rw()

# ── 1. queue ──────────────────────────────────────────────────────────
q = review.queue(con)
st.subheader(f"1 · Review queue ({len(q)} proposed)")
types = st.multiselect("Issue type", sorted(q["issue_type"].unique()), key="rq_types")
view = q[q["issue_type"].isin(types)] if types else q
st.dataframe(view[["issue_id", "issue_type", "record_key", "confidence", "explanation", "triage", "proposed_fix"]],
             hide_index=True, use_container_width=True)

if len(view):
    iid = st.selectbox("Decide on", view["issue_id"], key="rq_pick")
    row = view.set_index("issue_id").loc[iid]
    fix = json.loads(row["proposed_fix"]) if row["proposed_fix"] else {}
    c1, c2 = st.columns(2)
    c1.markdown(f"**Rule** `{row['rule_id']}` · confidence {row['confidence']:.2f}\n\n{row['explanation']}")
    c1.json(json.loads(row["evidence"] or "{}"), expanded=False)
    if row["triage"]:
        c1.caption(f"LLM triage (advisory): **{row['triage']}**: {row['triage_note']}")
    c2.markdown(f"**Proposed fix:** `{fix.get('field')}`: `{fix.get('old_value')}` → `{fix.get('new_value')}`"
                if fix else "**No automatic fix**: route to an expert.")
    edited = c2.text_input("Edit new value (optional)", key="rq_edit")
    comment = c2.text_input("Comment", key="rq_comment")
    b1, b2 = c2.columns(2)
    if b1.button("Accept", key="rq_accept", disabled=not can_act or not fix, type="primary"):
        cid = review.accept(con, iid, name, comment, edited or None)
        st.success(f"Logged `{cid}`. Recalculate to update the numbers.")
        st.rerun()
    if b2.button("Reject", key="rq_reject", disabled=not can_act):
        review.reject(con, iid, name, comment)
        st.rerun()

bulk = review.bulk_candidates(q)
with st.expander(f"Bulk accept high-confidence rule hits ({len(bulk)}; soil misreports excluded)"):
    st.caption(f"Confidence ≥ {review.BULK_MIN_CONFIDENCE}. Each item is still logged as its own correction.")
    picked = st.multiselect("Issues", bulk["issue_id"], key="rq_bulk")
    if st.button("Accept selected", key="rq_bulk_go", disabled=not can_act or not picked):
        n = len(review.bulk_accept(con, picked, name))
        st.success(f"{n} corrections logged.")
        st.rerun()

# ── 2. recalculate ────────────────────────────────────────────────────
st.subheader("2 · Recalculate")
st.caption("Reruns the pipeline with the approved corrections. Changed results go back to draft.")
if st.button("Recalculate", key="recalc", disabled=not can_act):
    changed = review.recalculate(con, mock=data.is_mock())
    st.session_state["changed"] = changed
if "changed" in st.session_state:
    ch = st.session_state["changed"]
    st.write(f"{len(ch)} results changed.")
    st.dataframe(ch, hide_index=True, use_container_width=True)

# ── 3. publish ────────────────────────────────────────────────────────
st.subheader("3 · Publish")
st.caption("Only published results feed the submission CSVs, the dashboard and the copilot.")
res = data.results("metric = 'tco2e' AND status <> 'published'")
pub = st.multiselect("Results to publish", res["result_id"], key="pub_ids")
if st.button("Publish selected", key="pub_go", disabled=not can_act or not pub):
    review.publish(con, pub, name)
    st.success(f"Published {len(pub)} results.")
    st.rerun()
done = data.results("status = 'published'")
st.dataframe(ui.badges(done[["result_id", "value", "unit", "status"]]), hide_index=True, use_container_width=True)

# ── audit log ─────────────────────────────────────────────────────────
st.subheader("Audit log")
log = review.audit_log(con)
st.dataframe(log, hide_index=True, use_container_width=True)
st.download_button("Download corrections.csv", log.to_csv(index=False), "corrections.csv", key="audit_dl")
