import { IconLayer, PolygonLayer } from "@deck.gl/layers";
import type { GeoParcel } from "../../../api/types";
import type { RGB } from "../../../theme/palette";
import type { FarmZone } from "../../fieldradar/useFieldData";

/** How long a colour takes to morph to the next year's. Just under the play step, so playback flows. */
export const TWEEN_MS = 420;
const tween = { duration: TWEEN_MS, type: "interpolation" as const };

// A soft round glow (white, alpha falling off smoothly), tinted per farm by deck.gl (mask: true).
const GLOW_PX = 128;
function glowSprite(): string {
  const c = document.createElement("canvas");
  c.width = c.height = GLOW_PX;
  const g = c.getContext("2d")!;
  const r = GLOW_PX / 2;
  const grad = g.createRadialGradient(r, r, 0, r, r, r);
  grad.addColorStop(0, "rgba(255,255,255,0.95)");
  grad.addColorStop(0.35, "rgba(255,255,255,0.6)");
  grad.addColorStop(0.7, "rgba(255,255,255,0.18)");
  grad.addColorStop(1, "rgba(255,255,255,0)");
  g.fillStyle = grad;
  g.fillRect(0, 0, GLOW_PX, GLOW_PX);
  return c.toDataURL();
}
let GLOW: string | null = null;

/** Farms as soft glowing zones (readable zoomed out) with their fields on top (readable zoomed in).
 *  `farmColor` returns null when the farm has no value for the layer: no glow, a faint field outline. */
export function fieldLayers(
  parcels: GeoParcel[], zones: FarmZone[], farmColor: (farmId: string) => RGB | null,
  selectedId: string | null, trigger: unknown,
) {
  GLOW ??= glowSprite();
  const glow = new IconLayer<FarmZone>({
    id: "farm-glow",
    data: zones,
    iconAtlas: GLOW,
    iconMapping: { glow: { x: 0, y: 0, width: GLOW_PX, height: GLOW_PX, mask: true } },
    getIcon: () => "glow",
    getPosition: (z) => z.position,
    getSize: (z) => z.size_m,
    sizeUnits: "meters",
    sizeMinPixels: 14,
    getColor: (z) => { const c = farmColor(z.farm_id); return c ? [...c, 175] : [0, 0, 0, 0]; },
    updateTriggers: { getColor: [trigger] },
    transitions: { getColor: tween },
  });
  const fields = new PolygonLayer<GeoParcel>({
    id: "parcel-fill",
    data: parcels,
    getPolygon: (f) => f.geometry.coordinates[0],
    filled: true,
    stroked: true,
    getFillColor: (f) => { const c = farmColor(f.properties.farm_id); return c ? [...c, 42] : [200, 210, 200, 8]; },
    getLineColor: (f) => {
      if (f.properties.parcel_id === selectedId) return [255, 255, 255, 240];
      const c = farmColor(f.properties.farm_id);
      return c ? [...c, 85] : [220, 230, 220, 30];
    },
    getLineWidth: (f) => (f.properties.parcel_id === selectedId ? 2.5 : 1),
    lineWidthUnits: "pixels",
    pickable: true,
    autoHighlight: true,
    highlightColor: [255, 255, 255, 45],
    updateTriggers: { getFillColor: [trigger], getLineColor: [trigger, selectedId], getLineWidth: [selectedId] },
    transitions: { getFillColor: tween, getLineColor: tween },
  });
  return [glow, fields];
}
