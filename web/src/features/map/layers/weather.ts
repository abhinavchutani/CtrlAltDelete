import { PolygonLayer } from "@deck.gl/layers";
import type { WeatherCell, WeatherFrame } from "../../../api/types";
import { mix, type Palette } from "../../../theme/palette";

const HALF = 0.125; // cells are 0.25° squares around (lat, lon)

/** Weather cells as flat squares; colour = drought index (wet → dry). */
export function weatherLayer(frame: WeatherFrame | undefined, p: Palette) {
  return new PolygonLayer<WeatherCell>({
    id: "weather",
    data: frame?.cells ?? [],
    getPolygon: (c) => [
      [c.lon - HALF, c.lat - HALF], [c.lon + HALF, c.lat - HALF], [c.lon + HALF, c.lat + HALF], [c.lon - HALF, c.lat + HALF],
    ],
    getFillColor: (c) => [...mix(p.wet, p.dry, c.drought_index), 170] as [number, number, number, number],
    stroked: false,
    pickable: true,
    updateTriggers: { getFillColor: [frame] },
  });
}
