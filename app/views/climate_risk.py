"""Climate risk. C1 (#52): backtest, 2027–31 production, per-feature effects. C2/C3 (#18/#19): SSP risk + €."""
import pandas as pd
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
    st.line_chart(c1p.assign(year=c1p["year"].astype(int).astype(str)).pivot_table(index="year", columns="category", values="value"))

# ── C2 / C3: future risk and € ────────────────────────────────────────
c23 = data.visible(data.results("scenario IN ('baseline','ssp126','ssp245','ssp585') AND metric IN "
                                "('yield_change_pct','p_bad_year','eur_at_risk','eur_at_risk_p90','shortfall_t',"
                                "'import_tco2e','eur_saved','tco2e_avoided')"), draft)
st.subheader("2041–60 risk by scenario")
if c23.empty:
    st.info("C2 / C3 results not written yet (#18, #19).")
    st.stop()
st.caption("2041–60 vs 1991–2020, 2025 parcel mix and current management held fixed (ensemble of 30 weather-years).")
ssps = sorted(s for s in c23["scenario"].unique() if s.startswith("ssp"))
ssp = st.select_slider("Scenario", options=ssps, value="ssp245" if "ssp245" in ssps else ssps[0])


def table(scen: str, metrics: list[str]) -> pd.DataFrame:
    cur = c23[(c23["scenario"] == scen) & c23["metric"].isin(metrics)]
    return cur.pivot_table(index="category", columns="metric", values="value")


risk, base = table(ssp, ["yield_change_pct", "p_bad_year", "eur_at_risk", "eur_at_risk_p90", "shortfall_t",
                         "import_tco2e"]), table("baseline", ["eur_at_risk", "p_bad_year"])
if "eur_at_risk" in risk:
    tot, tot0 = risk["eur_at_risk"].sum(), base["eur_at_risk"].sum() if "eur_at_risk" in base else None
    m1, m2, m3 = st.columns(3)
    m1.metric("Expected € at risk per year", f"€{tot:,.0f}",
              f"{tot - tot0:+,.0f} vs 1991–2020" if tot0 else None, delta_color="inverse")
    if "import_tco2e" in risk:
        m2.metric("Replacement-import emissions", f"{risk['import_tco2e'].sum():,.0f} t CO2e/yr")
    if "shortfall_t" in risk:
        m3.metric("Expected shortfall", f"{risk['shortfall_t'].sum():,.0f} t/yr")
    st.caption("€ at risk = shortfall × 2025 contract price × replacement-import premium (pack method). "
               "1-in-10-year losses are per crop; they don't add up across crops.")
    if len(base):
        st.bar_chart(pd.DataFrame({"1991–2020": base.get("eur_at_risk"), ssp: risk["eur_at_risk"]}), stack=False)
show = risk.rename(columns={"yield_change_pct": "yield change %", "p_bad_year": "P(bad year)",
                            "eur_at_risk": "€ at risk / yr", "eur_at_risk_p90": "€ 1-in-10 yr",
                            "shortfall_t": "shortfall t/yr", "import_tco2e": "import t CO2e/yr"})
st.dataframe(show.round(2), use_container_width=True)

st.subheader("What Apetit can do")
act = c23[(c23["scenario"] == ssp) & c23["metric"].isin(["eur_saved", "tco2e_avoided"])]
if act.empty:
    st.caption("No adaptation results for this scenario yet.")
else:
    a = act.pivot_table(index="category", columns="metric", values="value").reset_index()
    a[["action", "owner"]] = a["category"].str.split(r" \| owner: ", n=1, expand=True)
    a = a.rename(columns={"eur_saved": "€ avoided / yr (gross)", "tco2e_avoided": "t CO2e avoided / yr"})
    a["action"] = a["action"].str.replace("_", " ")
    st.dataframe(a[["action", "owner", "€ avoided / yr (gross)", "t CO2e avoided / yr"]]
                 .sort_values("€ avoided / yr (gross)", ascending=False).round(0), hide_index=True, use_container_width=True)
    st.caption("Gross values: the actions' own costs (irrigation capex/opex, water) are not netted off.")

obs = data.score_file("C3_euro_risk.json").get("observed_2026")
if obs:
    st.subheader("The 2026 hedge, observed")
    h1, h2, h3 = st.columns(3)
    h1.metric("Finland pea yield vs mean", f"{obs['FI_SW_2026_vs_mean_pct']:+.1f} %")
    h2.metric("Sweden pea yield vs mean", f"{obs['SE_SKANE_2026_vs_mean_pct']:+.1f} %")
    h3.metric("Two-region pool", f"{obs['pooled_FI_SE_2026_vs_mean_pct']:+.1f} %")
    st.caption(f"Weighted by contracted volume (FI {obs['contracted_share_FI_pct']:.0f} %). "
               "Source: out/scores/C3_euro_risk.json (make c).")
