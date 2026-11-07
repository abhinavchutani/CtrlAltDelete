import { ColumnLayer } from "@deck.gl/layers";
import type { FarmYear, FeatureCollection, GeoPoint } from "../../../api/types";
import { changeColor, type Palette } from "../../../theme/palette";

type FarmPoint = { farm_id: string; position: [number, number]; change: number | undefined };

/** One column per farm: height = the size of the drop, colour = change vs baseline. */
export function farmsLayer(geo: FeatureCollection<GeoPoint> | undefined, farms: FarmYear[] | undefined, p: Palette) {
  const byFarm = new Map((farms ?? []).map((f) => [f.farm_id, f.change_vs_baseline_pct]));
  const data: FarmPoint[] = (geo?.features ?? []).map((f) => ({
    farm_id: f.properties.farm_id, position: f.geometry.coordinates, change: byFarm.get(f.properties.farm_id),
  }));
  return new ColumnLayer<FarmPoint>({
    id: "farms",
    data,
    diskResolution: 8,
    radius: 3500,
    extruded: true,
    getPosition: (d) => d.position,
    getElevation: (d) => 500 + Math.max(0, -(d.change ?? 0)) * 800,
    getFillColor: (d) => changeColor(p, d.change),
    pickable: true,
    updateTriggers: { getFillColor: [farms], getElevation: [farms] },
  });
}
