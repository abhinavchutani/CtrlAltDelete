import { useEffect, useRef } from "react";
import type { PickingInfo } from "@deck.gl/core";
import { MapboxOverlay, type MapboxOverlayProps } from "@deck.gl/mapbox";
import Map, { AttributionControl, useControl, type IControl, type MapRef } from "react-map-gl/maplibre";
import "maplibre-gl/dist/maplibre-gl.css";
import type { GeoParcel } from "../../api/types";
import { HOME_VIEW, useStore } from "../../state/store";
import { PinCard } from "../alerts/PinCard";
import { ParcelCard } from "../fieldradar/ParcelCard";
import { useFieldData, type AlertPin } from "../fieldradar/useFieldData";
import { basemapStyle } from "./basemap";
import { fieldLayers } from "./layers/parcels";
import { alertPinLayers } from "./layers/pins";
import { cardClickedJustNow } from "./isolate";
import { WeatherFx } from "./WeatherFx";

const STYLE = basemapStyle();
const PIN_ZOOM = 12.5;
const CARD_ROOM: [number, number] = [-200, 0]; // land the pin left of centre so its card fits on the right

/** deck.gl drawn inside MapLibre's own WebGL context ("interleaved"): fields and imagery render in the same frame,
 *  so the fields never trail the map while panning. */
function DeckOverlay(props: MapboxOverlayProps) {
  // MapboxOverlay implements MapLibre's IControl; the two packages' typings just don't line up
  const overlay = useControl(() => new MapboxOverlay(props) as unknown as IControl) as unknown as MapboxOverlay;
  overlay.setProps(props);
  return null;
}

/** Satellite imagery with the farms glowing on top (coloured by the chosen layer), their fields, and the year's
 *  alert pins. Click a field to inspect it, or a pin to open its alert. MapLibre owns the camera. */
export function MapView() {
  const mapRef = useRef<MapRef>(null);
  const camera = useStore((s) => s.camera);
  const selectedParcel = useStore((s) => s.selectedParcel);
  const selectParcel = useStore((s) => s.selectParcel);
  const selectedAlert = useStore((s) => s.selectedAlert);
  const selectAlert = useStore((s) => s.selectAlert);
  const setViewRegion = useStore((s) => s.setViewRegion);
  const d = useFieldData();
  const selectedAlertId = selectedAlert?.id ?? null;
  const selectedPin = selectedAlertId ? d.pins.find((p) => p.alerts.some((a) => a.id === selectedAlertId)) : undefined;
  const layers = [
    ...fieldLayers(d.parcels, d.zones, d.farmColor, selectedParcel?.parcel_id ?? null, d.trigger),
    ...alertPinLayers(d.pins, selectedAlertId),
  ];

  // fly-to requests from the panels (region chips, alerts)
  useEffect(() => {
    if (camera.seq === 0) return;
    const { longitude, latitude, zoom } = camera.target;
    mapRef.current?.flyTo({ center: [longitude, latitude], zoom, duration: 1400, essential: true });
  }, [camera]);

  // an alert picked anywhere centres the map on its pin once that year's pins exist
  const flownTo = useRef<string | null>(null);
  useEffect(() => {
    if (!selectedAlertId) { flownTo.current = null; return; }
    if (flownTo.current === selectedAlertId) return;
    const pin = d.pins.find((p) => p.alerts.some((a) => a.id === selectedAlertId));
    if (!pin || !mapRef.current) return;
    flownTo.current = selectedAlertId;
    const zoom = Math.max(mapRef.current.getZoom(), PIN_ZOOM);
    mapRef.current.flyTo({ center: pin.position, zoom, duration: 1400, essential: true, offset: CARD_ROOM });
  }, [selectedAlertId, d.pins]);

  const onClick = ({ object, layer }: PickingInfo) => {
    if (cardClickedJustNow()) return; // the click was on a card over the map, not on a field
    if (layer?.id === "alert-pins") { selectAlert((object as AlertPin).alerts[0]); return; }
    const p = object as GeoParcel | undefined;
    selectParcel(p ? { ...p.properties, ring: p.geometry.coordinates[0] } : null);
  };
  const onHover = ({ object }: PickingInfo) => {
    const canvas = mapRef.current?.getCanvas();
    if (canvas) canvas.style.cursor = object ? "pointer" : "";
  };
  return (
    <div className="map-canvas" data-tour="map">
      <Map
        ref={mapRef}
        initialViewState={HOME_VIEW}
        mapStyle={STYLE}
        dragRotate={false}
        pitchWithRotate={false}
        touchPitch={false}
        maxPitch={0}
        attributionControl={false}
        onMoveEnd={(e) => setViewRegion(e.viewState.longitude < 18 ? "SE_SKANE" : "FI_SW")}
      >
        <AttributionControl compact position="bottom-right" />
        <DeckOverlay interleaved layers={layers} onClick={onClick} onHover={onHover} />
        {selectedPin && selectedAlert ? <PinCard alert={selectedAlert} position={selectedPin.position} /> : null}
        <ParcelCard />
      </Map>
      <WeatherFx />
      <div className="vignette" aria-hidden="true" />
    </div>
  );
}
