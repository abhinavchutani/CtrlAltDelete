import { PolygonLayer } from "@deck.gl/layers";
import type { FarmYear, FeatureCollection, GeoParcel } from "../../../api/types";
import { changeColor, type Palette } from "../../../theme/palette";

/** Parcels as extruded polygons; colour and height = their farm's change vs baseline in the chosen year. */
export function parcelsLayer(geo: FeatureCollection<GeoParcel> | undefined, farms: FarmYear[] | undefined, p: Palette) {
  const byFarm = new Map((farms ?? []).map((f) => [f.farm_id, f.change_vs_baseline_pct]));
  return new PolygonLayer<GeoParcel>({
    id: "parcels",
    data: geo?.features ?? [],
    getPolygon: (f) => f.geometry.coordinates[0],
    extruded: true,
    getElevation: (f) => 40 + Math.abs(byFarm.get(f.properties.farm_id) ?? 0) * 25,
    getFillColor: (f) => changeColor(p, byFarm.get(f.properties.farm_id)),
    pickable: true,
    updateTriggers: { getFillColor: [farms], getElevation: [farms] },
  });
}
