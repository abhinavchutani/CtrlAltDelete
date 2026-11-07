// ③ How unusual is this season? The 30 normal years (1991–2020) on this same day as small dots, today as the big one.
import type { RegionDay } from "../../api/types";
import { REGION_NAME, STATUS_LABEL } from "../../components/ui";
import { below, ordinal, useWidth } from "./shared";

/** One dot strip. `metric` picks dryness (0–1) or hot days. Right = more stress. */
export function DotStrip({ r, metric = "dryness", height = 44 }: { r: RegionDay; metric?: "dryness" | "heat"; height?: number }) {
  const [ref, W] = useWidth<HTMLDivElement>();
  const normal = metric === "dryness" ? r.dryness_normal : r.hot_normal;
  const value = metric === "dryness" ? r.dryness : r.hot_days;
  const p = metric === "dryness" ? r.dryness_pct : r.heat_pct;
  const lo = Math.min(...normal, value), hi = Math.max(...normal, value);
  const span = Math.max(hi - lo, metric === "dryness" ? 0.05 : 2);
  const x = (v: number) => 14 + ((v - lo) / span) * (W - 28);
  const med = [...normal].sort((a, b) => a - b)[Math.floor(normal.length / 2)];
  // stack dots that land on the same spot (a tiny beeswarm)
  const seen = new Map<number, number>();
  const dots = normal.map((v) => {
    const k = Math.round(x(v) / 9);
    const n = seen.get(k) ?? 0;
    seen.set(k, n + 1);
    return { cx: x(v), cy: height / 2 + (n % 2 ? 1 : -1) * Math.ceil(n / 2) * 7 };
  });
  const what = metric === "dryness" ? "drier" : "hotter";
  return (
    <div ref={ref} className="dotstrip">
    <svg width={W} height={height} viewBox={`0 0 ${W} ${height}`} role="img"
      aria-label={`${REGION_NAME[r.region]}: ${what} so far than ${below(value, normal)} of ${normal.length} normal seasons on this day (${ordinal(p)} percentile)`}>
      <line x1={14} x2={W - 14} y1={height / 2} y2={height / 2} stroke="var(--line)" strokeWidth={2} />
      <line x1={x(med)} x2={x(med)} y1={4} y2={height - 4} stroke="var(--line-strong)" strokeWidth={2} strokeDasharray="4 4" />
      {dots.map((d, i) => <circle key={i} cx={d.cx} cy={d.cy} r={3.5} fill="var(--ink-muted)" opacity={0.5} />)}
      <circle cx={x(value)} cy={height / 2} r={8} fill={`var(--status-${r.status})`} stroke="var(--ink)" strokeWidth={2} />
    </svg>
    </div>
  );
}

export function Unusual({ regions }: { regions: RegionDay[] }) {
  return (
    <div className="unusual">
      {regions.map((r) => (
        <div key={r.region} className="unusual-row">
          <span className="unusual-name">{REGION_NAME[r.region]}</span>
          <DotStrip r={r} />
          <span className={`unusual-pct ${r.status}`} title={STATUS_LABEL[r.status]}>{ordinal(r.dryness_pct)}</span>
        </div>
      ))}
      <div className="unusual-axis"><span>wetter</span><span>normal ┆</span><span>drier</span></div>
    </div>
  );
}

export function unusualLine(regions: RegionDay[]): string {
  const r = [...regions].sort((a, b) => b.dryness_pct - a.dryness_pct)[0];
  if (!r) return "";
  return `${REGION_NAME[r.region]} drier so far than ${below(r.dryness, r.dryness_normal)} of ${r.dryness_normal.length} normal seasons`;
}
