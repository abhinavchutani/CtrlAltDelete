// UI state only (what is selected / shown). Server data lives in react-query (api/hooks.ts).
// The map camera is NOT here: MapLibre owns it, so panning never re-renders React. To move the map, call
// flyTo(); MapView watches `camera.seq` and animates there.
import { create } from "zustand";
import type { Climate, Lever, Region, ScenarioSpec } from "../api/types";

export type Tab = "overview" | "map" | "assistant";
export type Lens = "overall" | "drought" | "heat" | "rain";
export type Mode = "ask" | "simulate" | "teach";
export type SheetKind = "issues" | "money" | "plans";
export type ParcelPick = { parcel_id: string; farm_id: string; area_ha: number; crop?: string | null; ring: [number, number][] };
export type View = { longitude: number; latitude: number; zoom: number };
/** One turn in the assistant. `context` carries what the user came from (a farm, a year, an issue). */
export type Turn = {
  id: number; mode: Mode; text: string; history: string[];
  context?: { farmId?: string; year?: number; issueId?: string; gap?: string };
};

export const START_YEAR = 2026;
export const HORIZON = 2040; // every view shows the same 15 seasons
export const HOME_VIEW: View = { longitude: 13.33, latitude: 55.85, zoom: 11.6 }; // the densest Skåne cluster
export const REGION_VIEW: Record<Region, View> = {
  FI_SW: { longitude: 22.2, latitude: 61.11, zoom: 11.6 },
  SE_SKANE: HOME_VIEW,
};
export const CLIMATES: { key: Climate; label: string; path: string }[] = [
  { key: "ssp126", label: "Low emissions", path: "low-emissions weather path" },
  { key: "ssp245", label: "Middle", path: "middle weather path" },
  { key: "ssp585", label: "High emissions", path: "high-emissions weather path" },
];
export const climatePath = (c: Climate) => CLIMATES.find((x) => x.key === c)?.path ?? "middle weather path";

type State = {
  tab: Tab;
  climate: Climate;
  /** Set → the map shows this plan (simulated via /api/simulate); null → today's plan (the preset). */
  planLevers: Lever[] | null;
  planLabel: string | null;
  year: number;
  playing: boolean;
  lens: Lens;
  camera: { target: View; seq: number };
  selectedParcel: ParcelPick | null;
  planSheetOpen: boolean;
  sheet: { kind: SheetKind; from: DOMRect | null; issueId?: string } | null;
  mode: Mode;
  turns: Turn[];
  draft: string;
  litNodes: string[]; // the knowledge-graph nodes the latest answer used
  newNodes: string[]; // notes filed this session (shown with a "New" pill)
  tourOpen: boolean;
};

type Actions = {
  setTab: (t: Tab) => void;
  setClimate: (c: Climate) => void;
  showPlan: (levers: Lever[] | null, label?: string | null) => void;
  setYear: (y: number) => void;
  setPlaying: (p: boolean) => void;
  setLens: (l: Lens) => void;
  flyTo: (v: View) => void;
  selectParcel: (p: ParcelPick | null) => void;
  setPlanSheet: (open: boolean) => void;
  openSheet: (kind: SheetKind, from?: DOMRect | null, issueId?: string) => void;
  closeSheet: () => void;
  setMode: (m: Mode) => void;
  setDraft: (d: string) => void;
  send: (text: string, mode?: Mode, context?: Turn["context"]) => void;
  /** Go to the assistant with a prompt ready in the composer (the user still presses send). */
  prefill: (mode: Mode, text: string) => void;
  light: (ids: string[]) => void;
  markNew: (id: string) => void;
  setTourOpen: (open: boolean) => void;
};

const hashTab = (): Tab => {
  const h = typeof window === "undefined" ? "" : window.location.hash.slice(1);
  return h === "map" || h === "assistant" ? h : "overview";
};

export const useStore = create<State & Actions>((set) => ({
  tab: hashTab(),
  climate: "ssp245",
  planLevers: null,
  planLabel: null,
  year: START_YEAR,
  playing: false,
  lens: "overall",
  camera: { target: HOME_VIEW, seq: 0 },
  selectedParcel: null,
  planSheetOpen: false,
  sheet: null,
  mode: "ask",
  turns: [],
  draft: "",
  litNodes: [],
  newNodes: [],
  tourOpen: false,
  setTab: (tab) => set({ tab, sheet: null }),
  setClimate: (climate) => set({ climate, planLevers: null, planLabel: null, playing: false }),
  showPlan: (planLevers, planLabel = null) => set({ planLevers, planLabel }),
  setYear: (year) => set({ year }),
  setPlaying: (playing) => set({ playing }),
  setLens: (lens) => set({ lens }),
  flyTo: (target) => set((s) => ({ camera: { target, seq: s.camera.seq + 1 } })),
  selectParcel: (selectedParcel) => set({ selectedParcel }),
  setPlanSheet: (planSheetOpen) => set({ planSheetOpen }),
  openSheet: (kind, from = null, issueId) => set({ sheet: { kind, from, issueId } }),
  closeSheet: () => set({ sheet: null }),
  setMode: (mode) => set({ mode }),
  setDraft: (draft) => set({ draft }),
  send: (text, mode, context) => set((s) => ({
    turns: [...s.turns, { id: Date.now(), mode: mode ?? s.mode, text, context,
      history: s.turns.filter((t) => t.mode === "ask").map((t) => t.text).slice(-5) }],
    mode: mode ?? s.mode, draft: "", tab: "assistant",
  })),
  prefill: (mode, draft) => set({ tab: "assistant", mode, draft, sheet: null }),
  light: (litNodes) => set({ litNodes }),
  markNew: (id) => set((s) => ({ newNodes: [...new Set([...s.newNodes, id])] })),
  setTourOpen: (tourOpen) => set({ tourOpen }),
}));

/** The spec the map and season strip show: today's plan or the chosen plan, always 2026–2040. */
export const activeSpec = (s: Pick<State, "climate" | "planLevers" | "planLabel">): ScenarioSpec | null =>
  s.planLevers ? { climate: s.climate, horizon_end: HORIZON, levers: s.planLevers, label: s.planLabel } : null;
