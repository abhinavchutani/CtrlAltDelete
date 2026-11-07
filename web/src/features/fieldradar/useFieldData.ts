// Everything Field Radar draws, derived from the API (no numbers are made up here):
//   health  = the farm's ok / watch / bad class for the chosen year (the API's own thresholds)  (/api/cube/{id}/farms)
//   risk    = € at risk band for the parcel's 2025 crop in its region (contract crops only)    (SimResult.regions)
//   drought = flowering-stage drought index of the parcel's weather cell                       (/api/weather)
//   heat    = hot days (Tmax ≥ 27 °C) at pea flowering in that cell                             (/api/weather)
//   pins    = the year's alerts, each on the worst-hit parcel of its crop in its region
import { useMemo } from "react";
import { useActiveScenario, useFarms, useGeoFarms, useGeoParcels, useWeather } from "../../api/hooks";
import type { Alert, EurBand, FarmYear, GeoParcel, Region, WeatherCell } from "../../api/types";
import { START_YEAR, useStore, type ColorBy } from "../../state/store";
import { mix, type RGB } from "../../theme/palette";

export const RISK: Record<"low" | "medium" | "high", RGB> = { low: [61, 220, 99], medium: [245, 184, 46], high: [255, 107, 74] };
export const BANDS: EurBand[] = ["< €50k", "€50–100k", "€100–250k", "€250k–1M", "> €1M"];
export type Level = "low" | "medium" | "high";
export type FarmRisk = FarmYear["risk"];
export type AlertPin = { alerts: Alert[]; parcel: GeoParcel; position: [number, number] };

/** Three-stop scale (low → medium → high) for t in 0..1. */
export const scale = (t: number): RGB => (t < 0.5 ? mix(RISK.low, RISK.medium, t * 2) : mix(RISK.medium, RISK.high, (t - 0.5) * 2));
export const FARM_LEVEL: Record<FarmRisk, Level> = { ok: "low", watch: "medium", bad: "high" };
export const droughtLevel = (d: number): Level => (d < 0.45 ? "low" : d < 0.65 ? "medium" : "high");
export const bandLevel = (b: EurBand | undefined): Level =>
  !b ? "low" : BANDS.indexOf(b) >= 3 ? "high" : BANDS.indexOf(b) >= 2 ? "medium" : "low";
export const REGION_NAME: Record<Region, string> = { FI_SW: "SW Finland", SE_SKANE: "Skåne" };
export const cropName = (c: string | null | undefined) => (c ? c.replace(/_/g, " ") : "unknown crop");
const SEVERITY_RANK: Record<string, number> = { critical: 0, notable: 1 };

export const centroid = (ring: [number, number][]): [number, number] => {
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
  const farmRisk = useMemo(() => new Map((farms.data ?? []).map((f) => [f.farm_id, f.risk])), [farms.data]);
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

  // € band per region × crop for the year. Only contract crops have one; barley, wheat, ley … don't.
  const cropBand = useMemo(() => {
    const m = new Map<string, EurBand>();
    for (const r of sim.data?.regions ?? []) if (r.year === year) m.set(`${r.region}:${r.crop}`, r.eur_at_risk);
    return m;
  }, [sim.data, year]);
  // an API without parcel crops (older build) falls back to pea, the crop every region reports
  const bandOf = (farmId: string, crop: string | null | undefined): EurBand | undefined =>
    cropBand.get(`${farmRegion.get(farmId)}:${crop === undefined ? "pea" : crop}`);

  const cellOf = (p: GeoParcel): WeatherCell | undefined => cellById.get(cellOfParcel.get(p.properties.parcel_id) ?? "");

  const colorOf = useMemo(() => {
    const by: Record<ColorBy, (p: GeoParcel) => RGB | null> = {
      health: (p) => { const r = farmRisk.get(p.properties.farm_id); return r ? RISK[FARM_LEVEL[r]] : null; },
      risk: (p) => {
        const b = bandOf(p.properties.farm_id, p.properties.crop);
        return b ? scale(BANDS.indexOf(b) / (BANDS.length - 1)) : null;
      },
      drought: (p) => { const c = cellOf(p); return c ? scale((c.drought_index - 0.2) / 0.6) : null; },
      heat: (p) => { const c = cellOf(p); return c ? scale(c.hot_days_flowering / 8) : null; },
    };
    return by[colorBy];
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [colorBy, farmRisk, cropBand, farmRegion, cellById, cellOfParcel]);

  // One pin per alerted parcel this year: the parcel of the alert's crop, in its region, on the farm with the
  // lowest yield change (ties → the larger parcel). Alerts landing on the same parcel share a pin, worst first.
  const pins = useMemo<AlertPin[]>(() => {
    const alerts = (sim.data?.alerts ?? []).filter((a) => a.year === year);
    if (!alerts.length || !farmChange.size) return [];
    const byParcel = new Map<string, AlertPin>();
    for (const a of alerts) {
      let best: GeoParcel | undefined, bv = Infinity;
      for (const p of parcels) {
        const { farm_id, crop, area_ha } = p.properties;
        if (farmRegion.get(farm_id) !== a.region) continue;
        if (a.crop && crop != null && crop !== a.crop) continue;
        const v = farmChange.get(farm_id);
        if (v === undefined) continue;
        if (v < bv || (v === bv && best && area_ha > best.properties.area_ha)) { bv = v; best = p; }
      }
      if (!best) continue;
      const id = best.properties.parcel_id;
      const pin = byParcel.get(id) ?? { alerts: [], parcel: best, position: centroid(best.geometry.coordinates[0]) };
      pin.alerts.push(a);
      byParcel.set(id, pin);
    }
    const pinsOut = [...byParcel.values()];
    for (const pin of pinsOut) pin.alerts.sort((x, y) => (SEVERITY_RANK[x.severity] ?? 9) - (SEVERITY_RANK[y.severity] ?? 9));
    return pinsOut;
  }, [sim.data, year, parcels, farmRegion, farmChange]);

  const stats = useMemo(() => {
    const fs = farms.data ?? [];
    const ok = fs.filter((f) => f.risk === "ok").length;
    let worst: { region: Region; crop: string; band: EurBand } | undefined;
    for (const r of sim.data?.regions ?? []) {
      if (r.year !== year) continue;
      if (!worst || BANDS.indexOf(r.eur_at_risk) > BANDS.indexOf(worst.band)) worst = { region: r.region, crop: r.crop, band: r.eur_at_risk };
    }
    const droughtBy = (r: Region) => {
      const cs = cells.filter((c) => c.region === r);
      return cs.length ? cs.reduce((s, c) => s + c.drought_index, 0) / cs.length : undefined;
    };
    return {
      healthPct: fs.length ? Math.round((100 * ok) / fs.length) : undefined,
      worst,
      drought: { FI_SW: droughtBy("FI_SW"), SE_SKANE: droughtBy("SE_SKANE") } as Record<Region, number | undefined>,
    };
  }, [farms.data, sim.data, year, cells]);

  const active = [sim, farms, geoParcels, geoFarms, weather];
  return {
    parcels, colorOf, trigger: [colorBy, farms.data, cropBand, weather.data], stats, sim, pins,
    farmChange, farmRisk, farmRegion, bandOf, cellOf,
    pending: active.some((q) => q.isLoading), error: active.find((q) => q.error)?.error ?? null,
  };
}
