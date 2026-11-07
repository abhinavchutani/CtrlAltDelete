// The lever editor's form model → a contract Lever. Ranges mirror src/p_spec.py BOUNDS.
import type { Lever } from "../../api/types";

export type LeverType = Lever["type"];
export const LEVER_TYPES: LeverType[] = ["irrigate", "earlier_sowing", "region_split", "heat_tolerant_variety", "crop_area"];
export type LeverForm = { type: LeverType; crop: string; region: "FI_SW" | "SE_SKANE"; value: number; fromYear: number; target: "drought_exposed" | "all" };
export const DEFAULT_FORM: LeverForm = { type: "irrigate", crop: "pea", region: "FI_SW", value: 0.7, fromYear: 2030, target: "drought_exposed" };
export const RANGE: Partial<Record<LeverType, { min: number; max: number; step: number; label: string }>> = {
  region_split: { min: 0.2, max: 0.9, step: 0.05, label: "Finland share" },
  heat_tolerant_variety: { min: 0, max: 0.6, step: 0.05, label: "heat-penalty cut (assumption)" },
  crop_area: { min: -50, max: 50, step: 5, label: "area change %" },
};

export function toLever(f: LeverForm): Lever {
  switch (f.type) {
    case "irrigate": return { type: "irrigate", crop: f.crop === "potato" ? "potato" : "pea", target: f.target };
    case "earlier_sowing": return { type: "earlier_sowing", crop: f.crop as never };
    case "region_split": return { type: "region_split", crop: "pea", fi_share: f.value };
    case "heat_tolerant_variety": return { type: "heat_tolerant_variety", crop: "pea", from_year: f.fromYear, penalty_cut: f.value };
    case "crop_area": return { type: "crop_area", crop: f.crop as never, region: f.region, change_pct: f.value };
  }
}

export const defaultValue = (t: LeverType) => (t === "region_split" ? 0.7 : t === "heat_tolerant_variety" ? 0.3 : t === "crop_area" ? -10 : 0);
