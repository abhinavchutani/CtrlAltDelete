// Everything the map draws, derived from the API (no numbers are made up here). One status per farm per lens:
//   overall = the farm's yield class for the year (API: ≤ −20 % bad year, ≤ −10 % watch)      (/api/cube/{id}/farms)
//   drought = flowering-stage drought index of the farm's nearest weather cell                (/api/weather)
//   heat    = hot days (Tmax ≥ 27 °C) at pea flowering in that cell                            (/api/weather)
//   rain    = growing-season rain vs 1991–2020 in that cell                                    (/api/weather)
// The weather lenses use the display thresholds in LENS_RULE (stated in the legend's title).
import { useMemo } from "react";
import { climateFor, useActiveScenario, useFarms, useGeoFarms, useGeoParcels, usePrefetchYears, useWeather } from "../../api/hooks";
import type { FarmYear, GeoParcel, Region, Status, WeatherCell } from "../../api/types";
import { useStore, type Lens } from "../../state/store";

export type RGB = [number, number, number];
export const STATUS_RGB: Record<Status, RGB> = { ok: [169, 211, 160], watch: [212, 147, 31], risk: [166, 58, 39] };
export const FARM_STATUS: Record<FarmYear["risk"], Status> = { ok: "ok", watch: "watch", bad: "risk" };
export const LENS_RULE: Record<Exclude<Lens, "overall">, { status: (c: WeatherCell) => Status; rule: string }> = {
  drought: { status: (c) => (c.drought_index < 0.45 ? "ok" : c.drought_index < 0.65 ? "watch" : "risk"),
    rule: "Drought index at flowering: under 0.45 on track, under 0.65 watch, else bad" },
  heat: { status: (c) => (c.hot_days_flowering <= 2 ? "ok" : c.hot_days_flowering <= 5 ? "watch" : "risk"),
    rule: "Hot days (≥ 27 °C) at flowering: up to 2 on track, up to 5 watch, more is bad" },
  rain: { status: (c) => (c.precip_anom_pct >= -10 ? "ok" : c.precip_anom_pct >= -25 ? "watch" : "risk"),
    rule: "Growing-season rain vs 1991–2020: within −10 % on track, to −25 % watch, drier is bad" },
};

export const centroid = (ring: [number, number][]): [number, number] => {
  const n = ring.length - (ring[0][0] === ring[ring.length - 1][0] && ring[0][1] === ring[ring.length - 1][1] ? 1 : 0);
  let x = 0, y = 0;
  for (let i = 0; i < n; i++) { x += ring[i][0]; y += ring[i][1]; }
  return [x / n, y / n];
};

export function useFieldData() {
  const year = useStore((s) => s.year);
  const lens = useStore((s) => s.lens);
  const farmFilter = useStore((s) => s.farmFilter);
  const sim = useActiveScenario();
  const farms = useFarms(sim.data?.scenario_id, year);
  const geoParcels = useGeoParcels();
  const geoFarms = useGeoFarms();
  const climate = sim.data?.spec.climate;
  const weather = useWeather(climateFor(year, climate), year);
  usePrefetchYears(sim.data?.scenario_id, (sim.data?.years ?? []).filter((y) => y <= 2040), climate);

  const farmRegion = useMemo(
    () => new Map((geoFarms.data?.features ?? []).map((f) => [f.properties.farm_id, f.properties.region as Region])),
    [geoFarms.data],
  );
  const farmPos = useMemo(
    () => new Map((geoFarms.data?.features ?? []).map((f) => [f.properties.farm_id, f.geometry.coordinates])),
    [geoFarms.data],
  );
  const farmChange = useMemo(() => new Map((farms.data ?? []).map((f) => [f.farm_id, f.change_vs_baseline_pct])), [farms.data]);
  const farmRisk = useMemo(() => new Map((farms.data ?? []).map((f) => [f.farm_id, FARM_STATUS[f.risk]])), [farms.data]);
  const cells = weather.data?.cells ?? [];
  const cellById = useMemo(() => new Map(cells.map((c) => [c.cell_id, c])), [cells]);
  // farm → nearest weather cell (cell positions don't change between years, so only the grid's size matters)
  const cellOfFarm = useMemo(() => {
    const out = new Map<string, string>();
    if (!cells.length) return out;
    for (const [farm, [x, y]] of farmPos) {
      let best = cells[0], bd = Infinity;
      for (const c of cells) { const d = (c.lon - x) ** 2 + (c.lat - y) ** 2; if (d < bd) { bd = d; best = c; } }
      out.set(farm, best.cell_id);
    }
    return out;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [farmPos, cells.length]);
  const cellOf = (farmId: string): WeatherCell | undefined => cellById.get(cellOfFarm.get(farmId) ?? "");

  const statusOf = useMemo(() => {
    const keep = farmFilter ? new Set(farmFilter.ids) : null;
    const base = lens === "overall"
      ? (f: string) => farmRisk.get(f) ?? null
      : (f: string) => { const c = cellById.get(cellOfFarm.get(f) ?? ""); return c ? LENS_RULE[lens as Exclude<Lens, "overall">].status(c) : null; };
    return keep ? (f: string) => (keep.has(f) ? base(f) : null) : base; // filtered-out farms draw faded (no status)
  }, [lens, farmRisk, cellById, cellOfFarm, farmFilter]);

  const parcels = geoParcels.data?.features ?? [];
  const counts = useMemo(() => {
    const by: Record<Region, Record<Status, number>> = { FI_SW: { ok: 0, watch: 0, risk: 0 }, SE_SKANE: { ok: 0, watch: 0, risk: 0 } };
    for (const p of parcels) {
      if (p.properties.crop !== "pea") continue;
      const s = statusOf(p.properties.farm_id), r = farmRegion.get(p.properties.farm_id);
      if (s && r) by[r][s] += 1;
    }
    return by;
  }, [parcels, statusOf, farmRegion]);

  const active = [sim, farms, geoParcels, geoFarms, weather];
  return {
    parcels: parcels as GeoParcel[], statusOf, trigger: [lens, farms.data, weather.data, farmFilter], sim, counts,
    farmChange, farmRisk, farmRegion, cellOf,
    pending: active.some((q) => q.isLoading || q.isFetching), error: active.find((q) => q.error)?.error ?? null,
  };
}
