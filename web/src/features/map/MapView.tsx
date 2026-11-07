import { useCallback, useEffect, useRef, useState } from "react";
import type { PickingInfo } from "@deck.gl/core";
import { MapboxOverlay, type MapboxOverlayProps } from "@deck.gl/mapbox";
import Map, { AttributionControl, useControl, type IControl, type MapLayerMouseEvent, type MapRef } from "react-map-gl/maplibre";
import type { StyleSpecification } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { GeoParcel } from "../../api/types";
import { HOME_VIEW, useStore } from "../../state/store";
import { FieldCard } from "../fieldradar/FieldCard";
import { useFieldData } from "../fieldradar/useFieldData";
import { lightStyle, PLAIN, SATELLITE } from "./basemap";
import { cardClickedJustNow } from "./isolate";
import { fieldLayers } from "./layers/parcels";

/** deck.gl drawn inside MapLibre's own WebGL context ("interleaved"), so fields never trail the map while panning. */
function DeckOverlay({ onReady, ...props }: MapboxOverlayProps & { onReady: (o: MapboxOverlay) => void }) {
  const overlay = useControl(() => new MapboxOverlay(props) as unknown as IControl) as unknown as MapboxOverlay;
  overlay.setProps(props);
  useEffect(() => { onReady(overlay); }, [overlay, onReady]);
  return null;
}

let LIGHT: Promise<string | StyleSpecification> | null = null;

/** The light map with every contract field coloured by status. Click a field for its card. MapLibre owns the camera. */
export function MapView({ satellite }: { satellite: boolean }) {
  const mapRef = useRef<MapRef>(null);
  const camera = useStore((s) => s.camera);
  const selectedParcel = useStore((s) => s.selectedParcel);
  const selectParcel = useStore((s) => s.selectParcel);
  const d = useFieldData();
  const [light, setLight] = useState<string | StyleSpecification>(PLAIN);
  useEffect(() => { void (LIGHT ??= lightStyle()).then(setLight); }, []);
  const layers = fieldLayers(d.parcels, d.statusOf, selectedParcel?.parcel_id ?? null, d.trigger);

  useEffect(() => {
    if (camera.seq === 0) return;
    const { longitude, latitude, zoom } = camera.target;
    mapRef.current?.flyTo({ center: [longitude, latitude], zoom, duration: 1400, essential: true });
  }, [camera]);

  // MapLibre owns the click (deck's own tap recogniser misses some clicks in interleaved mode); deck only picks.
  const overlay = useRef<MapboxOverlay | null>(null);
  const onReady = useCallback((o: MapboxOverlay) => { overlay.current = o; }, []);
  const onClick = (e: MapLayerMouseEvent) => {
    if (cardClickedJustNow()) return;
    const info = overlay.current?.pickObject({ x: e.point.x, y: e.point.y, radius: 3 });
    const p = info?.object as GeoParcel | undefined;
    selectParcel(p ? { ...p.properties, ring: p.geometry.coordinates[0] } : null);
  };
  const onHover = ({ object }: PickingInfo) => {
    const canvas = mapRef.current?.getCanvas();
    if (canvas) canvas.style.cursor = object ? "pointer" : "";
  };
  return (
    <div className="map-wrap" data-tour="map" role="region"
      aria-label="Map of contract fields coloured by status. Use the season strip below to change the year.">
      <Map
        ref={mapRef}
        initialViewState={camera.seq ? camera.target : HOME_VIEW}
        mapStyle={satellite ? SATELLITE : light}
        dragRotate={false}
        pitchWithRotate={false}
        touchPitch={false}
        maxPitch={0}
        attributionControl={false}
        onClick={onClick}
      >
        <AttributionControl compact position="bottom-right" style={{ marginBottom: 112 }} />
        <DeckOverlay interleaved layers={layers} onHover={onHover} onReady={onReady} />
        <FieldCard />
      </Map>
    </div>
  );
}
