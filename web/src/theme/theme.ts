// Appearance: the user's preference (system / light / dark; light when nothing is stored) and the resolved theme
// written to <html data-theme>.
// index.html runs the same resolution inline before first paint, so there is no flash.
import { create } from "zustand";

export type ThemePref = "system" | "light" | "dark";
export type Theme = "light" | "dark";

const KEY = "fr-theme";
const media = typeof window !== "undefined" ? window.matchMedia("(prefers-color-scheme: dark)") : null;

function readPref(): ThemePref {
  try {
    const v = localStorage.getItem(KEY);
    return v === "system" || v === "dark" ? v : "light";
  } catch { return "light"; }
}
const resolve = (p: ThemePref): Theme => (p === "system" ? (media?.matches ? "dark" : "light") : p);
const apply = (t: Theme) => { document.documentElement.dataset.theme = t; };

type S = { pref: ThemePref; theme: Theme; setPref: (p: ThemePref) => void };

export const useTheme = create<S>((set, get) => {
  const pref = readPref();
  const theme = resolve(pref);
  apply(theme);
  media?.addEventListener("change", () => {
    if (get().pref !== "system") return;
    const t = resolve("system"); apply(t); set({ theme: t });
  });
  return {
    pref, theme,
    setPref: (p) => {
      try { localStorage.setItem(KEY, p); } catch { /* private mode */ }
      const t = resolve(p); apply(t); set({ pref: p, theme: t });
    },
  };
});
