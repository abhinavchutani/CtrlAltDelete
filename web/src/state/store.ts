// UI state only (what is selected / shown). Server data lives in react-query (api/hooks.ts).
import { create } from "zustand";
import type { Alert, ScenarioSpec } from "../api/types";

export type MapLayer = "parcels" | "farms" | "weather";
export type ColorBy = "health" | "risk" | "drought" | "heat";
export type Drawer = "none" | "insights" | "decisions";
export type ChatMode = "collapsed" | "docked" | "max";
export type ChatMsg = { id: number; text: string; history: string[] };
export type ParcelPick = { parcel_id: string; farm_id: string; area_ha: number; ring: [number, number][] };
export type Door = "ask" | "simulate";
export type View = { longitude: number; latitude: number; zoom: number; pitch: number; bearing: number };

export const START_YEAR = 2026;
export const VIEW_ALL: View = { longitude: 17.8, latitude: 58.2, zoom: 4.6, pitch: 35, bearing: 0 };
export const REGION_VIEW: Record<Alert["region"], View> = {
  FI_SW: { longitude: 22.4, latitude: 60.6, zoom: 7.2, pitch: 40, bearing: 0 },
  SE_SKANE: { longitude: 13.5, latitude: 55.9, zoom: 7.6, pitch: 40, bearing: 0 },
};

type State = {
  scenarioId: string; // a preset id
  customSpec: ScenarioSpec | null; // set → the active scenario is POST /api/simulate(customSpec)
  pendingSpec: ScenarioSpec | null; // heard from voice/text, waiting for the user's confirm
  heard: string[];
  problems: string[];
  year: number;
  playing: boolean;
  layer: MapLayer;
  view: View;
  selectedAlert: Alert | null;
  door: Door;
  question: string | null;
  askHistory: string[]; // earlier questions, oldest first (sent as history so "make that a report" works)
  boardDialogRow: string | null;
  colorBy: ColorBy;
  selectedParcel: ParcelPick | null;
  watched: string[];
  drawer: Drawer;
  chatMode: ChatMode;
  chat: ChatMsg[];
};

type Actions = {
  pickPreset: (id: string) => void;
  runSpec: (spec: ScenarioSpec) => void;
  setPending: (spec: ScenarioSpec | null, heard?: string[], problems?: string[]) => void;
  setYear: (y: number) => void;
  setPlaying: (p: boolean) => void;
  setLayer: (l: MapLayer) => void;
  setView: (v: View) => void;
  selectAlert: (a: Alert | null) => void;
  ask: (q: string) => void;
  setDoor: (d: Door) => void;
  openDecision: (rowId: string | null) => void;
  setColorBy: (c: ColorBy) => void;
  selectParcel: (p: ParcelPick | null) => void;
  toggleWatch: (parcelId: string) => void;
  setDrawer: (d: Drawer) => void;
  setChatMode: (m: ChatMode) => void;
  sendChat: (text: string) => void;
};

export const useStore = create<State & Actions>((set) => ({
  scenarioId: "current_plan_ssp245",
  customSpec: null,
  pendingSpec: null,
  heard: [],
  problems: [],
  year: START_YEAR,
  playing: false,
  layer: "parcels",
  view: { longitude: 13.45, latitude: 55.95, zoom: 11.5, pitch: 0, bearing: 0 },
  selectedAlert: null,
  door: "simulate",
  question: null,
  askHistory: [],
  boardDialogRow: null,
  pickPreset: (id) => set({ scenarioId: id, customSpec: null, selectedAlert: null, year: START_YEAR, playing: false }),
  runSpec: (spec) => set({ customSpec: spec, pendingSpec: null, selectedAlert: null, door: "simulate" }),
  setPending: (spec, heard = [], problems = []) => set({ pendingSpec: spec, heard, problems, door: "simulate" }),
  setYear: (year) => set({ year }),
  setPlaying: (playing) => set({ playing }),
  setLayer: (layer) => set({ layer }),
  setView: (view) => set({ view }),
  selectAlert: (a) => set(a ? { selectedAlert: a, year: a.year, view: REGION_VIEW[a.region], playing: false } : { selectedAlert: null }),
  ask: (question) =>
    set((s) => ({
      question, door: "ask",
      askHistory: s.question && s.question !== question ? [...s.askHistory, s.question].slice(-5) : s.askHistory,
    })),
  setDoor: (door) => set({ door }),
  openDecision: (boardDialogRow) => set({ boardDialogRow }),
  colorBy: "health",
  selectedParcel: null,
  watched: [],
  drawer: "none",
  chatMode: "docked",
  chat: [],
  setColorBy: (colorBy) => set({ colorBy }),
  selectParcel: (selectedParcel) => set({ selectedParcel }),
  toggleWatch: (id) => set((s) => ({ watched: s.watched.includes(id) ? s.watched.filter((w) => w !== id) : [...s.watched, id] })),
  setDrawer: (drawer) => set((s) => ({ drawer: s.drawer === drawer ? "none" : drawer })),
  setChatMode: (chatMode) => set({ chatMode }),
  // each chat question remembers the questions before it, so follow-ups ("make that a report") resolve
  sendChat: (text) => set((s) => ({
    chat: [...s.chat, { id: Date.now(), text, history: s.chat.map((m) => m.text).slice(-5) }],
    chatMode: s.chatMode === "collapsed" ? "docked" : s.chatMode,
  })),
}));
