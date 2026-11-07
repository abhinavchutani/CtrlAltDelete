// Every server read/write the app does. Components call these; they never fetch directly.
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { useStore } from "../state/store";
import { get, post, qs } from "./client";
import type {
  AdaptationOption, AskOut, BoardRow, Climate, Decision, FarmYear, FeatureCollection, GeoParcel, GeoPoint, Health, Hazard,
  Hedge, IntentOut, MonthsFrame, PathwayItem, Provenance, Region, ScenarioPreset, ScenarioSpec, SimResult, WeatherFrame,
} from "./types";

const forever = { staleTime: Infinity };

export const useHealth = () =>
  useQuery({
    queryKey: ["health"],
    queryFn: () => get<Health>("/api/health"),
    refetchInterval: (q) => (q.state.data?.warming ? 2000 : false), // poll while the model warms up
  });
/** True when this retrieval endpoint answers from fixtures (mock mode, or its src.r_* module isn't built yet). */
export function useRetrievalIsFixture(kind: "ask" | "options" | "board") {
  const h = useHealth();
  return !!h.data && (h.data.mock || !h.data.layers?.[`live:${kind}`]);
}

export const useScenarios = () => useQuery({ queryKey: ["scenarios"], queryFn: () => get<ScenarioPreset[]>("/api/scenarios"), ...forever });

/** The scenario on screen: a preset, or a custom spec run through /api/simulate. */
export function useActiveScenario() {
  const scenarioId = useStore((s) => s.scenarioId);
  const customSpec = useStore((s) => s.customSpec);
  return useQuery({
    queryKey: customSpec ? ["simulate", customSpec] : ["scenario", scenarioId],
    queryFn: () =>
      customSpec ? post<SimResult>("/api/simulate", customSpec) : get<SimResult>(`/api/scenario/${encodeURIComponent(scenarioId)}`),
    placeholderData: keepPreviousData,
    ...forever,
  });
}

// Query builders shared by the hooks and the prefetch, so a prefetched year is the same cache entry.
const farmsQuery = (scenarioId: string | undefined, year: number) => ({
  queryKey: ["farms", scenarioId, year],
  queryFn: () => get<FarmYear[]>(`/api/cube/${encodeURIComponent(scenarioId!)}/farms${qs({ year })}`),
  ...forever,
});
const weatherQuery = (climate: Climate | "historical", year: number) => ({
  queryKey: ["weather", climate, year],
  queryFn: () => get<WeatherFrame>(`/api/weather${qs({ climate, year })}`),
  ...forever,
});
/** The weather frame a year is drawn with: observed up to START_YEAR, the scenario's climate after. */
export const climateFor = (year: number, climate: Climate | undefined, startYear: number): Climate | "historical" =>
  year <= startYear ? "historical" : (climate ?? "ssp245");

export const useFarms = (scenarioId: string | undefined, year: number) =>
  useQuery({ ...farmsQuery(scenarioId, year), enabled: !!scenarioId, placeholderData: keepPreviousData });

export const useWeather = (climate: Climate | "historical", year: number) =>
  useQuery({ ...weatherQuery(climate, year), placeholderData: keepPreviousData });

/** Load every year of the scenario in the background, so play and scrubbing never wait on the network. */
export function usePrefetchYears(scenarioId: string | undefined, years: number[], climate: Climate | undefined, startYear: number) {
  const qc = useQueryClient();
  useEffect(() => {
    if (!scenarioId || !years.length) return;
    for (const y of years) {
      void qc.prefetchQuery(farmsQuery(scenarioId, y));
      void qc.prefetchQuery(weatherQuery(climateFor(y, climate, startYear), y));
    }
    // years is a fresh array each render; its ends and length identify it
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [qc, scenarioId, climate, startYear, years.length, years[0]]);
}

export const useHedge = (climate: Climate) =>
  useQuery({ queryKey: ["hedge", climate], queryFn: () => get<Hedge>(`/api/hedge${qs({ climate })}`), ...forever });

export const usePathways = (scenarioId: string | undefined) =>
  useQuery({
    queryKey: ["pathways", scenarioId],
    queryFn: () => get<PathwayItem[]>(`/api/pathways/${encodeURIComponent(scenarioId!)}`),
    enabled: !!scenarioId,
    ...forever,
  });

export const useOptions = (hazard: Hazard | null, crop: string | null) =>
  useQuery({
    queryKey: ["options", hazard, crop],
    queryFn: () => get<AdaptationOption[]>(`/api/options${qs({ hazard, crop })}`),
    enabled: !!hazard,
    ...forever,
  });

export const useBoard = (scenarioId: string | undefined) =>
  useQuery({
    queryKey: ["board", scenarioId],
    queryFn: () => get<BoardRow[]>(`/api/board/${encodeURIComponent(scenarioId!)}`),
    enabled: !!scenarioId,
  });

export function useDecide() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ rowId, decision }: { rowId: string; decision: Decision }) =>
      post<BoardRow>(`/api/board/${encodeURIComponent(rowId)}/decision`, decision),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["board"] }),
  });
}

