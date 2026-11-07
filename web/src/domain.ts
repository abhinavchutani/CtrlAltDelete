// Pure helpers: labels, ordering and lookups the components render. No React here.
import type { Alert, EurBand, Lever, RegionYear, ScenarioSpec } from "./api/types";

export const EUR_BANDS: EurBand[] = ["< €50k", "€50–100k", "€100–250k", "€250k–1M", "> €1M"];
export const bandIndex = (b: EurBand) => EUR_BANDS.indexOf(b);

export const CLIMATE_LABEL: Record<ScenarioSpec["climate"], string> = {
  ssp126: "low emissions (SSP1-2.6)",
  ssp245: "middle path (SSP2-4.5)",
  ssp585: "high emissions (SSP5-8.5)",
};
export const HAZARD_LABEL: Record<string, string> = {
  H1: "drought", H2: "heat at flowering", H3: "waterlogging", H4: "harvest rain", H5: "season length", H6: "blight", H7: "pollen beetle",
};

export function leverLabel(l: Lever): string {
  switch (l.type) {
    case "irrigate":
      return `irrigate ${l.target === "all" ? "all" : "dry"} ${l.crop} fields`;
    case "earlier_sowing":
      return `earlier sowing (${l.crop ?? "all"})`;
    case "region_split":
      return `${l.crop ?? "pea"} split ${Math.round(l.fi_share * 100)} % Finland`;
    case "heat_tolerant_variety":
      return `heat-tolerant ${l.crop ?? "pea"} from ${l.from_year ?? 2030} (assumption: −${Math.round((l.penalty_cut ?? 0.3) * 100)} % heat penalty)`;
    case "crop_area":
      return `${l.crop} area ${l.change_pct > 0 ? "+" : ""}${l.change_pct} % in ${l.region}`;
  }
}

export const specChips = (s: ScenarioSpec): string[] => [
  `climate: ${CLIMATE_LABEL[s.climate ?? "ssp245"]}`,
  `to ${s.horizon_end ?? 2040}`,
  ...(s.levers ?? []).map(leverLabel),
];

/** Replace a lever of the same type (one lever per type keeps the spec readable) or add it. */
export function withLever(spec: ScenarioSpec, lever: Lever): ScenarioSpec {
  const rest = (spec.levers ?? []).filter((l) => l.type !== lever.type);
  return { ...spec, levers: [...rest, lever], label: null };
}
export const withoutLever = (spec: ScenarioSpec, i: number): ScenarioSpec => ({
  ...spec, levers: (spec.levers ?? []).filter((_, j) => j !== i), label: null,
});

export const regionYear = (rows: RegionYear[], year: number) => rows.filter((r) => r.year === year);
export const alertsByYear = (alerts: Alert[]) => {
  const m = new Map<number, Alert[]>();
  for (const a of alerts) m.set(a.year, [...(m.get(a.year) ?? []), a]);
  return m;
};
