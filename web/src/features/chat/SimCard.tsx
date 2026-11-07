// A what-if, simulated and shown in full: money at risk vs today's plan, the harvest year by year against normal
// (today's plan dashed, the new plan solid), CO2e, confidence and alerts. Every number comes from /api/simulate.
import { useQuery } from "@tanstack/react-query";
import { get } from "../../api/client";
import { useSimulation } from "../../api/hooks";
import type { RegionYear, ScenarioSpec, SimResult } from "../../api/types";
import { leverLabel } from "../../domain";
import { useStore } from "../../state/store";
import { REGION_NAME } from "../fieldradar/useFieldData";

const W = 520, H = 190, PAD = { l: 38, r: 12, t: 12, b: 24 };
const COLOR: Record<string, string> = { SE_SKANE: "#e2a842", FI_SW: "#7fc4b8" };
const VS = { better: "Better than today's plan", same: "About the same as today's plan", worse: "Worse than today's plan" } as const;

function HarvestChart({ crop, now, base, years }: { crop: string; now: RegionYear[]; base: RegionYear[]; years: number[] }) {
  const pick = (rows: RegionYear[], region: string) => rows.filter((r) => r.crop === crop && r.region === region).sort((a, b) => a.year - b.year);
  const regions = [...new Set(now.filter((r) => r.crop === crop).map((r) => r.region))];
  const all = [...now, ...base].filter((r) => r.crop === crop).map((r) => r.change_vs_baseline_pct);
  if (!all.length) return null;
  const lo = Math.min(-25, ...all) - 3, hi = Math.max(10, ...all) + 3;
  const x = (y: number) => PAD.l + ((y - years[0]) / Math.max(1, years[years.length - 1] - years[0])) * (W - PAD.l - PAD.r);
  const yy = (v: number) => PAD.t + ((hi - v) / (hi - lo)) * (H - PAD.t - PAD.b);
  const path = (rows: RegionYear[]) => rows.map((r, i) => `${i ? "L" : "M"}${x(r.year).toFixed(1)},${yy(r.change_vs_baseline_pct).toFixed(1)}`).join(" ");
  const ticksY = [-20, -10, 0, 10].filter((v) => v > lo && v < hi);
  return (
    <figure className="harvest">
      <figcaption>{crop.replace(/_/g, " ")} harvest vs the 1991–2020 normal, each year (%)</figcaption>
      <svg viewBox={`0 0 ${W} ${H}`} className="harvest-svg" role="img" aria-label={`${crop} harvest change by year`}>
        {ticksY.map((v) => (
          <g key={v}>
            <line x1={PAD.l} x2={W - PAD.r} y1={yy(v)} y2={yy(v)} className={v === -20 ? "bad-line" : "grid-line"} />
            <text x={PAD.l - 6} y={yy(v) + 3} textAnchor="end" className="axis-t">{v > 0 ? "+" : ""}{v}</text>
          </g>
        ))}
        {years.filter((y) => y % 5 === 0 || y === years[0]).map((y) => <text key={y} x={x(y)} y={H - 6} textAnchor="middle" className="axis-t">{y}</text>)}
        <text x={W - PAD.r} y={yy(-20) - 4} textAnchor="end" className="bad-t">bad harvest (under 80 %)</text>
        {regions.map((r) => (
          <g key={r}>
            <path d={path(pick(base, r))} className="line-base" stroke={COLOR[r]} />
            <path d={path(pick(now, r))} className="line-now" stroke={COLOR[r]} />
          </g>
        ))}
      </svg>
      <div className="harvest-key">
        {regions.map((r) => <span key={r}><i style={{ background: COLOR[r] }} />{REGION_NAME[r as keyof typeof REGION_NAME]}</span>)}
        <span><i className="dash" />today's plan</span><span><i className="solid" />this plan</span>
      </div>
    </figure>
  );
}

export function SimCard({ spec, heard }: { spec: ScenarioSpec; heard: string[] }) {
  const r = useSimulation(spec);
  const baseId = `current_plan_${spec.climate ?? "ssp245"}`;
  const base = useQuery({ queryKey: ["scenario", baseId], queryFn: () => get<SimResult>(`/api/scenario/${baseId}`), staleTime: Infinity });
  const runSpec = useStore((s) => s.runSpec);
  const crop = (spec.levers ?? []).map((l) => ("crop" in l ? l.crop : undefined)).find((c) => c && c !== "all") ?? "pea";
  if (r.isLoading || (!r.data && r.isFetching)) {
    return <div className="bubble bot sim-card"><div className="sim-running"><span className="spinner" />Simulating {heard.length ? heard.join(", ") : "your plan"} on every year to {spec.horizon_end ?? 2040}…</div></div>;
  }
  if (r.error || !r.data) return <div className="bubble bot err">{String(r.error ?? "no result")}</div>;
  const d = r.data, m = d.meters;
  const alerts = d.alerts.filter((a) => a.severity === "critical").length;
  return (
    <div className="bubble bot sim-card">
      <div className="sim-kicker">Simulated · {d.years.length} years · {(spec.levers ?? []).map(leverLabel).join(" + ") || "today's plan"}</div>
      <div className="sim-head">
        <div><div className="fact-label">€ at risk a year</div><div className="sim-big">{m.eur_at_risk_per_year}</div></div>
        <div className={`sim-vs vs-${m.vs_current_plan}`}>{VS[m.vs_current_plan]}</div>
      </div>
      {base.data ? <HarvestChart crop={crop} now={d.regions} base={base.data.regions} years={d.years} /> : null}
      <dl className="result-meters">
        <dt>Import CO2e</dt><dd>{m.co2e_direction}</dd>
        <dt>Critical alerts</dt><dd>{alerts} in {d.years.length} years</dd>
        <dt>Confidence</dt><dd>{m.confidence} <span className="muted small">({m.confidence_why.join("; ")})</span></dd>
      </dl>
      {d.better ? <p className="small muted">The engine also found: {d.better.spec.label} (saves {d.better.saves} a year).</p> : null}
      <button className="btn-run" onClick={() => runSpec(spec)}>Show it on the map</button>
    </div>
  );
}