export const useAsk = (question: string | null, history: string[] = []) =>
  useQuery({
    queryKey: ["ask", question, history],
    queryFn: () => post<AskOut>("/api/ask", { question, history: history.map((q) => ({ question: q })) }),
    enabled: !!question,
    ...forever,
  });

/** One chat line → its intent (door ask or simulate). Cached per text + the spec it would extend. */
export const useIntentQuery = (text: string, base: ScenarioSpec | null) =>
  useQuery({ queryKey: ["intent", text, base], queryFn: () => post<IntentOut>("/api/intent", { text, base }), ...forever });

export const useIntent = () =>
  useMutation({ mutationFn: ({ text, base }: { text: string; base: ScenarioSpec | null }) => post<IntentOut>("/api/intent", { text, base }) });

export const useGeoFarms = () =>
  useQuery({ queryKey: ["geo", "farms"], queryFn: () => get<FeatureCollection<GeoPoint>>("/api/geo/farms"), ...forever });
export const useGeoParcels = () =>
  useQuery({ queryKey: ["geo", "parcels"], queryFn: () => get<FeatureCollection<GeoParcel>>("/api/geo/parcels"), ...forever });

/** Text or speech → intent → either an ask question or a pending spec (confirmed by the user before it runs). */
export function useSubmitText() {
  const intent = useIntent();
  const sim = useActiveScenario();
  const { ask, setPending } = useStore();
  return {
    ...intent,
    submit: (text: string) =>
      intent.mutate({ text, base: sim.data?.spec ?? null }, {
        onSuccess: (r) => (r.door === "ask" || !r.spec ? ask(r.text) : setPending(r.spec as ScenarioSpec, r.heard ?? [], r.problems ?? [])),
      }),
  };
}

// ── UI v3 ──────────────────────────────────────────────────────────
/** What the model is built on, counted from the data by the API. */
export const useProvenance = () =>
  useQuery({ queryKey: ["provenance"], queryFn: () => get<Provenance>("/api/provenance"), ...forever });

/** Month-by-month weather of one region in one year (drives the map's weather effects and the alert card). */
export const useMonths = (region: Region | null, year: number, climate: Climate | undefined) =>
  useQuery({
    queryKey: ["months", region, year, climate ?? "ssp245"],
    queryFn: () => get<MonthsFrame>(`/api/weather/months${qs({ region, year, climate: climate ?? "ssp245" })}`),
    enabled: !!region,
    placeholderData: keepPreviousData,
    ...forever,
  });

/** Every adaptation option in the knowledge base (cost level, lead time, robustness per lever). */
export const useAllOptions = () =>
  useQuery({ queryKey: ["options", "all"], queryFn: () => get<AdaptationOption[]>("/api/options"), ...forever });

/** A spec simulated on its own (the assistant's what-if cards), without changing what the map shows. */
export const useSimulation = (spec: ScenarioSpec | null) =>
  useQuery({
    queryKey: ["simulate", spec],
    queryFn: () => post<SimResult>("/api/simulate", spec),
    enabled: !!spec,
    retry: (n, e) => n < 8 && String(e).startsWith("503"), // the model may still be warming
    retryDelay: 2500,
    ...forever,
  });
