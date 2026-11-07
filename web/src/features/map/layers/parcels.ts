import { PolygonLayer } from "@deck.gl/layers";
import type { GeoParcel } from "../../../api/types";
import type { RGB } from "../../../theme/palette";

/** Parcels as flat glowing fields: a translucent fill plus a bright edge, coloured by the active layer.
 *  `colorOf` returns null when the parcel has no value for that layer (drawn as a faint outline). */
export function parcelLayers(
  parcels: GeoParcel[], colorOf: (p: GeoParcel) => RGB | null, selectedId: string | null, trigger: unknown,
) {
  const fill = new PolygonLayer<GeoParcel>({
    id: "parcel-fill",
    data: parcels,
    getPolygon: (f) => f.geometry.coordinates[0],
    filled: true,
    stroked: true,
    getFillColor: (f) => { const c = colorOf(f); return c ? [...c, 120] : [200, 210, 200, 18]; },
    getLineColor: (f) => {
      const c = colorOf(f);
      if (f.properties.parcel_id === selectedId) return [255, 255, 255, 255];
      return c ? [...c, 235] : [220, 230, 220, 60];
    },
    getLineWidth: (f) => (f.properties.parcel_id === selectedId ? 3 : 1.5),
    lineWidthUnits: "pixels",
    pickable: true,
    autoHighlight: true,
    highlightColor: [255, 255, 255, 50],
    updateTriggers: { getFillColor: [trigger], getLineColor: [trigger, selectedId], getLineWidth: [selectedId] },
  });
  // a wide, faint outline behind the edge reads as a glow on the dark imagery
  const glow = new PolygonLayer<GeoParcel>({
    id: "parcel-glow",
    data: parcels,
    getPolygon: (f) => f.geometry.coordinates[0],
    filled: false,
    stroked: true,
    getLineColor: (f) => { const c = colorOf(f); return c ? [...c, 70] : [0, 0, 0, 0]; },
    getLineWidth: 7,
    lineWidthUnits: "pixels",
    updateTriggers: { getLineColor: [trigger] },
  });
  return [glow, fill];
}
