import DeckGL from "@deck.gl/react";
import type { PickingInfo } from "@deck.gl/core";
import Map from "react-map-gl/maplibre";
import "maplibre-gl/dist/maplibre-gl.css";
import { useStore, type MapLayer } from "../../state/store";
import { Status } from "../../components/Status";
import { useMapData } from "./useMapData";

const BASEMAP = import.meta.env.VITE_BASEMAP_STYLE;
const LAYERS: MapLayer[] = ["parcels", "farms", "weather"];

function tooltip({ object }: PickingInfo) {
  if (!object) return null;
  const o = object as Record<string, unknown> & { properties?: Record<string, unknown> };
  const props = o.properties ?? o;
  return { text: Object.entries(props).filter(([k]) => k !== "position").map(([k, v]) => `${k}: ${v}`).join("\n") };
}

export function MapView() {
  const { view, setView, layer, setLayer } = useStore();
  const { layers, pending, error } = useMapData();
  return (
    <div className="map">
      <div className="map-layer-toggle tabs row" role="tablist">
        {LAYERS.map((l) => (
          <button key={l} role="tab" aria-selected={layer === l} onClick={() => setLayer(l)}>{l}</button>
        ))}
        <Status loading={pending} error={error} />
      </div>
      <DeckGL
        viewState={view}
        onViewStateChange={({ viewState }) => setView(viewState as typeof view)}
        controller
        layers={layers}
        getTooltip={tooltip}
      >
        {BASEMAP ? <Map mapStyle={BASEMAP} /> : null}
      </DeckGL>
    </div>
  );
}
