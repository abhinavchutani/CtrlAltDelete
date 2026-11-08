// The plan finder's state: POST /api/search streams one event per simulated plan (Server-Sent Events over fetch,
// since EventSource can't POST). Kept in its own store so the Overview and Assistant share one run.
import { create } from "zustand";
import type { Climate, PlanBaseline, PlanCandidate, SearchEvent } from "../api/types";

type Status = "idle" | "running" | "done" | "error";
const PACE_MS = 70;
type SearchState = {
  key: string | null; // climate:horizon of the run on screen
  status: Status;
  total: number;
  done: number;
  years: number;
  plan: PlanBaseline | null;
  candidates: Record<string, PlanCandidate>;
  arrival: string[]; // ids in the order they were simulated
  last: string | null; // the plan simulated most recently (shown while running)
  ranking: string[];
  best: string | null;
  error: string | null;
  start: (climate: Climate, horizon: number) => Promise<void>;
};

/** Live order while running: the best so far first (by band, then savings), final ranking once done. */
const BANDS = ["< €50k", "€50–100k", "€100–250k", "€250k–1M", "> €1M"];
export const liveOrder = (s: Pick<SearchState, "candidates" | "arrival" | "ranking">): PlanCandidate[] =>
  s.ranking.length
    ? s.ranking.map((id) => s.candidates[id]).filter(Boolean)
    : s.arrival.map((id) => s.candidates[id]).sort((a, b) =>
      BANDS.indexOf(a.eur_at_risk_per_year) - BANDS.indexOf(b.eur_at_risk_per_year)
      || BANDS.indexOf(b.saves ?? "") - BANDS.indexOf(a.saves ?? ""));

export const useSearch = create<SearchState>((set, get) => ({
  key: null, status: "idle", total: 0, done: 0, years: 0, plan: null, candidates: {}, arrival: [], last: null,
  ranking: [], best: null, error: null,
  start: async (climate, horizon) => {
    const key = `${climate}:${horizon}`;
    const cur = get();
    if (cur.key === key && (cur.status === "running" || cur.status === "done")) return;
    set({ key, status: "running", total: 0, done: 0, years: 0, plan: null, candidates: {}, arrival: [], last: null,
      ranking: [], best: null, error: null });
    const apply = (e: SearchEvent) => {
      if (get().key !== key) return; // a newer run took over
      switch (e.type) {
        case "start": set({ total: e.total, years: e.years, plan: e.plan }); break;
        case "phase": set({ total: e.total }); break;
        case "candidate": set((s) => ({
          done: e.done, total: e.total, last: e.candidate.id,
          candidates: { ...s.candidates, [e.candidate.id]: e.candidate }, arrival: [...s.arrival, e.candidate.id],
        })); break;
        case "stress": set((s) => ({
          candidates: { ...s.candidates, [e.id]: { ...s.candidates[e.id], futures: e.futures } },
        })); break;
        case "done": set({ status: "done", ranking: e.ranking, best: e.best, last: null }); break;
        case "error": set({ status: "error", error: e.detail }); break;
      }
    };
    try {
      const res = await fetch("/api/search", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ climate, horizon_end: horizon }),
      });
      if (!res.ok || !res.body) {
        let detail = res.statusText;
        try { detail = (await res.json()).detail ?? detail; } catch { /* not JSON */ }
        throw new Error(`${res.status}: ${detail}`);
      }
      const reader = res.body.getReader();
      const dec = new TextDecoder();
      let buf = "", shown = 0;
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        let cut: number;
        while ((cut = buf.indexOf("\n\n")) >= 0) {
          const chunk = buf.slice(0, cut);
          buf = buf.slice(cut + 2);
          for (const line of chunk.split("\n")) {
            if (!line.startsWith("data: ")) continue;
            const ev = JSON.parse(line.slice(6)) as SearchEvent;
            // a finished search replays in one burst: show each real plan arriving rather than all at once
            if (ev.type === "candidate" && shown++ > 0) await new Promise((r) => setTimeout(r, PACE_MS));
            apply(ev);
          }
        }
      }
      if (get().key === key && get().status === "running") set({ status: "error", error: "the stream ended early" });
    } catch (err) {
      if (get().key === key) set({ status: "error", error: err instanceof Error ? err.message : String(err) });
    }
  },
}));
