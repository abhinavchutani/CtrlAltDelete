// Two small charts for a Simulate answer, both straight from /api/simulate (the plan) and the climate's preset
// (today's plan): pea harvest vs the 1991–2020 normal per region over the years, and € at risk per season as a strip.
import { useQuery } from "@tanstack/react-query";
import { get } from "../../api/client";
import type { Climate, RegionYear, SimResult } from "../../api/types";
import "./simcharts.css";

const REGIONS = [{ key: "FI_SW", name: "SW Finland", cls: "fi", color: "var(--kg-model)" },
  { key: "SE_SKANE", name: "Skåne", cls: "se", color: "var(--harvest)" }] as const;
const BAD = -20; // a bad year: harvest 20 %+ below normal (the engine's farm rule)
const tone = (band: string) => (band === "< €50k" || band === "€50–100k" ? "ok" : band === "€100–250k" ? "watch" : "risk");

const pea = (rows: RegionYear[], region: string) =>
  rows.filter((r) => r.crop === "pea" && r.region === region).sort((a, b) => a.year - b.year);

function HarvestLines({ plan, today, years }: { plan: SimResult; today?: SimResult; years: number[] }) {
  const W = 560, H = 190, L = 34, R = 8, T = 10, B = 22;
  const all = [...plan.regions, ...(today?.regions ?? [])].filter((r) => r.crop === "pea").map((r) => r.change_vs_baseline_pct);
  const lo = Math.min(BAD - 5, ...all), hi = Math.max(10, ...all) + 3;
  const x = (y: number) => L + ((y - years[0]) / Math.max(1, years[years.length - 1] - years[0])) * (W - L - R);
  const y = (v: number) => T + ((hi - v) / (hi - lo)) * (H - T - B);
  const path = (rows: RegionYear[]) => rows.map((r, i) => `${i ? "L" : "M"}${x(r.year).toFixed(1)},${y(r.change_vs_baseline_pct).toFixed(1)}`).join(" ");
  const ticks = [-20, -10, 0, 10, 20].filter((v) => v > lo && v < hi);
  const summary = REGIONS.map((g) => {
    const p = pea(plan.regions, g.key);
    const worst = p.reduce((a, b) => (b.change_vs_baseline_pct < a.change_vs_baseline_pct ? b : a), p[0]);
    return worst ? `${g.name} lowest ${worst.change_vs_baseline_pct}% in ${worst.year}` : "";
  }).join("; ");
  return (
    <figure>
      <figcaption>Pea harvest vs normal <span>· % against 1991–2020, each season</span></figcaption>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Pea harvest against normal with this plan: ${summary}`}>
        {ticks.map((v) => (
          <g key={v}>
            <line x1={L} x2={W - R} y1={y(v)} y2={y(v)} className={v === BAD ? "bad" : "grid"} />
            <text x={L - 6} y={y(v) + 3} textAnchor="end" className="ax">{v > 0 ? `+${v}` : v}</text>
          </g>
        ))}
        {ticks.includes(BAD) ? <text x={W - R} y={y(BAD) - 4} textAnchor="end" className="bad-t">bad year (−20 %)</text> : null}
        {years.filter((_, i) => i % 2 === 0).map((yr) => <text key={yr} x={x(yr)} y={H - 6} textAnchor="middle" className="ax">{yr}</text>)}
        {REGIONS.map((g) => (
          <g key={g.key}>
            {today ? <path d={path(pea(today.regions, g.key))} fill="none" stroke={g.color} strokeWidth={1.5} strokeDasharray="4 3" opacity={0.7} /> : null}
            <path d={path(pea(plan.regions, g.key))} fill="none" stroke={g.color} strokeWidth={2.5} />
          </g>
        ))}
      </svg>
      <div className="simc-key">
        {REGIONS.map((g) => <span key={g.key} className={g.cls}><i />{g.name}</span>)}
        <span><i />with this plan</span>{today ? <span><i className="dash" />today's plan</span> : null}
      </div>
    </figure>
  );
}

function RiskStrip({ plan, today, years }: { plan: SimResult; today?: SimResult; years: number[] }) {
  const row = (rows: RegionYear[], region: string) => {
    const by = new Map(pea(rows, region).map((r) => [r.year, r.eur_at_risk]));
    return years.map((yr) => by.get(yr) ?? "< €50k");
  };
  const count = (bands: string[]) => bands.filter((b) => tone(b) === "risk").length;
  return (
    <figure>
      <figcaption>€ at risk per season <span>· pea, today's plan vs with this plan</span></figcaption>
      <div className="simc-rows" role="img" aria-label={REGIONS.map((g) =>
        `${g.name}: ${today ? `${count(row(today.regions, g.key))} seasons over €250k today, ` : ""}${count(row(plan.regions, g.key))} with this plan`).join("; ")}>
        {REGIONS.map((g, gi) => (
          <div key={g.key} style={{ display: "contents" }}>
            {gi ? <span className="gap" /> : null}
            {today ? (
              <>
                <span className="lab">{g.name} <small>today</small></span>
                {row(today.regions, g.key).map((b, i) => <span key={i} className={`cell ${tone(b)}`} title={`${years[i]}: ${b}`} />)}
              </>
            ) : null}
            <span className="lab">{g.name} <small>with plan</small></span>
            {row(plan.regions, g.key).map((b, i) => <span key={i} className={`cell ${tone(b)}`} title={`${years[i]}: ${b}`} />)}
          </div>
        ))}
        <span />{years.map((yr, i) => <span key={yr} className="yr">{i % 2 === 0 ? String(yr).slice(2) : ""}</span>)}
      </div>
      <div className="simc-key">
        <span><i style={{ borderColor: "var(--status-ok)" }} />under €100k</span>
        <span><i style={{ borderColor: "var(--status-watch)" }} />€100–250k</span>
        <span><i style={{ borderColor: "var(--status-risk)" }} />over €250k</span>
      </div>
    </figure>
  );
}

/** Both charts; today's plan is the climate's preset (fetched once, cached). */
export function SimCharts({ plan, climate }: { plan: SimResult; climate: Climate }) {
  const id = `current_plan_${climate ?? "ssp245"}`;
  const today = useQuery({ queryKey: ["scenario", id], queryFn: () => get<SimResult>(`/api/scenario/${id}`), staleTime: Infinity });
  const years = plan.years.filter((y) => y <= 2040);
  return (
    <div className="simc">
      <HarvestLines plan={plan} today={today.data} years={years} />
      <RiskStrip plan={plan} today={today.data} years={years} />
    </div>
  );
}
