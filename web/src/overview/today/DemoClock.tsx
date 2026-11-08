// The demo clock: the Overview's "today". Step a day, pick a date in the season, or play the season forward
// (one day per tick; it stops when a crop's status changes, so the viewer sees what moved).
import { useEffect } from "react";
import type { Today } from "../../api/types";
import { ChevronLeft, ChevronRight, PauseIcon, PlayIcon } from "../../components/ui";
import { useStore } from "../../state/store";
import { addDays, longDate } from "./shared";

const TICK_MS = 600;

export function DemoClock({ t, fetching }: { t: Today | undefined; fetching: boolean }) {
  const setAsOf = useStore((s) => s.setAsOf);
  const playing = useStore((s) => s.dayPlaying);
  const setPlaying = useStore((s) => s.setDayPlaying);
  const [first, last] = t?.season ?? ["", ""];
  const step = (n: number) => {
    if (!t) return;
    const d = addDays(t.date, n);
    if (d >= first && d <= last) setAsOf(d);
  };

  // play: advance once the day's data is in; stop on a status change or at the end of the season
  useEffect(() => {
    if (!playing || !t || fetching) return;
    if (t.changes.some((c) => c.kind === "escalated" || c.kind === "eased")) { setPlaying(false); return; }
    if (t.date >= last) { setPlaying(false); return; }
    const id = window.setTimeout(() => setAsOf(addDays(t.date, 1)), TICK_MS);
    return () => window.clearTimeout(id);
  }, [playing, t, fetching, last, setAsOf, setPlaying]);

  const play = () => {
    if (!playing && t && t.changes.some((c) => c.kind === "escalated" || c.kind === "eased")) step(1); // move off the stop
    setPlaying(!playing);
  };

  return (
    <div className="clock glass" role="group" aria-label="Demo clock" aria-busy={fetching || undefined}>
      <button type="button" className="clock-btn" aria-label="Previous day" onClick={() => step(-1)} disabled={!t || t.date <= first}><ChevronLeft /></button>
      <label className="clock-date">
        <span className="sr-only">Day</span>
        <input type="date" value={t?.date ?? ""} min={first} max={last} disabled={!t}
          onChange={(e) => { if (e.target.value >= first && e.target.value <= last) setAsOf(e.target.value); }} />
        <span aria-hidden="true">{t ? longDate(t.date) : "…"}</span>
      </label>
      <button type="button" className="clock-btn" aria-label="Next day" onClick={() => step(1)} disabled={!t || t.date >= last}><ChevronRight /></button>
      <button type="button" className="clock-play" aria-pressed={playing} aria-label={playing ? "Pause" : "Play the season"} onClick={play} disabled={!t}>
        {playing ? <PauseIcon size={18} /> : <PlayIcon size={18} />}
      </button>
    </div>
  );
}
