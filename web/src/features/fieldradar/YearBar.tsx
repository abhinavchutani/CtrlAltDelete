import type { Alert } from "../../api/types";
import { Pause, Play } from "../../components/Icons";
import { useStore } from "../../state/store";
import { PLAY_MS, useTimeline } from "../timeline/useTimeline";

const SEV: Record<string, number> = { critical: 0, notable: 1 };
const plain = (s: string) => s.replace(/SE_SKANE/g, "Skåne").replace(/FI_SW/g, "SW Finland");

/** Play the years, or drag to one. A dot marks every year with a problem; playback stops there and opens it.
 *  The thumb glides between years at the same pace the map's colours morph. */
export function YearBar() {
  const t = useTimeline();
  const selectAlert = useStore((s) => s.selectAlert);
  const selected = useStore((s) => s.selectedAlert);
  const span = Math.max(1, t.last - t.first);
  const pct = (y: number) => `${((y - t.first) / span) * 100}%`;
  const ticks = [t.first, ...Array.from({ length: span - 1 }, (_, i) => t.first + i + 1).filter((y) => y % 5 === 0), t.last]
    .filter((y, i, a) => a.indexOf(y) === i && (y === t.first || y === t.last || (y - t.first >= 2 && t.last - y >= 2)));
  const pace = t.playing ? `${PLAY_MS}ms linear` : "220ms ease-out";
  // one dot per year, coloured by its worst alert
  const byYear = new Map<number, Alert[]>();
  for (const a of t.alerts) byYear.set(a.year, [...(byYear.get(a.year) ?? []), a]);
  const dots = [...byYear.entries()].map(([year, as]) => ({
    year, alerts: as.sort((a, b) => (SEV[a.severity] ?? 9) - (SEV[b.severity] ?? 9)),
  }));
  return (
    <section className="yearbar" aria-label="Explore years" data-tour="years">
      <button className="play" onClick={t.playing ? t.pause : t.play} aria-label={t.playing ? "Pause" : "Play the years"}>
        {t.playing ? <Pause size={18} /> : <Play size={18} />}
      </button>
      <div className="yearbar-label">
        <span>Explore years</span>
        <span className="yearbar-sub"><span className="sev-dot critical" /> stops at each problem</span>
      </div>
      <div className="track">
        <div className="track-line" />
        <div className="track-fill" style={{ width: pct(t.year), transition: `width ${pace}` }} />
        {ticks.map((y) => (
          <button key={y} className="track-tick" style={{ left: pct(y) }} onClick={() => t.scrub(y)}>
            <span className="tick-mark" /><span className="tick-label">{y}</span>
          </button>
        ))}
        {dots.map((d) => {
          const worst = d.alerts[0];
          const on = !!selected && d.alerts.some((a) => a.id === selected.id);
          return (
            <button key={d.year} className={`problem-dot ${worst.severity} ${on ? "on" : ""} ${d.year === t.year ? "here" : ""}`}
              style={{ left: pct(d.year) }} onClick={() => selectAlert(worst)}
              aria-label={`${d.year}: ${plain(worst.title)}`}>
              <span className="problem-tip" role="tooltip">
                <strong>{d.year}</strong>
                {d.alerts.map((a) => <span key={a.id}>{plain(a.title)} · {a.eur_at_risk ?? "—"}</span>)}
              </span>
            </button>
          );
        })}
        <div className="track-thumb" style={{ left: pct(t.year), transition: `left ${pace}` }} />
        <input className="track-input" type="range" min={t.first} max={t.last} value={t.year}
          onChange={(e) => t.scrub(Number(e.target.value))} aria-label="Year" />
      </div>
      <span className="yearbar-year" aria-live="polite">{t.year}</span>
    </section>
  );
}
