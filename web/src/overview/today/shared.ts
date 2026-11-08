// Words and day arithmetic for the Today widgets. No numbers are made here: every value comes from /api/radar/today.
import { useLayoutEffect, useRef, useState } from "react";
import type { RegionDay, StageName, Today, TodayCrop } from "../../api/types";
import { REGION_NAME } from "../../components/ui";

export const CROP_NAME: Record<TodayCrop, string> = {
  pea: "pea", potato: "potato", spinach: "spinach", carrot: "carrot", turnip_rape: "turnip rape",
};
export const STAGE_WORD: Record<RegionDay["stage"], string> = {
  not_sown: "not sown yet", sown: "growing", flowering: "flowering", fill: "filling pods", harvest: "harvested",
};
export const STAGE_SHORT: Record<StageName, string> = { sown: "Sown", flowering: "Flowering", fill: "Fill", harvest: "Harvest" };

const DAY = 86_400_000;
const utc = (iso: string) => Date.UTC(+iso.slice(0, 4), +iso.slice(5, 7) - 1, +iso.slice(8, 10));
/** Days since 1 April of the same year (the season's day 0). */
export const seasonDay = (iso: string) => Math.round((utc(iso) - Date.UTC(+iso.slice(0, 4), 3, 1)) / DAY);
export const addDays = (iso: string, n: number) => new Date(utc(iso) + n * DAY).toISOString().slice(0, 10);
export const SEASON_DAYS = 214; // 1 Apr – 31 Oct

export const longDate = (iso: string) =>
  new Date(utc(iso)).toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
export const shortDate = (iso: string) =>
  new Date(utc(iso)).toLocaleDateString("en-GB", { day: "numeric", month: "short", timeZone: "UTC" });

export const ordinal = (n: number) => {
  const s = n % 100 >= 11 && n % 100 <= 13 ? "th" : ({ 1: "st", 2: "nd", 3: "rd" } as Record<number, string>)[n % 10] ?? "th";
  return `${n}${s}`;
};
export const pct = (x: number) => `${Math.round(100 * x)}%`;

/** How many of the 30 normal years sit below today's value ("drier than 27 of 30"). */
export const below = (value: number, normal: number[]) => normal.filter((v) => v < value).length;

/** "Skåne pea flowering · SW Finland pea growing" for the page title. */
export const stageLine = (t: Today) =>
  t.regions.map((r) => `${REGION_NAME[r.region]} ${CROP_NAME[r.crop]} ${STAGE_WORD[r.stage]}`).join(" · ");

const SSP: Record<string, string> = { ssp126: "SSP1-2.6", ssp245: "SSP2-4.5", ssp585: "SSP5-8.5" };
export const pathNote = (t: Today) =>
  t.path === "historical" ? "Twin weather (synthetic), not a forecast" : `One simulated ${SSP[t.path]} weather path, not a forecast`;

/** The rendered width of an element, so charts draw in real pixels (no stretched dots or labels). */
export function useWidth<T extends HTMLElement>(fallback = 360) {
  const ref = useRef<T>(null);
  const [w, setW] = useState(fallback);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(([e]) => setW(Math.max(120, Math.round(e.contentRect.width))));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, w] as const;
}
