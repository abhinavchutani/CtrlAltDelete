// ① This season at a glance: one stage bar per region, a "today" line, the status mark.
// Stages reached by today are solid; later ones are the 1991–2020 median dates, drawn faded and dashed.
import type { RegionDay, Today } from "../../api/types";
import { REGION_NAME, STATUS_LABEL, StatusMark } from "../../components/ui";
import { CROP_NAME, SEASON_DAYS, seasonDay, STAGE_WORD, useWidth } from "./shared";

const MONTHS = [["Apr", 0], ["May", 30], ["Jun", 61], ["Jul", 91], ["Aug", 122], ["Sep", 153], ["Oct", 183]] as const;
const FILL = { sown: "color-mix(in srgb, var(--accent) 38%, transparent)", flowering: "var(--apetit)", fill: "var(--status-ok)" } as const;
const ROW = 40, TOP = 4;
type X = (d: number) => number;

function Row({ r, y, today, x }: { r: RegionDay; y: number; today: number; x: X }) {
  const at = Object.fromEntries(r.stages.map((s) => [s.name, s])) as Record<string, RegionDay["stages"][number]>;
  const segs = (["sown", "flowering", "fill"] as const).map((name, i) => {
    const a = seasonDay(at[name].date), b = seasonDay(at[(["flowering", "fill", "harvest"] as const)[i]].date);
    const exp = at[name].expected;
    // a reached stage is solid up to today; anything after today is the expected part
    const solidEnd = exp ? a : Math.min(b, Math.max(a, today));
    return (
      <g key={name}>
        {!exp && solidEnd > a ? <rect x={x(a)} y={y} width={x(solidEnd) - x(a)} height={ROW - 16} rx={6} fill={FILL[name]} /> : null}
        {b > Math.max(a, solidEnd) ? (
          <rect x={x(Math.max(a, solidEnd))} y={y} width={x(b) - x(Math.max(a, solidEnd))} height={ROW - 16} rx={6}
            fill={FILL[name]} opacity={0.35} stroke="var(--line-strong)" strokeDasharray="6 5" strokeWidth={1.5} />
        ) : null}
      </g>
    );
  });
  return <g>{segs}</g>;
}

export function SeasonGlance({ t }: { t: Today }) {
  const [ref, W] = useWidth<HTMLDivElement>();
  const x: X = (d) => (Math.max(0, Math.min(SEASON_DAYS, d)) / SEASON_DAYS) * (W - 4) + 2;
  const today = seasonDay(t.date);
  const h = TOP + t.regions.length * ROW + 22;
  const label = t.regions.map((r) => `${REGION_NAME[r.region]}: ${STAGE_WORD[r.stage]}, ${STATUS_LABEL[r.status].toLowerCase()}`).join("; ");
  return (
    <div className="glance">
      <div className="glance-names">
        {t.regions.map((r) => (
          <span key={r.region} className="glance-name"><StatusMark status={r.status} size={13} />{REGION_NAME[r.region]}</span>
        ))}
      </div>
      <div ref={ref} className="glance-chart">
      <svg width={W} height={h} viewBox={`0 0 ${W} ${h}`} role="img"
        aria-label={`${CROP_NAME[t.crop]} season on ${t.date}. ${label}`}>
        {t.regions.map((r, i) => <Row key={r.region} r={r} y={TOP + i * ROW} today={today} x={x} />)}
        {MONTHS.map(([m, d]) => (
          <text key={m} x={x(d) + 4} y={h - 4} className="glance-tick">{m}</text>
        ))}
        <line x1={x(today)} x2={x(today)} y1={0} y2={h - 18} stroke="var(--ink)" strokeWidth={2} />
      </svg>
      </div>
    </div>
  );
}

/** One sentence under the chart: the worst region's stage and status. */
export function glanceLine(t: Today): string {
  const rank = { risk: 2, watch: 1, ok: 0 } as const;
  const r = [...t.regions].sort((a, b) => rank[b.status] - rank[a.status])[0];
  if (!r) return "";
  const fl = r.stages.find((s) => s.name === "flowering");
  const days = fl && !fl.expected ? Math.max(0, seasonDay(t.date) - seasonDay(fl.date)) : null;
  const when = r.stage === "flowering" && days !== null ? `, day ${days + 1} of flowering` : "";
  return `${REGION_NAME[r.region]} ${CROP_NAME[r.crop]}: ${STAGE_WORD[r.stage]}${when} · ${STATUS_LABEL[r.status].toLowerCase()}`;
}
