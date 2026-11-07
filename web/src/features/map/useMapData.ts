// Everything the map needs for the current scenario × year × layer, as deck.gl layers.
import { useMemo } from "react";
import { useActiveScenario, useFarms, useGeoFarms, useGeoParcels, useWeather } from "../../api/hooks";
import { START_YEAR, useStore } from "../../state/store";
import { readPalette } from "../../theme/palette";
import { farmsLayer } from "./layers/farms";
import { parcelsLayer } from "./layers/parcels";
import { weatherLayer } from "./layers/weather";

export function useMapData() {
  const { year, layer } = useStore();
  const sim = useActiveScenario();
  const farms = useFarms(sim.data?.scenario_id, year);
  const geoParcels = useGeoParcels();
  const geoFarms = useGeoFarms();
  const climate = year <= START_YEAR ? "historical" : (sim.data?.spec.climate ?? "ssp245");
  const weather = useWeather(climate, year);
  const palette = useMemo(() => readPalette(), []);

  const layers = useMemo(() => {
    if (layer === "weather") return [weatherLayer(weather.data, palette)];
    if (layer === "farms") return [farmsLayer(geoFarms.data, farms.data, palette)];
    return [parcelsLayer(geoParcels.data, farms.data, palette)];
  }, [layer, weather.data, geoFarms.data, geoParcels.data, farms.data, palette]);

  // only the active layer's queries decide loading / error, so a broken layer doesn't flag the others
  const active = layer === "weather" ? [weather] : layer === "farms" ? [sim, farms, geoFarms] : [sim, farms, geoParcels];
  const pending = active.some((q) => q.isLoading);
  const error = active.find((q) => q.error)?.error ?? null;
  return { layers, pending, error };
}
