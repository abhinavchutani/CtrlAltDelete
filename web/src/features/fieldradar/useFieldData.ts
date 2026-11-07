// Everything Field Radar draws, derived from the API (no numbers are made up here):
//   health  = the farm's yield change vs its 1991–2020 baseline in the chosen year   (/api/cube/{id}/farms)
//   risk    = € at risk band of the farm's region for pea in that year              (SimResult.regions)
//   drought = flowering-stage drought index of the parcel's weather cell            (/api/weather)
//   heat    = hot days (Tmax ≥ 27 °C) at pea flowering in that cell                  (/api/weather)
import { useMemo } from "react";
import { useActiveScenario, useFarms, useGeoFarms, useGeoParcels, useWeather } from "../../api/hooks";
import type { EurBand, GeoParcel, Region, WeatherCell } from "../../api/types";
import { START_YEAR, useStore, type ColorBy } from "../../state/store";
import { mix, type RGB } from "../../theme/palette";

export const RISK: Record<"low" | "medium" | "high", RGB> = { low: [61, 220, 99], medium: [245, 184, 46], high: [255, 107, 74] };
export const BANDS: EurBand[] = ["< €50k", "€50–100k", "€100–250k", "€250k–1M", "> €1M"];
export type Level = "low" | "medium" | "high";

/** Three-stop scale (low → medium → high) for t in 0..1. */
export const scale = (t: number): RGB => (t < 0.5 ? mix(RISK.low, RISK.medium, t * 2) : mix(RISK.medium, RISK.high, (t - 0.5) * 2));
export const healthLevel = (pct: number | undefined): Level => (pct === undefined || pct > -10 ? "low" : pct > -20 ? "medium" : "high");
export const droughtLevel = (d: number): Level => (d < 0.45 ? "low" : d < 0.65 ? "medium" : "high");
export const bandLevel = (b: EurBand | undefined): Level =>
  !b ? "low" : BANDS.indexOf(b) >= 3 ? "high" : BANDS.indexOf(b) >= 2 ? "medium" : "low";

const centroid = (ring: [number, number][]): [number, number] => {
  const n = ring.length - (ring[0][0] === ring[ring.length - 1][0] && ring[0][1] === ring[ring.length - 1][1] ? 1 : 0);
  let x = 0, y = 0;
  for (let i = 0; i < n; i++) { x += ring[i][0]; y += ring[i][1]; }
  return [x / n, y / n];
};

export function useFieldData() {
  const { year, colorBy } = useStore();
  const sim = useActiveScenario();
  const farms = useFarms(sim.data?.scenario_id, year);
  const geoParcels = useGeoParcels();
  const geoFarms = useGeoFarms();
  const climate = year <= START_YEAR ? "historical" : (sim.data?.spec.climate ?? "ssp245");
  const weather = useWeather(climate, year);

  const farmRegion = useMemo(
    () => new Map((geoFarms.data?.features ?? []).map((f) => [f.properties.farm_id, f.properties.region as Region])),
    [geoFarms.data],
  );
  const farmChange = useMemo(() => new Map((farms.data ?? []).map((f) => [f.farm_id, f.change_vs_baseline_pct])), [farms.data]);
  const cells = weather.data?.cells ?? [];
  const cellById = useMemo(() => new Map(cells.map((c) => [c.cell_id, c])), [cells]);

  // parcel → nearest weather cell, computed once from the cell grid (cell positions don't change between frames)
  const parcels = geoParcels.data?.features ?? [];
  const cellOfParcel = useMemo(() => {
    const out = new Map<string, string>();
    if (!cells.length) return out;
    for (const p of parcels) {
      const [x, y] = centroid(p.geometry.coordinates[0]);
      let best = cells[0], bd = Infinity;
      for (const c of cells) { const d = (c.lon - x) ** 2 + (c.lat - y) ** 2; if (d < bd) { bd = d; best = c; } }
      out.set(p.properties.parcel_id, best.cell_id);
    }
    return out;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [parcels, cells.length]);

  const regionBand = useMemo(() => {
    const m = new Map<Region, EurBand>();
    for (const r of sim.data?.regions ?? []) if (r.year === year && r.crop === "pea") m.set(r.region, r.eur_at_risk);
    return m;
  }, [sim.data, year]);

  const cellOf = (p: GeoParcel): WeatherCell | undefined => cellById.get(cellOfParcel.get(p.properties.parcel_id) ?? "");

  const colorOf = useMemo(() => {
    const by: Record<ColorBy, (p: GeoParcel) => RGB | null> = {
      health: (p) => {
        const v = farmChange.get(p.properties.farm_id);
        return v === undefined ? null : scale(Math.max(0, Math.min(1, (-v + 5) / 30)));
      },
      risk: (p) => {
        const b = regionBand.get(farmRegion.get(p.properties.farm_id) as Region);
        return b ? scale(BANDS.indexOf(b) / (BANDS.length - 1)) : null;
      },
      drought: (p) => { const c = cellOf(p); return c ? scale((c.drought_index - 0.2) / 0.6) : null; },
      heat: (p) => { const c = cellOf(p); return c ? scale(c.hot_days_flowering / 8) : null; },
    };
    return by[colorBy];
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [colorBy, farmChange, regionBand, farmRegion, cellById, cellOfParcel]);

  const stats = useMemo(() => {
    const fs = farms.data ?? [];
    const ok = fs.filter((f) => f.risk === "ok").length;
    const bands = [...regionBand.values()];
    const worst = bands.length ? bands.reduce((a, b) => (BANDS.indexOf(b) > BANDS.indexOf(a) ? b : a)) : undefined;
    const droughtBy = (r: Region) => {
      const cs = cells.filter((c) => c.region === r);
      return cs.length ? cs.reduce((s, c) => s + c.drought_index, 0) / cs.length : undefined;
    };
    return {
      healthPct: fs.length ? Math.round((100 * ok) / fs.length) : undefined,
      worstBand: worst,
      drought: { FI_SW: droughtBy("FI_SW"), SE_SKANE: droughtBy("SE_SKANE") } as Record<Region, number | undefined>,
    };
  }, [farms.data, regionBand, cells]);

  const active = [sim, farms, geoParcels, geoFarms, weather];
  return {
    parcels, colorOf, trigger: [colorBy, farms.data, regionBand, weather.data], stats, sim,
    farmChange, farmRegion, regionBand, cellOf,
    pending: active.some((q) => q.isLoading), error: active.find((q) => q.error)?.error ?? null,
  };
}
