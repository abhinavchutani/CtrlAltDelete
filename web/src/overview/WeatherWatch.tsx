// "Next season's weather": month by month (April–August) rain in mm against the 1991–2020 normal per region, with pea
// flowering (June) marked. From /api/weather/months on the chosen climate path: one plausible weather path, not a
// forecast. Bar colour uses the map's rain-lens rule (within −10 % on track, to −25 % watch, drier is bad).
import { useMonths } from "../api/hooks";
import type { Climate, MonthWeather, Region, Status } from "../api/types";
import { REGION_NAME, StatusMark } from "../components/ui";

export const MONTHS = [4, 5, 6, 7, 8];
export const FLOWERING = 6;
const ABBR = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
export const rainStatus = (pct: number): Status => (pct >= -10 ? "ok" : pct >= -25 ? "watch" : "risk");
const sign = (n: number) => (n > 0 ? `+${n}` : n < 0 ? `−${Math.abs(n)}` : "0");

export function useSeasonWatch(year: number, climate: Climate) {
  const fi = useMonths("FI_SW", year, climate);
  const se = useMonths("SE_SKANE", year, climate);
  const pick = (ms?: MonthWeather[]) => (ms ?? []).filter((m) => MONTHS.includes(m.month));
  const regions: { region: Region; months: MonthWeather[] }[] = [
    { region: "FI_SW", months: pick(fi.data?.months) }, { region: "SE_SKANE", months: pick(se.data?.months) },
  ];
  // the region whose flowering month is driest leads the headline
  const lead = regions
    .map((r) => ({ ...r, june: r.months.find((m) => m.month === FLOWERING) }))
    .filter((r) => r.june)
    .sort((a, b) => a.june!.precip_anom_pct - b.june!.precip_anom_pct)[0];
    return { regions, lead, loading: fi.isLoading || se.isLoading };
}

/** This season's monthly rain (solid) against the 1991–2020 normal for the same months (dashed), in mm.
 *  The normal is derived from the API's own pair: normal = rain / (1 + anomaly %). Pea flowering (June) shaded. */
function RegionLine({ region, months, year }: { region: Region; months: MonthWeather[]; year: number }) {
  const W = 240, H = 100, L = 24, R = 8, T = 12, B = 18;
  const pts = months.map((m) => ({ ...m, normal: m.precip_anom_pct > -100 ? m.precip_mm / (1 + m.precip_anom_pct / 100) : 0 }));
  if (!pts.length) return null;
  const max = Math.max(...pts.flatMap((p) => [p.precip_mm, p.normal]), 1) * 1.1;
  const x = (i: number) => L + (i * (W - L - R)) / Math.max(1, pts.length - 1);
  const y = (v: number) => T + (1 - v / max) * (H - T - B);
  const path = (k: "precip_mm" | "normal") => pts.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p[k]).toFixed(1)}`).join(" ");
  const fi = pts.findIndex((p) => p.month === FLOWERING);
  const step = (W - L - R) / Math.max(1, pts.length - 1);
  const tick = Math.max(10, Math.round(max / 2 / 10) * 10);
  return (
    <div className="wl-region">
      <span className="wl-name">{REGION_NAME[region]}</span>
      <svg viewBox={`0 0 ${W} ${H}`} role="img"
        aria-label={`${REGION_NAME[region]} ${year} rain against normal: ${pts.map((p) => `${ABBR[p.month]} ${Math.round(p.precip_mm)} mm vs ${Math.round(p.normal)} mm`).join(", ")}`}>
        {fi >= 0 ? <rect x={x(fi) - step / 2} y={T - 6} width={step} height={H - T - B + 6} rx={6} fill="var(--leaf-soft)" /> : null}
        {[0, tick].map((v) => (
          <g key={v}>
            <line x1={L} x2={W - R} y1={y(v)} y2={y(v)} stroke="var(--line)" strokeWidth={1} />
            <text x={L - 4} y={y(v) + 3} textAnchor="end" fontSize={10} fill="var(--ink-muted)">{v}</text>
          </g>
        ))}
        <path d={path("normal")} fill="none" stroke="var(--ink-muted)" strokeWidth={1.5} strokeDasharray="4 3" />
        <path d={path("precip_mm")} fill="none" stroke="var(--ink)" strokeWidth={2} />
        {pts.map((p, i) => (
          <g key={p.month}>
            <circle cx={x(i)} cy={y(p.precip_mm)} r={4.5} fill={`var(--status-${rainStatus(p.precip_anom_pct)})`}
              stroke={rainStatus(p.precip_anom_pct) === "ok" ? "var(--leaf)" : "#fff"} strokeWidth={1.5} />
            <text x={x(i)} y={H - 4} textAnchor="middle" fontSize={11} fontWeight={p.month === FLOWERING ? 700 : 500}
              fill={p.month === FLOWERING ? "var(--leaf)" : "var(--ink-muted)"}>{ABBR[p.month]}</text>
          </g>
        ))}
        <text x={L - 4} y={T - 2} textAnchor="end" fontSize={10} fill="var(--ink-muted)">mm</text>
      </svg>
    </div>
  );
}

/** The widget body: a headline about flowering rain, then both regions' months. */
export function WeatherWatch({ year, climate }: { year: number; climate: Climate }) {
  const w = useSeasonWatch(year, climate);
  if (w.loading) return <div className="minimap skeleton" />;
  const j = w.lead?.june;
  const s = j ? rainStatus(j.precip_anom_pct) : "ok";
  return (
    <>
      {j && w.lead ? (
        <span className="ww-head">
          <StatusMark status={s} size={14} />
          <span>{s === "ok"
            ? <>Pea flowering (June) looks <b>close to normal</b> in both regions.</>
            : <><b>{REGION_NAME[w.lead.region]}</b>: June rain {sign(j.precip_anom_pct)}% at pea flowering, {s === "watch" ? "worth watching" : "drought risk"}.</>}
          </span>
        </span>
      ) : null}
      <div className="wl">
        {w.regions.map((r) => <RegionLine key={r.region} region={r.region} months={r.months} year={year} />)}
      </div>
      <div className="wl-key"><span><i />{year} rain</span><span><i className="dash" />1991–2020 normal</span></div>
    </>
  );
}
