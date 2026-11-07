// Every server read/write the app does. Components call these; they never fetch directly.
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useStore } from "../state/store";
import { get, post, qs } from "./client";
import type {
  AdaptationOption, AskOut, BoardRow, Climate, Decision, FarmYear, FeatureCollection, GeoParcel, GeoPoint, Health, Hazard,
  Hedge, IntentOut, PathwayItem, ScenarioPreset, ScenarioSpec, SimResult, WeatherFrame,
} from "./types";

const forever = { staleTime: Infinity };

export const useHealth = () => useQuery({ queryKey: ["health"], queryFn: () => get<Health>("/api/health") });
export const useScenarios = () => useQuery({ queryKey: ["scenarios"], queryFn: () => get<ScenarioPreset[]>("/api/scenarios"), ...forever });

/** The scenario on screen: a preset, or a custom spec run through /api/simulate. */
export function useActiveScenario() {
  const { scenarioId, customSpec } = useStore();
  return useQuery({
    queryKey: customSpec ? ["simulate", customSpec] : ["scenario", scenarioId],
    queryFn: () =>
      customSpec ? post<SimResult>("/api/simulate", customSpec) : get<SimResult>(`/api/scenario/${encodeURIComponent(scenarioId)}`),
    placeholderData: keepPreviousData,
    ...forever,
  });
}

export const useFarms = (scenarioId: string | undefined, year: number) =>
  useQuery({
    queryKey: ["farms", scenarioId, year],
    queryFn: () => get<FarmYear[]>(`/api/cube/${encodeURIComponent(scenarioId!)}/farms${qs({ year })}`),
    enabled: !!scenarioId,
    placeholderData: keepPreviousData,
    ...forever,
  });

export const useWeather = (climate: Climate | "historical", year: number) =>
  useQuery({
    queryKey: ["weather", climate, year],
    queryFn: () => get<WeatherFrame>(`/api/weather${qs({ climate, year })}`),
    placeholderData: keepPreviousData,
    ...forever,
  });

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

export const useAsk = (question: string | null) =>
  useQuery({
    queryKey: ["ask", question],
    queryFn: () => post<AskOut>("/api/ask", { question, history: [] }),
    enabled: !!question,
    ...forever,
  });

export const useIntent = () => useMutation({ mutationFn: (text: string) => post<IntentOut>("/api/intent", { text }) });

export const useGeoFarms = () =>
  useQuery({ queryKey: ["geo", "farms"], queryFn: () => get<FeatureCollection<GeoPoint>>("/api/geo/farms"), ...forever });
export const useGeoParcels = () =>
  useQuery({ queryKey: ["geo", "parcels"], queryFn: () => get<FeatureCollection<GeoParcel>>("/api/geo/parcels"), ...forever });

/** Text or speech → intent → either an ask question or a pending spec (confirmed by the user before it runs). */
export function useSubmitText() {
  const intent = useIntent();
  const { ask, setPending } = useStore();
  return {
    ...intent,
    submit: (text: string) =>
      intent.mutate(text, {
        onSuccess: (r) => (r.door === "ask" || !r.spec ? ask(r.text) : setPending(r.spec as ScenarioSpec, r.heard ?? [], r.problems ?? [])),
      }),
  };
}
