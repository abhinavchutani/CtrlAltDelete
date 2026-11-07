// Words and lookups for simulated plans (no numbers are made here: bands and counts come from the API).
import type { AdaptationOption, CostLevel, Lever, PlanCandidate } from "../../api/types";

export const COST_ORDER: CostLevel[] = ["low", "low_med", "med", "high"];
export const COST_LABEL: Record<CostLevel, string> = { low: "Low cost", low_med: "Low–medium cost", med: "Medium cost", high: "High cost" };
export const FUTURE_LABEL: Record<string, string> = { ssp126: "Low emissions", ssp245: "Middle path", ssp585: "High emissions" };

/** A plan's cost level: the dearest of its changes, as the knowledge base rates that kind of change. */
export function planCost(levers: Lever[], options: AdaptationOption[] | undefined): CostLevel | null {
  if (!options) return null;
  let worst: CostLevel | null = null;
  for (const lv of levers) {
    const o = options.find((x) => x.lever?.type === lv.type);
    if (o && (!worst || COST_ORDER.indexOf(o.cost_level) > COST_ORDER.indexOf(worst))) worst = o.cost_level;
  }
  return worst;
}

/** "Holds in both other futures", "holds in 1 of 2", or null before the stress test ran. */
export function holds(c: PlanCandidate): { ok: number; of: number } | null {
  if (!c.futures) return null;
  const v = Object.values(c.futures);
  return { ok: v.filter((f) => f.vs_current_plan === "better").length, of: v.length };
}
