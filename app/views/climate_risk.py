import streamlit as st

from app import data, ui

st.title("Climate risk")
st.caption("2041–60 vs 1991–2020, 2025 parcel mix and current management held fixed.")

res = data.visible(data.results("scenario LIKE 'ssp%'"), ui.show_drafts())
if res.empty:
    st.info("No climate results yet.")
    st.stop()

ssps = sorted(res["scenario"].unique())
ssp = st.select_slider("Scenario", options=ssps, value="ssp245" if "ssp245" in ssps else ssps[0])
cur = res[res["scenario"] == ssp]
risk = cur[cur["metric"].isin(["yield_change_pct", "p_bad_year", "eur_at_risk"])]
wide = risk.pivot_table(index="category", columns="metric", values="value")

c1, c2 = st.columns(2)
if "eur_at_risk" in wide:
    c1.metric("€ at risk per year", f"€{wide['eur_at_risk'].sum():,.0f}")
if "p_bad_year" in wide:
    c2.metric("Worst bad-year odds", f"{wide['p_bad_year'].max():.0%}", help="P(yield < 80 % of 1991–2020 mean)")

st.subheader("By region × crop")
st.dataframe(wide.rename(columns={"yield_change_pct": "yield change %", "p_bad_year": "P(bad year)",
                                  "eur_at_risk": "€ at risk / yr"}), use_container_width=True)
if "yield_change_pct" in wide:
    st.bar_chart(wide["yield_change_pct"], horizontal=True)

st.subheader("Adaptation options")
adapt = cur[cur["metric"] == "eur_saved"]
if adapt.empty:
    st.caption("None for this scenario yet.")
else:
    st.dataframe(ui.badges(adapt[["category", "value", "unit", "status"]].rename(columns={"category": "action | owner"})),
                 hide_index=True, use_container_width=True)
