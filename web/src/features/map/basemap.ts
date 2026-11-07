// Satellite imagery basemap (no API key): Esri World Imagery tiles, darkened so the data layers glow on top.
// VITE_BASEMAP_STYLE (a MapLibre style URL) still overrides it.
import type { StyleSpecification } from "maplibre-gl";

export const SATELLITE: StyleSpecification = {
  version: 8,
  sources: {
    imagery: {
      type: "raster",
      tiles: ["https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"],
      tileSize: 256,
      maxzoom: 18,
      attribution: "Imagery © Esri, Maxar, Earthstar Geographics",
    },
  },
  layers: [
    { id: "bg", type: "background", paint: { "background-color": "#0b120d" } },
    {
      id: "imagery", type: "raster", source: "imagery",
      paint: { "raster-brightness-max": 0.62, "raster-saturation": -0.25, "raster-contrast": 0.08 },
    },
  ],
};

export const basemapStyle = (): string | StyleSpecification => import.meta.env.VITE_BASEMAP_STYLE || SATELLITE;
