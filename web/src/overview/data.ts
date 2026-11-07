// Shared Overview data: the outlook (today's plan) and the plan finder's best plan for the chosen climate path.
// No numbers are made here; everything comes from /api/radar/outlook and the /api/search stream.
import { useEffect } from "react";
import { useOutlook } from "../api/hooks";
import type { Bucket, Issue, PlanCandidate, Region, Season, Status } from "../api/types";
import { useSearch } from "../state/search";
import { HORIZON, useStore } from "../state/store";

export const BUCKET_LABEL: Record<Bucket, string> = { lt100k: "under €100k", "100k_250k": "€100–250k", "250k_plus": "€250k+" };
export const BUCKET_LEVEL: Record<Bucket, number> = { lt100k: 1, "100k_250k": 2, "250k_plus": 3 };
export const WORDS = ["no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve",
  "thirteen", "fourteen", "fifteen"];
export const word = (n: number) => WORDS[n] ?? String(n);
export const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

/** The best plan for the chosen climate path; starts (or joins) the plan finder run. */
export function useBestPlan() {
  const climate = useStore((s) => s.climate);
  const s = useSearch();
  useEffect(() => { void s.start(climate, HORIZON); }, [climate]); // eslint-disable-line react-hooks/exhaustive-deps
  const mine = s.key === `${climate}:${HORIZON}`;
  const best: PlanCandidate | null = mine && s.best ? s.candidates[s.best] ?? null : null;
  return { status: mine ? s.status : "running", best, tested: mine ? Object.keys(s.candidates).length : 0,
    done: mine ? s.done : 0, total: mine ? s.total : 0, error: s.error };
}

export function useTodayOutlook() {
  const climate = useStore((s) => s.climate);
  return useOutlook(climate, null);
}

export const marksByYear = (issues: Issue[]): Record<number, Status[]> => {
  const m: Record<number, Status[]> = {};
  for (const i of issues) (m[i.year] ??= []).push(i.status);
  return m;
};
export const seasonMarks = (seasons: Season[]): Record<number, Status[]> =>
  Object.fromEntries(seasons.map((s) => [s.year, [s.status]]));

/** The region most issues of a type fall in ("SW Finland farms hit hardest"). */
export function mostlyIn(issues: Issue[]): Region | null {
  const n = new Map<Region, number>();
  for (const i of issues) n.set(i.region, (n.get(i.region) ?? 0) + 1);
  return [...n.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] ?? null;
}

export const TYPE_LABEL: Record<string, string> = { drought: "Drought at flowering", heat: "Heat at flowering" };
export const typeLabel = (t: string) => TYPE_LABEL[t] ?? cap(t.replace(/_/g, " "));
const MONTH = ["", "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

/** The issue's headline, in words chosen from its numbers (thresholds stated here, nothing invented). */
export function issueHeadline(i: Issue): string {
  const m = i.month ? MONTH[i.month] : "season";
  if (i.type === "drought") {
    const r = i.rain_vs_normal_pct ?? 0;
    const dry = r <= -50 ? "A very dry" : r <= -20 ? "A dry" : "A dry spell in";
    return i.crop === "pea" ? `${dry} ${m} hits peas as they flower` : `${dry} ${m} hits ${i.crop || "the crop"} as it flowers`;
  }
  if (i.type === "heat") return `Heat at flowering cuts ${i.crop === "pea" ? "pea" : i.crop || "crop"} yields in ${m}`;
  return `${typeLabel(i.type)} in ${m}`;
}
