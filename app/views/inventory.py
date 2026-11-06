"""Inventory page. Reads Track A's naming (#44): totals = scope 'total', categories = summary rows under
their scope, biogenic = scope 'memo', line items = metric 'tco2e_line'."""
import streamlit as st

from app import data, ui

TOTALS = [("scope1_total", "Scope 1"), ("scope2_location_total", "Scope 2 (location)"),
          ("scope2_market_total", "Scope 2 (market)"), ("scope3_total", "Scope 3")]

years = data.q("SELECT DISTINCT year FROM results WHERE metric = 'tco2e' AND scope = 'total' ORDER BY year")["year"].tolist()
st.title("Inventory")
if not years:
    st.info("No inventory results yet.")
    st.stop()
year = st.segmented_control("Year", years, default=max(years)) or max(years)
summ = data.visible(data.results("metric = 'tco2e' AND year = ?", [year]), ui.show_drafts())
if summ.empty:
    st.info("No inventory results for this year (published only; toggle 'Show drafts' to see drafts).")
    st.stop()

tot = summ[summ["scope"] == "total"].set_index("category")["value"]
cols = st.columns(len(TOTALS))
for col, (cat, label) in zip(cols, TOTALS):
    col.metric(label, f"{tot[cat]:,.0f} t CO2e" if cat in tot else "—")
memo = summ[summ["scope"] == "memo"]
st.caption("Scope 2 location- and market-based are alternatives, not a sum."
           + (f" Biogenic CO2 (memo, not Scope 1): {memo['value'].sum():,.0f} t." if len(memo) else ""))

st.subheader("By category")
cats = summ[~summ["scope"].isin(["total", "memo"])]
st.dataframe(ui.badges(cats[["result_id", "scope", "category", "value", "unit", "status"]].round({"value": 1})),
             hide_index=True, use_container_width=True)

st.subheader("Trace a number")
st.caption("Category → its line items → source records, factors and corrections.")
pick = st.selectbox("Category", cats["result_id"],
                    format_func=lambda r: f"{cats.set_index('result_id').at[r, 'category']} "
                                          f"({cats.set_index('result_id').at[r, 'value']:,.0f} t)")
row = cats.set_index("result_id").loc[pick]
st.markdown(f"**{row['value']:,.0f} {row['unit']}** · {ui.BADGE.get(row['status'], row['status'])} · "
            f"method `{row['method']}` · produced by `{row['produced_by']}`")
lin = data.lineage(pick)
children = data.results("result_id IN (SELECT source_ref FROM lineage WHERE result_id = ?)", [pick])
if children.empty:
    leaf = pick
    st.dataframe(lin, hide_index=True, use_container_width=True)
else:
    st.dataframe(children[["result_id", "value", "unit", "method"]].sort_values("value", ascending=False),
                 hide_index=True, use_container_width=True)
    leaf = st.selectbox("Line item", children.sort_values("value", ascending=False)["result_id"])
    st.dataframe(data.lineage(leaf), hide_index=True, use_container_width=True)
keys = data.lineage(leaf).query("source_kind == 'record'")["source_ref"].tolist()
corr = data.corrections_for(keys)
st.markdown("**Corrections on these records**")
if corr.empty:
    st.caption("None.")
else:
    st.dataframe(corr, hide_index=True, use_container_width=True)
