// Frontier geometry: FI share on x, € band index on y (bands are ordinal, never exact €).
import type { HedgePoint } from "../../api/types";
import { bandIndex, EUR_BANDS } from "../../domain";

export const W = 360, H = 180, PAD = 34;
export const xOf = (share: number) => PAD + share * (W - 2 * PAD);
export const yOf = (bandIdx: number) => H - PAD - (bandIdx / (EUR_BANDS.length - 1)) * (H - 2 * PAD);
export const path = (pts: HedgePoint[], key: "expected_loss" | "tail_loss") =>
  pts.map((p, i) => `${i ? "L" : "M"}${xOf(p.fi_share).toFixed(1)},${yOf(bandIndex(p[key])).toFixed(1)}`).join(" ");
