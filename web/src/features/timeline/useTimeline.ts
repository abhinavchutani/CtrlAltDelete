// Timeline state: years of the active scenario, play/scrub, and the events to mark.
import { useEffect, useMemo } from "react";
import { useActiveScenario, usePathways } from "../../api/hooks";
import { START_YEAR, useStore } from "../../state/store";

export const PLAY_MS = 700;

export function useTimeline() {
  const sim = useActiveScenario();
  const pathways = usePathways(sim.data?.scenario_id);
  const { year, setYear, playing, setPlaying } = useStore();
  const years = sim.data?.years ?? [START_YEAR];
  const first = years[0];
  const last = years[years.length - 1];

  useEffect(() => {
    if (!playing) return;
    const t = setInterval(() => {
      const y = useStore.getState().year;
      if (y >= last) setPlaying(false);
      else setYear(y + 1);
    }, PLAY_MS);
    return () => clearInterval(t);
  }, [playing, last, setYear, setPlaying]);

  const decideBy = useMemo(
    () =>
      (pathways.data ?? [])
        .filter((p) => p.decide_by !== null && p.decide_by !== undefined && p.decide_by <= last)
        .map((p) => ({ year: Math.max(p.decide_by as number, first), label: `decide by ${p.decide_by}: ${p.option}`, item: p })),
    [pathways.data, first, last],
  );

  return {
    first, last, year, playing, alerts: sim.data?.alerts ?? [], decideBy,
    loading: sim.isLoading, error: sim.error,
    play: () => { if (year >= last) setYear(first); setPlaying(true); },
    pause: () => setPlaying(false),
    scrub: (y: number) => { setPlaying(false); setYear(y); },
  };
}
