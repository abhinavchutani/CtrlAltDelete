import type { Region } from "../../api/types";
import { useStore } from "../../state/store";
import { Drop, Euro, Leaf, Pause, Play } from "../../components/Icons";
import { useTimeline } from "../timeline/useTimeline";
import { droughtLevel, useFieldData } from "./useFieldData";

const LEVEL = { low: "Low risk", medium: "Medium risk", high: "High risk" } as const;

/** Farm health, € risk and drought for the chosen year, then play + the timeline with the scenario's alerts. */
export function StatsBar() {
  const d = useFieldData();
  const t = useTimeline();
  const { view, selectAlert } = useStore();
  const region: Region = view.longitude < 18 ? "SE_SKANE" : "FI_SW";
  const drought = d.stats.drought[region];
  const span = Math.max(1, t.last - t.first);
  const pct = (y: number) => `${((y - t.first) / span) * 100}%`;
  const ticks = [t.first, ...Array.from({ length: span }, (_, i) => t.first + i + 1).filter((y) => y % 10 === 0), t.last]
    .filter((y, i, a) => a.indexOf(y) === i);
  return (
    <section className="glass stats-bar" aria-label="Year summary">
      <div className="stat">
        <span className="stat-icon good"><Leaf /></span>
        <div><div className="stat-label">Farm health</div><div className="stat-value">{d.stats.healthPct ?? "—"}{d.stats.healthPct !== undefined ? "%" : ""}</div></div>
      </div>
      <div className="stat">
        <span className="stat-icon warn"><Euro /></span>
        <div><div className="stat-label">€ risk (worst region)</div><div className="stat-value">{d.stats.worstBand ?? "—"}</div></div>
      </div>
      <div className="stat">
        <span className="stat-icon bad"><Drop /></span>
        <div>
          <div className="stat-label">Drought · {region === "SE_SKANE" ? "Skåne" : "SW Finland"}</div>
          <div className="stat-value">{drought === undefined ? "—" : LEVEL[droughtLevel(drought)]}</div>
        </div>
      </div>
      <button className="play" onClick={t.playing ? t.pause : t.play} aria-label={t.playing ? "Pause" : "Play"}>
        {t.playing ? <Pause /> : <Play />}
      </button>
      <div className="track">
        <div className="track-line" />
        <div className="track-fill" style={{ width: pct(t.year) }} />
        {t.alerts.map((a) => (
          <button key={a.id} className={`track-alert ${a.severity}`} style={{ left: pct(a.year) }}
            title={`${a.year}: ${a.title} (${a.eur_at_risk ?? ""})`} onClick={() => selectAlert(a)} aria-label={a.title} />
        ))}
        {ticks.map((y) => (
          <button key={y} className={`track-tick ${y === t.year ? "on" : ""}`} style={{ left: pct(y) }} onClick={() => t.scrub(y)}>
            <span className="knob" /><span className="tick-label">{y}</span>
          </button>
        ))}
        <div className="track-cursor" style={{ left: pct(t.year) }}><span>{t.year}</span></div>
        <input className="track-input" type="range" min={t.first} max={t.last} value={t.year}
          onChange={(e) => t.scrub(Number(e.target.value))} aria-label="year" />
      </div>
    </section>
  );
}
