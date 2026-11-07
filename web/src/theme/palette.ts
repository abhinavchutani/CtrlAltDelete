// deck.gl needs RGB arrays; read them from tokens.css so the map restyles with the theme.
export type RGB = [number, number, number];
export type Palette = Record<"good" | "neutral" | "bad" | "wet" | "dry" | "farm", RGB>;

const FALLBACK: Palette = {
  good: [46, 125, 50], neutral: [224, 224, 224], bad: [198, 40, 40], wet: [21, 101, 192], dry: [161, 82, 12], farm: [55, 71, 79],
};

function hex(v: string): RGB | null {
  const m = /^#?([0-9a-f]{6})$/i.exec(v.trim());
  if (!m) return null;
  const n = parseInt(m[1], 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

export function readPalette(el: Element = document.documentElement): Palette {
  const css = getComputedStyle(el);
  const out = { ...FALLBACK };
  for (const k of Object.keys(FALLBACK) as (keyof Palette)[]) out[k] = hex(css.getPropertyValue(`--map-${k}`)) ?? FALLBACK[k];
  return out;
}

/** Linear blend a → b, t in 0..1. */
export const mix = (a: RGB, b: RGB, t: number): RGB => {
  const c = Math.max(0, Math.min(1, t));
  return [0, 1, 2].map((i) => Math.round(a[i] + (b[i] - a[i]) * c)) as RGB;
};

/** Diverging colour for a % change vs baseline: −30 % → bad, 0 → neutral, +30 % → good. */
export const changeColor = (p: Palette, pct: number | undefined): RGB =>
  pct === undefined ? p.neutral : pct < 0 ? mix(p.neutral, p.bad, -pct / 30) : mix(p.neutral, p.good, pct / 30);
