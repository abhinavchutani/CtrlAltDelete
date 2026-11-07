// Light cartographic basemap: OpenFreeMap's Positron vector style (no API key), restyled to the Field Radar tokens
// so the fields stay the hero. Satellite is an opt-in layer. VITE_BASEMAP_STYLE (a MapLibre style URL) overrides it.
import type { LayerSpecification, StyleSpecification } from "maplibre-gl";

const STYLE_URL = "https://tiles.openfreemap.org/styles/positron";
type Palette = { land: string; water: string; woods: string; town: string; building: string; casing: string;
  road: string; rail: string; label: string; halo: string; boundary: string };
/** Mirrors the --map-* tokens in tokens.css (MapLibre paints need literal colours). */
const PALETTES: Record<"light" | "dark", Palette> = {
  light: { land: "#ECEEE6", water: "#CFE0E8", woods: "#DFE6D2", town: "#E6E5DC", building: "#DDDBD0", casing: "#D4D4C8",
    road: "#FFFFFF", rail: "#D4D4C8", label: "#5D6659", halo: "#ECEEE6", boundary: "#A3A595" },
  dark: { land: "#121615", water: "#0D1D26", woods: "#142019", town: "#191D1B", building: "#1E2321", casing: "#252A28",
    road: "#2B312E", rail: "#252A28", label: "#8A948C", halo: "#121615", boundary: "#3C4440" },
};


/** Shown while the vector style loads (or if it can't be reached): plain land, fields on top. */
export const plainStyle = (theme: "light" | "dark"): StyleSpecification => ({
  version: 8, sources: {}, layers: [{ id: "bg", type: "background", paint: { "background-color": PALETTES[theme].land } }],
});
export const PLAIN: StyleSpecification = plainStyle("light");

export const SATELLITE: StyleSpecification = {
  version: 8,
  sources: {
    imagery: {
      type: "raster", tileSize: 256, maxzoom: 18, attribution: "Imagery © Esri, Maxar, Earthstar Geographics",
      tiles: ["https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"],
    },
  },
  layers: [{ id: "imagery", type: "raster", source: "imagery", paint: { "raster-saturation": -0.3, "raster-brightness-max": 0.9 } }],
};

function paintFor(l: LayerSpecification, C: Palette): Record<string, unknown> | null {
  const id = l.id;
  if (l.type === "background") return { "background-color": C.land };
  if (l.type === "raster" || l.type === "hillshade") return null; // drop shaded relief: nothing busy behind fields
  if (l.type === "fill") {
    if (id.startsWith("water")) return { "fill-color": C.water, "fill-opacity": 1 };
    if (id.includes("wood") || id === "park" || id.includes("grass")) return { "fill-color": C.woods, "fill-opacity": 1 };
    if (id.includes("residential")) return { "fill-color": C.town, "fill-opacity": 0.8 };
    if (id === "building") return { "fill-color": C.building, "fill-opacity": 0.8 };
    return { "fill-color": C.land, "fill-opacity": 0.6 };
  }
  if (l.type === "line") {
    if (id.startsWith("waterway")) return { "line-color": C.water };
    if (id.includes("casing")) return { "line-color": C.casing };
    if (id.startsWith("rail")) return { "line-color": C.rail };
    if (id.startsWith("boundary")) return { "line-color": C.boundary, "line-opacity": 0.5 };
    if (id.startsWith("highway") || id.startsWith("road") || id.startsWith("tunnel") || id.startsWith("aeroway")) return { "line-color": C.road };
  }
  if (l.type === "symbol") return { "text-color": C.label, "text-halo-color": C.halo, "text-halo-width": 1.4, "icon-opacity": 0.6 };
  return {};
}

/** Fetch Positron and recolour every layer to the tokens. Falls back to PLAIN if offline. */
export async function lightStyle(theme: "light" | "dark" = "light"): Promise<string | StyleSpecification> {
  if (import.meta.env.VITE_BASEMAP_STYLE) return import.meta.env.VITE_BASEMAP_STYLE as string;
  try {
    const res = await fetch(STYLE_URL);
    if (!res.ok) throw new Error(String(res.status));
    const style = (await res.json()) as StyleSpecification;
    const layers: LayerSpecification[] = [];
    for (const l of style.layers) {
      const p = paintFor(l, PALETTES[theme]);
      if (p === null) continue;
      layers.push({ ...l, paint: { ...(("paint" in l && l.paint) || {}), ...p } } as LayerSpecification);
    }
    return { ...style, layers };
  } catch {
    return plainStyle(theme);
  }
}
