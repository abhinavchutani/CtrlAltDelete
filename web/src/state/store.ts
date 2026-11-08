// UI state only (what is selected / shown). Server data lives in react-query (api/hooks.ts).
import { create } from "zustand";
import type { Climate, Filed } from "../api/types";

export type Tab = "overview" | "assistant";
export type Mode = "ask" | "simulate" | "teach";
export type SheetKind = "issues" | "money" | "plans" | "farms-near" | "farms-repeat";
/** One turn in the assistant. `context` carries what the user came from (a gap to fill). */
export type Turn = { id: number; mode: Mode; text: string; history: string[]; context?: { gap?: string } };

export const START_YEAR = 2026; // the last season with observed weather
export const HORIZON = 2040; // every view shows the same 15 seasons
export const CLIMATES: { key: Climate; label: string; path: string }[] = [
  { key: "ssp126", label: "Low emissions", path: "low-emissions weather path" },
  { key: "ssp245", label: "Middle", path: "middle weather path" },
  { key: "ssp585", label: "High emissions", path: "high-emissions weather path" },
];
export const climatePath = (c: Climate) => CLIMATES.find((x) => x.key === c)?.path ?? "middle weather path";

type State = {
  tab: Tab;
  climate: Climate;
  sheet: { kind: SheetKind; from: DOMRect | null; issueId?: string } | null;
  mode: Mode;
  turns: Turn[];
  draft: string;
  litNodes: string[]; // the knowledge-graph nodes the latest answer used
  newNodes: string[]; // notes filed this session (shown with a "New" pill)
  tourOpen: boolean;
  filing: { f: Filed; at: number } | null; // the latest filed note, played as an animation in the graph
  focus: string | null; // the graph node whose drawer is open
  graphOpen: boolean; // "Adaptive database" beside the chat; hidden by default so the chat has the room
  litUnseen: boolean; // an answer lit graph nodes while the graph was hidden (badge on the toggle)
};

type Actions = {
  setTab: (t: Tab) => void;
  setClimate: (c: Climate) => void;
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
  playFiling: (f: Filed | null) => void;
  setFocus: (id: string | null) => void;
  setGraphOpen: (open: boolean) => void;
};

const hashTab = (): Tab => (typeof window !== "undefined" && window.location.hash.slice(1) === "assistant" ? "assistant" : "overview");


export const useStore = create<State & Actions>((set) => ({
  tab: hashTab(),
  climate: "ssp245",
  sheet: null,
  mode: "ask",
  turns: [],
  draft: "",
  litNodes: [],
  newNodes: [],
  tourOpen: false,
  filing: null,
  focus: null,
  graphOpen: false,
  litUnseen: false,
  setTab: (tab) => set({ tab, sheet: null }),
  setClimate: (climate) => set({ climate }),
  openSheet: (kind, from = null, issueId) => set({ sheet: { kind, from, issueId } }),
  closeSheet: () => set({ sheet: null }),
  setMode: (mode) => set({ mode }),
  setDraft: (draft) => set({ draft }),
  send: (text, mode, context) => set((s) => ({
    turns: [...s.turns, { id: Date.now(), mode: mode ?? s.mode, text, context,
      history: s.turns.filter((t) => t.mode === "ask").map((t) => t.text).slice(-5) }],
    mode: mode ?? s.mode, draft: "", tab: "assistant", sheet: null,
  })),
  prefill: (mode, draft) => set({ tab: "assistant", mode, draft, sheet: null }),
  light: (litNodes) => set((s) => ({ litNodes, litUnseen: !s.graphOpen && litNodes.length > 0 })),
  markNew: (id) => set((s) => ({ newNodes: [...new Set([...s.newNodes, id])] })),
  setTourOpen: (tourOpen) => set({ tourOpen }),
  // a newly filed note opens the graph: watching it file itself is the point
  playFiling: (f) => set((s) => (f && s.filing?.f.note_id === f.note_id ? {}
    : { filing: f ? { f, at: Date.now() } : null, ...(f ? { graphOpen: true, litUnseen: false } : {}) })),
  setFocus: (focus) => set({ focus }),
  setGraphOpen: (graphOpen) => set({ graphOpen, litUnseen: false, ...(graphOpen ? {} : { focus: null }) }),
}));
