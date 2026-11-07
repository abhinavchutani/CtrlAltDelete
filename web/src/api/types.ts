// Friendly names for the generated contract types (types.gen.ts comes from api/schemas.py; never hand-edit it).
import type { components } from "./types.gen";

type S = components["schemas"];
export type ScenarioSpec = S["ScenarioSpec"];
export type ScenarioPreset = S["ScenarioPreset"];
export type SimResult = S["SimResult"];
export type Alert = S["Alert"];
export type RegionYear = S["RegionYear"];
export type Meters = S["Meters"];
export type BetterOption = S["BetterOption"];
export type FarmYear = S["FarmYear"];
export type WeatherFrame = S["WeatherFrame"];
export type WeatherCell = S["WeatherCell"];
export type Hedge = S["Hedge"];
export type HedgePoint = S["HedgePoint"];
export type PathwayItem = S["PathwayItem"];
export type AdaptationOption = S["AdaptationOption"];
export type BoardRow = S["BoardRow"];
export type Decision = S["Decision"];
export type AskOut = S["AskOut"];
export type IntentOut = S["IntentOut"];
export type EvidenceRef = S["EvidenceRef"];
export type Health = S["Health"];
export type Lever = NonNullable<Alert["suggested_lever"]>;
export type Climate = ScenarioSpec["climate"];
export type Region = RegionYear["region"];
export type EurBand = RegionYear["eur_at_risk"];
export type Hazard = NonNullable<Alert["hazard"]>;

export type Table = { columns: string[]; rows: (string | number | null)[][] };
export type ReportRef = { report_id: string; filename: string; url: string };

export type GeoPoint = { type: "Feature"; geometry: { type: "Point"; coordinates: [number, number] }; properties: { farm_id: string; region: Region } };
export type GeoParcel = {
  type: "Feature";
  geometry: { type: "Polygon"; coordinates: [number, number][][] };
  properties: { parcel_id: string; farm_id: string; area_ha: number; crop?: string | null };
};
export type FeatureCollection<F> = { type: "FeatureCollection"; features: F[] };

// UI v3
export type Provenance = S["Provenance"];
export type MonthsFrame = S["MonthsFrame"];
export type MonthWeather = S["MonthWeather"];
export type CostLevel = AdaptationOption["cost_level"];
/** One simulated plan in the /api/search stream (api/schemas.py PlanCandidate; streamed, so not in the OpenAPI). */
export type PlanFuture = { vs_current_plan: "better" | "same" | "worse"; eur_at_risk_per_year: EurBand; saves: EurBand | null };
export type PlanCandidate = {
  id: string; label: string; levers: Lever[]; phase: "single" | "combo" | "stress";
  eur_at_risk_per_year: EurBand; saves: EurBand | null; vs_current_plan: "better" | "same" | "worse";
  costly_years: number; worst_year: EurBand; plan_costly_years: number;
  co2e_direction: "lower" | "same" | "higher"; assumption: boolean; futures?: Record<string, PlanFuture>;
};
export type PlanBaseline = { eur_at_risk_per_year: EurBand; costly_years: number; worst_year: EurBand };
export type SearchEvent =
  | { type: "start"; climate: Climate; horizon_end: number; total: number; years: number; plan: PlanBaseline }
  | { type: "candidate"; done: number; total: number; candidate: PlanCandidate }
  | { type: "phase"; phase: "combo"; total: number; helped: string[] }
  | { type: "stress"; id: string; futures: Record<string, PlanFuture> }
  | { type: "done"; ranking: string[]; best: string | null; tested: number; seconds: number }
  | { type: "error"; detail: string };
