"""Farm & peat. Reads Track A's peat reveal (#48): metric 'farm_tco2e', category = farm_id (one row per farm ×
crop) or 'all_farms' (the total), scenario 'mineral_only' vs 'with_organic_soils'."""
import streamlit as st

from app import data, ui

SCEN = ("mineral_only", "with_organic_soils")

st.title("Farm & peat")
st.caption("The current calculator assumes mineral soil. Drained organic soils emit 29 t CO2/ha/yr under "
           "annual crops (pack METHODOLOGY §5).")

res = data.visible(data.results("metric = 'farm_tco2e'"), ui.show_drafts())
res = res[res["scenario"].isin(SCEN)]
if res.empty:
    st.info("No farm footprint results yet (run `make a`).")
else:
    year = int(res["year"].max())
    res = res[res["year"] == year]
    farms = res[res["category"] != "all_farms"]            # the total row is not a farm
    wide = farms.pivot_table(index="category", columns="scenario", values="value", aggfunc="sum").fillna(0)
    tot = res[res["category"] == "all_farms"].set_index("scenario")["value"]
    before = float(tot.get("mineral_only", wide.get("mineral_only", 0).sum()))
    after = float(tot.get("with_organic_soils", wide.get("with_organic_soils", 0).sum()))
    if set(SCEN) <= set(wide.columns):
        wide["peat_add_on"] = wide["with_organic_soils"] - wide["mineral_only"]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric(f"Calculator, mineral soil ({year})", f"{before:,.0f} t CO2e")
        c2.metric("With drained organic soils", f"{after:,.0f} t CO2e", f"{after - before:+,.0f} t", delta_color="inverse")
        c3.metric("Share from peat", f"{(after - before) / after:.0%}" if after else "—")
        c4.metric("Farms with peat emissions", int((wide["peat_add_on"] > 0.5).sum()))
        top = wide.sort_values("peat_add_on", ascending=False).head(15)
        share10 = top["peat_add_on"].head(10).sum() / max(wide["peat_add_on"].sum(), 1e-9)
        st.subheader("Where the peat is")
        st.caption(f"The top 10 farms carry {share10:.0%} of the peat add-on: verify their soil type before the "
                   "SBTi base year is fixed.")
        st.bar_chart(top[["mineral_only", "peat_add_on"]], stack=True, horizontal=True)
        st.dataframe(top.round(1), use_container_width=True)
    with st.expander("All farm rows"):
        st.dataframe(ui.badges(res[["result_id", "category", "scenario", "value", "unit", "status"]]),
                     hide_index=True, use_container_width=True)

st.subheader("Parcel map (soil map class)")
parcels = data.raw_parcels()
if parcels.empty:
    st.caption("Run `make load` to show the pack's parcels.")
else:
    soil = st.multiselect("Soil class", sorted(parcels["soil_class_soilmap"].dropna().unique()), default=["organic"])
    shown = parcels[parcels["soil_class_soilmap"].isin(soil)] if soil else parcels
    st.map(shown.rename(columns={"lat": "latitude", "lon": "longitude"}), size=60)
    st.caption(f"{len(shown):,} of {len(parcels):,} parcels. The soil map is ~88 % accurate.")
