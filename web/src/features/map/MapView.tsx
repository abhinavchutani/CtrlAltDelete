import DeckGL from "@deck.gl/react";
import type { PickingInfo } from "@deck.gl/core";
import Map from "react-map-gl/maplibre";
import "maplibre-gl/dist/maplibre-gl.css";
import type { GeoParcel } from "../../api/types";
import { useStore } from "../../state/store";
import { useFieldData } from "../fieldradar/useFieldData";
import { basemapStyle } from "./basemap";
import { parcelLayers } from "./layers/parcels";
import { RadarOverlay } from "./RadarOverlay";

const STYLE = basemapStyle();

/** Satellite imagery with the contract parcels glowing on top, coloured by the active layer. Click a field to inspect it. */
export function MapView() {
  const { view, setView, selectedParcel, selectParcel } = useStore();
  const d = useFieldData();
  const layers = parcelLayers(d.parcels, d.colorOf, selectedParcel?.parcel_id ?? null, d.trigger);
  const onClick = ({ object }: PickingInfo) => {
    const p = object as GeoParcel | undefined;
    selectParcel(p ? { ...p.properties, ring: p.geometry.coordinates[0] } : null);
  };
  return (
    <div className="map-canvas">
      <DeckGL
        viewState={view}
        onViewStateChange={({ viewState }) => setView(viewState as typeof view)}
        controller={{ dragRotate: false }}
        layers={layers}
        onClick={onClick}
        getCursor={({ isHovering }) => (isHovering ? "pointer" : "grab")}
      >
        <Map mapStyle={STYLE} />
      </DeckGL>
      <RadarOverlay />
    </div>
  );
}
