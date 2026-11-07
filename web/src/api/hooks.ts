// Every server read/write the app does. Components call these; they never fetch directly.
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useStore } from "../state/store";
import { get, post, qs } from "./client";
import type {
  AdaptationOption, AskOut, BoardRow, Climate, Decision, FarmYear, FeatureCollection, GeoParcel, GeoPoint, Health, Hazard,
  Hedge, IntentOut, PathwayItem, ScenarioPreset, ScenarioSpec, SimResult, WeatherFrame,
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
