import { PolygonLayer } from "@deck.gl/layers";
import type { GeoParcel, Status } from "../../../api/types";
import { STATUS_RGB } from "../../fieldradar/useFieldData";

/** How long a colour takes to morph to the next year's. */
export const TWEEN_MS = 420;
const tween = { duration: TWEEN_MS, type: "interpolation" as const };
const LEAF: [number, number, number] = [59, 117, 25];
const INK: [number, number, number] = [31, 42, 30];

/** Fields are the hero: filled by status, on-track fields outlined in leaf, others in white; the selected field in ink. */
export function fieldLayers(parcels: GeoParcel[], statusOf: (farmId: string) => Status | null, selectedId: string | null, trigger: unknown) {
  return [new PolygonLayer<GeoParcel>({
    id: "parcel-fill",
    data: parcels,
    getPolygon: (f) => f.geometry.coordinates[0],
    filled: true,
    stroked: true,
    getFillColor: (f) => { const s = statusOf(f.properties.farm_id); return s ? [...STATUS_RGB[s], s === "ok" ? 215 : 235] : [200, 192, 172, 90]; },
    getLineColor: (f) => {
      if (f.properties.parcel_id === selectedId) return [...INK, 255];
      return statusOf(f.properties.farm_id) === "ok" ? [...LEAF, 230] : [255, 255, 255, 235];
    },
    getLineWidth: (f) => (f.properties.parcel_id === selectedId ? 3 : 1.2),
    lineWidthUnits: "pixels",
    pickable: true,
    autoHighlight: true,
    highlightColor: [255, 255, 255, 60],
    updateTriggers: { getFillColor: [trigger], getLineColor: [trigger, selectedId], getLineWidth: [selectedId] },
    transitions: { getFillColor: tween, getLineColor: tween },
  })];
}
