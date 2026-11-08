// Every server read/write the app does. Components call these; they never fetch directly.
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, get, post, qs } from "./client";
import type {
  AdaptationOption, Climate, EntityView, Filed, Graph, Health, Interview, IntentOut, KnowledgeItem, Lever, MonthsFrame, Outlook,
  Provenance, RadarAskOut, Region, ScenarioSpec, SimResult,
} from "./types";

const forever = { staleTime: Infinity };
const warmRetry = { retry: (n: number, e: unknown) => n < (e instanceof ApiError && e.status === 503 ? 30 : 1), retryDelay: 3000 }; // 503 = model warming

export const useHealth = () =>
  useQuery({
    queryKey: ["health"],
    queryFn: () => get<Health>("/api/health"),
    refetchInterval: (q) => (q.state.data?.warming ? 2000 : false), // poll while the model warms up
  });

/** The Overview's numbers (api/radar.py): today's plan, or a plan's levers, on one climate path, 2026–2040. */
export const useOutlook = (climate: Climate, levers: Lever[] | null) =>
  useQuery({
    queryKey: ["outlook", climate, levers ?? []],
    queryFn: () => post<Outlook>("/api/radar/outlook", { climate, levers: levers ?? [] }),
    placeholderData: keepPreviousData,
    ...warmRetry,
    ...forever,
  });

/** What the model is built on, counted from the data by the API. */
export const useProvenance = () =>
  useQuery({ queryKey: ["provenance"], queryFn: () => get<Provenance>("/api/provenance"), ...forever });

/** Month-by-month weather of one region in one year. */
export const useMonths = (region: Region | null, year: number, climate: Climate | undefined) =>
  useQuery({
    queryKey: ["months", region, year, climate ?? "ssp245"],
    queryFn: () => get<MonthsFrame>(`/api/weather/months${qs({ region, year, climate: climate ?? "ssp245" })}`),
    enabled: !!region,
    placeholderData: keepPreviousData,
    ...forever,
  });

/** Every adaptation option in the knowledge base (cost level per lever). */
export const useAllOptions = () =>
  useQuery({ queryKey: ["options", "all"], queryFn: () => get<AdaptationOption[]>("/api/options"), ...forever });

/** A spec simulated on its own (the assistant's Simulate cards). */
export const useSimulation = (spec: ScenarioSpec | null) =>
  useQuery({ queryKey: ["simulate", spec], queryFn: () => post<SimResult>("/api/simulate", spec), enabled: !!spec, ...warmRetry, ...forever });

/** One Simulate line → the plan it describes (src.p_parse, deterministic). */
export const useIntentQuery = (text: string, base: ScenarioSpec | null) =>
  useQuery({ queryKey: ["intent", text, base], queryFn: () => post<IntentOut>("/api/intent", { text, base }), ...forever });

// ── assistant ─────────────────────────────────────────────────────
export const useGraph = () => useQuery({ queryKey: ["graph"], queryFn: () => get<Graph>("/api/graph"), staleTime: 30_000 });

export const useRadarAsk = (question: string, history: string[]) =>
  useQuery({
    queryKey: ["radar-ask", question, history],
    queryFn: () => post<RadarAskOut>("/api/radar/ask", { question, history: history.map((q) => ({ question: q })) }),
    ...forever,
  });

/** Everything linked to one farm or site ID (tables, people's notes, open gaps); only fetched for an entity node. */
export const useEntity = (id: string | null) =>
  useQuery({ queryKey: ["entity", id], queryFn: () => get<EntityView>(`/api/entity/${encodeURIComponent(id!)}`), enabled: !!id, staleTime: 30_000 });

export const useTopics = () => useQuery({ queryKey: ["topics"], queryFn: () => get<string[]>("/api/tacit/topics"), ...forever });

export function useFileNote() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (b: { text: string; contributed_by: string; role?: string | null; farm_id?: string | null; gap_id?: string | null }) =>
      post<Filed>("/api/tacit/notes", b),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["graph"] }),
  });
}

export function useConfirmNote() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, reviewer }: { id: string; reviewer: string }) =>
      post<KnowledgeItem>(`/api/tacit/notes/${encodeURIComponent(id)}/confirm`, { reviewer }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["graph"] }),
  });
}

export function useRefileNote() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, topic }: { id: string; topic: string }) =>
      fetch(`/api/tacit/notes/${encodeURIComponent(id)}`, {
        method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ topic }),
      }).then(async (r) => { if (!r.ok) throw new Error(`${r.status}: ${(await r.json()).detail}`); return r.json() as Promise<Filed>; }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["graph"] }),
  });
}

export const useInterview = (gapId: string | null) =>
  useQuery({
    queryKey: ["interview", gapId],
    queryFn: () => post<Interview>("/api/tacit/interviews", { gap_id: gapId }),
    enabled: !!gapId,
    ...forever,
  });

/** Cited adaptation measures for a problem (kb/solutions.json via /api/solutions). */
export const useSolutions = (hazards: string[], climate: Climate) =>
  useQuery({
    queryKey: ["solutions", hazards, climate],
    queryFn: () => get<import("./types").Solution[]>(`/api/solutions?${hazards.map((h) => `hazard=${h}`).join("&")}&crop=pea&climate=${climate}`),
    enabled: hazards.length > 0,
    staleTime: 60_000,
  });
