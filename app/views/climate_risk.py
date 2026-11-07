"""Climate risk. C1 (#52): backtest, 2027–31 production, per-feature effects. C2/C3 (#18/#19): SSP risk + €."""
import streamlit as st

from app import data, ui

st.title("Climate risk")
draft = ui.show_drafts()

# ── C1: does the model see weather? ───────────────────────────────────
bt = data.visible(data.results("scenario = 'backtest'"), draft)
if not bt.empty:
    st.subheader("Yield model backtest: trained up to 2023, tested on 2024–26")
    head = bt[bt["category"] == "all"].set_index("metric")["value"]
    c1, c2 = st.columns(2)
    if "production_mape_pct" in head:
        c1.metric("Production error (MAPE, region × crop × year)", f"{head['production_mape_pct']:.1f} %")
    if "farm_nrmse" in head:
        c2.metric("Farm-level nRMSE", f"{head['farm_nrmse']:.3f}")
    cells = bt[bt["metric"].isin(["production_t_actual", "production_t", "ape_pct"])]
    if not cells.empty:
        wide = cells.pivot_table(index=["category", "year"], columns="metric", values="value").reset_index()
        wide = wide.rename(columns={"category": "region:crop", "production_t_actual": "actual t",
                                    "production_t": "predicted t", "ape_pct": "error %"}).round(1)
        st.dataframe(wide, hide_index=True, use_container_width=True)
        st.caption("2026 is the hard test: a strong Finnish pea year and a drought-hit Swedish one. "
                   "(2025 was a normal year in the twin.)")

eff = data.visible(data.results("metric = 'feature_effect_pct'"), draft)
if not eff.empty:
    st.subheader("What drives yield (per-feature effects)")
    eff = eff.assign(crop=eff["category"].str.split(":").str[0], feature=eff["category"].str.split(":", n=1).str[1])
    crops = sorted(eff["crop"].unique())
    crop = st.selectbox("Crop", crops, index=crops.index("pea") if "pea" in crops else 0, key="eff_crop")
    top = eff[eff["crop"] == crop].reindex(eff[eff["crop"] == crop]["value"].abs().sort_values(ascending=False).index).head(12)
    st.bar_chart(top.set_index("feature")["value"], horizontal=True)
    st.caption("% change in yield per one unit of the feature. Drought indices run 0–1 (−28 % per unit ≈ −2.8 % per "
               "+0.1); hot days are per day; interactions (\"irr_x_…\") are the extra effect when irrigated.")

c1p = data.visible(data.results("metric = 'production_t' AND scenario = 'ssp245' AND year BETWEEN 2027 AND 2031"), draft)
if not c1p.empty:
    st.subheader("Expected production 2027–31 (one SSP2-4.5 weather realisation)")
    st.line_chart(c1p.pivot_table(index="year", columns="category", values="value"))

# ── C2 / C3: future risk and € ────────────────────────────────────────
res = data.visible(data.results("scenario LIKE 'ssp%' AND metric IN ('yield_change_pct','p_bad_year','eur_at_risk','eur_saved')"), draft)
st.subheader("2041–60 risk by scenario")
if res.empty:
    st.info("C2 / C3 results not written yet (#18, #19).")
    st.stop()
st.caption("2041–60 vs 1991–2020, 2025 parcel mix and current management held fixed.")
ssps = sorted(res["scenario"].unique())
ssp = st.select_slider("Scenario", options=ssps, value="ssp245" if "ssp245" in ssps else ssps[0])
cur = res[res["scenario"] == ssp]
wide = cur[cur["metric"] != "eur_saved"].pivot_table(index="category", columns="metric", values="value")
m1, m2 = st.columns(2)
if "eur_at_risk" in wide:
    m1.metric("€ at risk per year", f"€{wide['eur_at_risk'].sum():,.0f}")
if "p_bad_year" in wide:
    m2.metric("Worst bad-year odds", f"{wide['p_bad_year'].max():.0%}", help="P(yield < 80 % of 1991–2020 mean)")
st.dataframe(wide.rename(columns={"yield_change_pct": "yield change %", "p_bad_year": "P(bad year)",
                                  "eur_at_risk": "€ at risk / yr"}), use_container_width=True)
if "yield_change_pct" in wide:
    st.bar_chart(wide["yield_change_pct"], horizontal=True)
adapt = cur[cur["metric"] == "eur_saved"]
st.subheader("Adaptation options")
if adapt.empty:
    st.caption("None for this scenario yet.")
else:
    st.dataframe(ui.badges(adapt[["category", "value", "unit", "status"]].rename(columns={"category": "action | owner"})),
                 hide_index=True, use_container_width=True)
