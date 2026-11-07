// UI state only (what is selected / shown). Server data lives in react-query (api/hooks.ts).
// The map camera is NOT here: MapLibre owns it, so panning never re-renders React. To move the map, call
// flyTo(); MapView watches `camera.seq` and animates there.
import { create } from "zustand";
import type { Alert, Region, ScenarioSpec } from "../api/types";

export type MapLayer = "parcels" | "farms" | "weather";
export type ColorBy = "health" | "drought" | "heat";
export type Tab = "overview" | "map";
export type ChatMsg = { id: number; text: string; history: string[]; kind?: "search" };
export type ParcelPick = { parcel_id: string; farm_id: string; area_ha: number; crop?: string | null; ring: [number, number][] };
export type Door = "ask" | "simulate";
export type View = { longitude: number; latitude: number; zoom: number };

export const START_YEAR = 2026;
export const HOME_VIEW: View = { longitude: 13.33, latitude: 55.85, zoom: 11.6 }; // the densest Skåne cluster
export const REGION_VIEW: Record<Alert["region"], View> = {
  FI_SW: { longitude: 22.2, latitude: 61.11, zoom: 11.6 },
  SE_SKANE: HOME_VIEW,
};

type State = {
  tab: Tab;
  scenarioId: string; // a preset id
  customSpec: ScenarioSpec | null; // set → the active scenario is POST /api/simulate(customSpec)
  pendingSpec: ScenarioSpec | null; // heard from voice/text, waiting for the user's confirm
  heard: string[];
  problems: string[];
  year: number;
  playing: boolean;
  layer: MapLayer;
  camera: { target: View; seq: number }; // a fly-to request, not the live camera
  selectedAlert: Alert | null;
  door: Door;
  question: string | null;
  askHistory: string[]; // earlier questions, oldest first (sent as history so "make that a report" works)
  boardDialogRow: string | null;
  colorBy: ColorBy;
  selectedParcel: ParcelPick | null;
  watched: string[];
  chat: ChatMsg[];
  tourOpen: boolean;
  assistantOpen: boolean; // the assistant floats over whatever tab is open
  viewRegion: Region; // the region the map is looking at (updated when a move ends)
  weatherFx: boolean; // rain / heat / drought effects on the map
};

type Actions = {
  setTab: (t: Tab) => void;
  pickPreset: (id: string) => void;
  runSpec: (spec: ScenarioSpec) => void;
  resetSpec: () => void;
  setPending: (spec: ScenarioSpec | null, heard?: string[], problems?: string[]) => void;
  setYear: (y: number) => void;
  setPlaying: (p: boolean) => void;
  setLayer: (l: MapLayer) => void;
  flyTo: (v: View) => void;
  selectAlert: (a: Alert | null) => void;
  ask: (q: string) => void;
  setDoor: (d: Door) => void;
  openDecision: (rowId: string | null) => void;
  setColorBy: (c: ColorBy) => void;
  selectParcel: (p: ParcelPick | null) => void;
  toggleWatch: (parcelId: string) => void;
  sendChat: (text: string, kind?: "search") => void;
  setTourOpen: (open: boolean) => void;
  setAssistantOpen: (open: boolean) => void;
  setViewRegion: (r: Region) => void;
  setWeatherFx: (on: boolean) => void;
};

export const useStore = create<State & Actions>((set) => ({
  tab: "overview",
  scenarioId: "current_plan_ssp245",
  customSpec: null,
  pendingSpec: null,
  heard: [],
  problems: [],
  year: START_YEAR,
  playing: false,
  layer: "parcels",
  camera: { target: HOME_VIEW, seq: 0 },
  selectedAlert: null,
  door: "simulate",
  question: null,
  askHistory: [],
  boardDialogRow: null,
  colorBy: "health",
  selectedParcel: null,
  watched: [],
  chat: [],
  tourOpen: false,
  assistantOpen: false,
  viewRegion: "SE_SKANE",
  weatherFx: true,
  setTab: (tab) => set({ tab }),
  pickPreset: (id) => set({ scenarioId: id, customSpec: null, selectedAlert: null, playing: false }),
  runSpec: (spec) => set({ customSpec: spec, pendingSpec: null, selectedAlert: null, door: "simulate", tab: "map", assistantOpen: false }),
  resetSpec: () => set({ customSpec: null, selectedAlert: null }),
  setPending: (spec, heard = [], problems = []) => set({ pendingSpec: spec, heard, problems, door: "simulate" }),
  setYear: (year) => set({ year }),
  setPlaying: (playing) => set({ playing }),
  setLayer: (layer) => set({ layer }),
  flyTo: (target) => set((s) => ({ camera: { target, seq: s.camera.seq + 1 } })),
  // MapView centres on the alert's pin once that year's farms are loaded
  selectAlert: (a) => set(a ? { selectedAlert: a, year: a.year, playing: false, selectedParcel: null } : { selectedAlert: null }),
  ask: (question) =>
    set((s) => ({
      question, door: "ask",
      askHistory: s.question && s.question !== question ? [...s.askHistory, s.question].slice(-5) : s.askHistory,
    })),
  setDoor: (door) => set({ door }),
  openDecision: (boardDialogRow) => set({ boardDialogRow }),
  setColorBy: (colorBy) => set({ colorBy }),
  selectParcel: (selectedParcel) => set(selectedParcel ? { selectedParcel, selectedAlert: null } : { selectedParcel }),
  toggleWatch: (id) => set((s) => ({ watched: s.watched.includes(id) ? s.watched.filter((w) => w !== id) : [...s.watched, id] })),
  // each chat question remembers the questions before it, so follow-ups ("make that a report") resolve
  sendChat: (text, kind) => set((s) => ({
    chat: [...s.chat, { id: Date.now(), text, history: s.chat.map((m) => m.text).slice(-5), kind }],
    assistantOpen: true,
  })),
  setTourOpen: (tourOpen) => set({ tourOpen }),
  setAssistantOpen: (assistantOpen) => set({ assistantOpen }),
  setViewRegion: (viewRegion) => set({ viewRegion }),
  setWeatherFx: (weatherFx) => set({ weatherFx }),
}));
