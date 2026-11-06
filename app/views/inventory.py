import streamlit as st

from app import data, ui

st.title("Inventory 2025")
res = data.visible(data.results("metric = 'tco2e' AND year = 2025"), ui.show_drafts())
if res.empty:
    st.info("No inventory results yet (published only; toggle 'Show drafts' to see drafts).")
    st.stop()

scope_tot = res.groupby("scope")["value"].sum()
cols = st.columns(len(scope_tot))
for col, (scope, v) in zip(cols, scope_tot.items()):
    col.metric(f"Scope {scope.replace('_', ' ')}", f"{v:,.0f} t CO2e")
st.caption("Scope 2 is shown location- and market-based; they are alternatives, not a sum.")

st.subheader("Lines")
st.dataframe(ui.badges(res[["result_id", "scope", "category", "value", "unit", "status", "method"]]),
             hide_index=True, use_container_width=True)

st.subheader("Trace a number")
rid = st.selectbox("Result", res["result_id"], format_func=lambda r: f"{r}  ({res.set_index('result_id').at[r, 'value']:,.0f} t)")
row = res.set_index("result_id").loc[rid]
st.markdown(f"**{row['value']:,.0f} {row['unit']}** · {ui.BADGE.get(row['status'], row['status'])} · "
            f"method `{row['method']}` · produced by `{row['produced_by']}`")
lin = data.lineage(rid)
st.dataframe(lin, hide_index=True, use_container_width=True)
keys = lin.loc[lin["source_kind"] == "record", "source_ref"].tolist()
corr = data.corrections_for(keys)
st.markdown("**Corrections on these records**")
if corr.empty:
    st.caption("None.")
else:
    st.dataframe(corr, hide_index=True, use_container_width=True)
