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
