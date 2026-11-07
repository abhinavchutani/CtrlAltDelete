import { alertsByYear } from "../../domain";
import { useStore } from "../../state/store";
import { Status } from "../../components/Status";
import { EventDot } from "./EventDot";
import { useTimeline } from "./useTimeline";

const W = 900, H = 74, PAD = 30;

export function Timeline() {
  const t = useTimeline();
  const selectAlert = useStore((s) => s.selectAlert);
  const span = Math.max(1, t.last - t.first);
  const x = (y: number) => PAD + ((y - t.first) / span) * (W - 2 * PAD);
  const byYear = alertsByYear(t.alerts);
  const ticks = Array.from({ length: span + 1 }, (_, i) => t.first + i).filter((y) => y % 5 === 0 || y === t.first);
  return (
    <div className="row">
      <button onClick={t.playing ? t.pause : t.play}>{t.playing ? "Pause" : "Play"}</button>
      <input type="range" min={t.first} max={t.last} value={t.year} onChange={(e) => t.scrub(Number(e.target.value))} aria-label="year" />
      <strong>{t.year}</strong>
      <Status loading={t.loading} error={t.error} />
      <svg className="chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="timeline">
        <line className="axis" x1={PAD} x2={W - PAD} y1={20} y2={20} />
        <line className="axis" x1={PAD} x2={W - PAD} y1={50} y2={50} />
        <text x={2} y={23}>alerts</text>
        <text x={2} y={53}>decide</text>
        {ticks.map((y) => <text key={y} x={x(y) - 10} y={H - 4}>{y}</text>)}
        <line className="cursor" x1={x(t.year)} x2={x(t.year)} y1={8} y2={58} />
        {[...byYear.entries()].flatMap(([y, as]) => as.map((a, i) => <EventDot key={a.id} alert={a} x={x(y)} y={20 - i * 8} onSelect={selectAlert} />))}
        {t.decideBy.map((d, i) => (
          <rect key={i} className="decide-mark" x={x(d.year) - 3} y={46} width={6} height={8}><title>{d.label}</title></rect>
        ))}
      </svg>
    </div>
  );
}
