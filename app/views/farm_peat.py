import streamlit as st

from app import data, ui

st.title("Farm & peat")
st.caption("The current calculator assumes mineral soil. Drained organic soils emit 29 t CO2/ha/yr under "
           "annual crops (pack METHODOLOGY §5).")

res = data.visible(data.results("metric = 'farm_tco2e'"), ui.show_drafts())
if res.empty:
    st.info("No farm footprint results yet.")
else:
    wide = res.pivot_table(index="category", columns="scenario", values="value", aggfunc="sum").fillna(0)
    if {"mineral_only", "with_organic_soils"} <= set(wide.columns):
        before, after = wide["mineral_only"].sum(), wide["with_organic_soils"].sum()
        c1, c2, c3 = st.columns(3)
        c1.metric("Calculator (mineral soil)", f"{before:,.0f} t CO2e")
        c2.metric("With organic soils", f"{after:,.0f} t CO2e", f"{after - before:+,.0f} t", delta_color="inverse")
        c3.metric("Farms affected", int((wide["with_organic_soils"] > wide["mineral_only"]).sum()))
        wide["extra"] = wide["with_organic_soils"] - wide["mineral_only"]
        st.bar_chart(wide[["mineral_only", "extra"]].sort_values("extra", ascending=False), stack=True)
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
