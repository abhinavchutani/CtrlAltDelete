// Timeline state: years of the active scenario, play/scrub, and the events to mark.
// Call it from ONE mounted component (YearBar): it owns the playback interval.
import { useEffect, useMemo, useRef } from "react";
import { useActiveScenario, usePathways } from "../../api/hooks";
import { START_YEAR, useStore } from "../../state/store";

export const PLAY_MS = 450; // one year per step; colours tween over TWEEN_MS (map/layers/parcels.ts) so playback flows
const SEVERITY: Record<string, number> = { critical: 0, notable: 1 };

export function useTimeline() {
  const sim = useActiveScenario();
  const pathways = usePathways(sim.data?.scenario_id);
  const { year, setYear, playing, setPlaying } = useStore();
  const years = sim.data?.years ?? [START_YEAR];
  const first = years[0];
  const last = years[years.length - 1];

  // Playback stops at every year with a problem: it opens that year's worst alert (MapView flies to its pin), so
  // nobody plays past a drought without seeing it. Play again to carry on from the next year.
  const alerts = sim.data?.alerts ?? [];
  const alertsRef = useRef(alerts);
  alertsRef.current = alerts;
  useEffect(() => {
    if (!playing) return;
    const t = setInterval(() => {
      const y = useStore.getState().year;
      if (y >= last) { setPlaying(false); return; }
      const hit = alertsRef.current.filter((a) => a.year === y + 1)
        .sort((a, b) => (SEVERITY[a.severity] ?? 9) - (SEVERITY[b.severity] ?? 9))[0];
      if (hit) useStore.getState().selectAlert(hit); // sets the year and pauses
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
    first, last, year, playing, alerts, decideBy,
    loading: sim.isLoading, error: sim.error,
    // playing on from a stop closes its alert card; from the last year it starts over
    play: () => { useStore.getState().selectAlert(null); if (year >= last) setYear(first); setPlaying(true); },
    pause: () => setPlaying(false),
    scrub: (y: number) => { setPlaying(false); setYear(y); },
  };
}
