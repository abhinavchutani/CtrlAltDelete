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

  const pending = [sim, farms, geoParcels, geoFarms, weather].some((q) => q.isLoading);
  const error = [sim, farms, geoParcels, geoFarms, weather].find((q) => q.error)?.error ?? null;
  return { layers, pending, error };
}
