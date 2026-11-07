import { useEffect, useRef } from "react";
import DeckGL from "@deck.gl/react";
import type { PickingInfo } from "@deck.gl/core";
import Map from "react-map-gl/maplibre";
import "maplibre-gl/dist/maplibre-gl.css";
import type { GeoParcel } from "../../api/types";
import { useStore } from "../../state/store";
import { useFieldData, type AlertPin } from "../fieldradar/useFieldData";
import { basemapStyle } from "./basemap";
import { parcelLayers } from "./layers/parcels";
import { alertPinLayers } from "./layers/pins";

const STYLE = basemapStyle();
const PIN_ZOOM = 12.5;

/** Satellite imagery with the contract parcels glowing on top, coloured by the active layer, plus the year's alert
 *  pins. Click a field to inspect it, or a pin to open its alert. */
export function MapView() {
  const { view, setView, selectedParcel, selectParcel, selectedAlert, selectAlert } = useStore();
  const d = useFieldData();
  const selectedAlertId = selectedAlert?.id ?? null;
  const layers = [
    ...parcelLayers(d.parcels, d.colorOf, selectedParcel?.parcel_id ?? null, d.trigger),
    ...alertPinLayers(d.pins, selectedAlertId),
  ];

  // An alert picked anywhere (timeline dot, list, pin) centres the map on its pin once that year's pins exist.
  const flownTo = useRef<string | null>(null);
  useEffect(() => {
    if (!selectedAlertId) { flownTo.current = null; return; }
    if (flownTo.current === selectedAlertId) return;
    const pin = d.pins.find((p) => p.alerts.some((a) => a.id === selectedAlertId));
    if (!pin) return;
    flownTo.current = selectedAlertId;
    setView({ longitude: pin.position[0], latitude: pin.position[1], zoom: Math.max(view.zoom, PIN_ZOOM), pitch: 0, bearing: 0 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedAlertId, d.pins]);

  const onClick = ({ object, layer }: PickingInfo) => {
    if (layer?.id === "alert-pins") {
      const pin = object as AlertPin;
      selectAlert(pin.alerts[0], { keepView: true });
      return;
    }
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
    </div>
  );
}
