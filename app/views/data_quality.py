import streamlit as st

from app import data

st.title("Data quality")
issues = data.q("SELECT * FROM issues")
real = issues[issues["issue_type"] != "observation"]

c1, c2, c3 = st.columns(3)
c1.metric("Issues found", len(real))
c2.metric("Awaiting review", int((real["status"] == "proposed").sum()))
c3.metric("Legitimate oddities (suppressed)", int((issues["status"] == "legitimate").sum()))

st.subheader("Issues by type")
st.bar_chart(real.groupby("issue_type").size().rename("issues"), horizontal=True)

st.subheader("Review queue")
st.caption("Decisions (accept / reject / edit) arrive in #21. Agents never approve.")
types = st.multiselect("Issue type", sorted(real["issue_type"].unique()))
queue = real[real["status"] == "proposed"]
if types:
    queue = queue[queue["issue_type"].isin(types)]
st.dataframe(queue[["issue_id", "issue_type", "record_key", "confidence", "explanation", "evidence", "proposed_fix"]]
             .sort_values("confidence", ascending=False), hide_index=True, use_container_width=True)

st.subheader("Checked, legitimate")
st.caption("Credit notes, tonne lots, seasonal peaks and ammonia systems are not errors (REASONING_LOG R01–R04).")
st.dataframe(issues[issues["status"] == "legitimate"][["table_name", "record_key", "explanation"]],
             hide_index=True, use_container_width=True)
