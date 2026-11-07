// The problem, next to its pin on the map: what happens, the month's weather, the € at risk, and what to do about
// it (the model's pick plus every option in the knowledge base), each testable on the spot.
import { useState } from "react";
import { Marker } from "react-map-gl/maplibre";
import { useActiveScenario, useMonths, useOptions, useSimulation } from "../../api/hooks";
import type { AdaptationOption, Alert, Lever, ScenarioSpec } from "../../api/types";
import { Close, Play } from "../../components/Icons";
import { HAZARD_LABEL, leverLabel, withLever } from "../../domain";
import { useStore } from "../../state/store";
import { EvidenceChips } from "../ask/EvidenceChips";
import { REGION_NAME } from "../fieldradar/useFieldData";
import { useIsolate } from "../map/isolate";

const MONTH = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const MONTH_LONG = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
const COST: Record<string, string> = { low: "Low cost", low_med: "Low–medium cost", med: "Medium cost", high: "High cost" };
const ROBUST: Record<string, string> = { no_regret: "No-regret", scenario_dependent: "Depends on the future", maladaptive: "Can backfire", reactive: "Reactive" };
const WINDOW: Record<string, string> = { strategic: "Plan ahead", pre_season: "Before the season", in_season: "During the season" };
const ORDER = { simulated: 0, simulated_with_caveat: 1, assumption: 2 } as const;
const plain = (s: string) => s.replace(/SE_SKANE/g, "Skåne").replace(/FI_SW/g, "SW Finland");
const signed = (n: number, unit: string) => `${n > 0 ? "+" : ""}${n}${unit}`;

type Focus = { region: string; crop: string; year: number; label: string };
const VS_WORD = { better: "better than today's plan", same: "about the same as today's plan", worse: "worse than today's plan" } as const;

/** Run one change on top of the scenario on screen, right here: its effect on this problem (that year, region and
 *  crop) and over the whole horizon. "Apply" puts it on the map. */
export function TestIt({ lever, focus }: { lever: Lever; focus?: Focus }) {
  const sim = useActiveScenario();
  const runSpec = useStore((s) => s.runSpec);
  const [spec, setSpec] = useState<ScenarioSpec | null>(null);
  const r = useSimulation(spec);
  if (!sim.data) return null;
  const base = sim.data.spec;
  if (!spec) return <button className="btn-test" onClick={() => setSpec({ ...withLever(base, lever), label: leverLabel(lever) })}>Test it</button>;
  if (r.isLoading || r.isFetching) return <span className="test-run"><span className="spinner" /> Simulating {sim.data.years.length} years…</span>;
  if (r.error || !r.data) return <span className="test-run sev-critical">{String(r.error ?? "no result")}</span>;
  const m = r.data.meters;
  const cell = (rows: typeof r.data.regions) => focus && rows.find((x) => x.region === focus.region && x.crop === focus.crop && x.year === focus.year);
  const before = cell(sim.data.regions), after = cell(r.data.regions);
  return (
    <div className={`test-result vs-${m.vs_current_plan}`}>
      {before && after ? (
        <span>{focus!.label}: <strong>{before.eur_at_risk}</strong> → <strong>{after.eur_at_risk}</strong> at risk
          {after.change_vs_baseline_pct !== before.change_vs_baseline_pct
            ? ` (harvest ${before.change_vs_baseline_pct > 0 ? "+" : ""}${before.change_vs_baseline_pct} % → ${after.change_vs_baseline_pct > 0 ? "+" : ""}${after.change_vs_baseline_pct} % vs normal)` : ""}</span>
      ) : null}
      <span>Over {r.data.years.length} years: {VS_WORD[m.vs_current_plan]}, {m.eur_at_risk_per_year} a year</span>
      <button className="link-btn" onClick={() => runSpec(spec)}>Apply on the map</button>
    </div>
  );
}

function Solution({ o, focus }: { o: AdaptationOption; focus?: Focus }) {
  return (
    <li className="solution">
      <div className="solution-name">{o.option}</div>
      <div className="solution-tags">
        <span className={`tag-cost ${o.cost_level}`}>{COST[o.cost_level] ?? o.cost_level}</span>
        <span>{WINDOW[o.window] ?? o.window}</span>
        <span>ready in {o.lead_time_yrs[0] === o.lead_time_yrs[1] ? o.lead_time_yrs[0] : `${o.lead_time_yrs[0]}–${o.lead_time_yrs[1]}`} yr</span>
        <span className={o.robustness}>{ROBUST[o.robustness] ?? o.robustness}</span>
        {o.simulated !== "simulated" ? <span className="muted">{o.simulated === "assumption" ? "assumption" : "simulated, with caveat"}</span> : null}
      </div>
      {o.lever ? <TestIt lever={o.lever} focus={focus} /> : <span className="muted small">Not in the model yet: judged from the source ({o.source_name})</span>}
    </li>
  );
}

export function PinCard({ alert: a, position }: { alert: Alert; position: [number, number] }) {
  const sim = useActiveScenario();
  const selectAlert = useStore((s) => s.selectAlert);
  const setPlaying = useStore((s) => s.setPlaying);
  const months = useMonths(a.region, a.year, sim.data?.spec.climate);
  const options = useOptions(a.hazard ?? null, a.crop ?? null);
  const [all, setAll] = useState(false);
  const ref = useIsolate<HTMLDivElement>();
  const m = a.month ? months.data?.months.find((x) => x.month === a.month) : undefined;
  const season = (months.data?.months ?? []).filter((x) => x.month >= 4 && x.month <= 9);
  const maxAbs = Math.max(30, ...season.map((x) => Math.abs(x.precip_anom_pct)));
  const opts = [...(options.data ?? [])].sort((x, y) =>
    (ORDER[x.simulated] ?? 9) - (ORDER[y.simulated] ?? 9) || Number(!x.lever) - Number(!y.lever)
    || (x.robustness === "no_regret" ? 0 : 1) - (y.robustness === "no_regret" ? 0 : 1));
  const shown = all ? opts : opts.slice(0, 4);
  const playOn = () => { selectAlert(null); setPlaying(true); };
  const focus: Focus | undefined = a.crop ? { region: a.region, crop: a.crop, year: a.year,
    label: `${a.year}, ${REGION_NAME[a.region]} ${a.crop}` } : undefined;
  return (
    <Marker longitude={position[0]} latitude={position[1]} anchor="left" offset={[30, -24]} style={{ zIndex: 4 }}>
      <div className="pin-card glass" ref={ref} role="dialog" aria-label={plain(a.title)}>
        <button className="icon-btn card-close" onClick={() => selectAlert(null)} aria-label="Close"><Close size={16} /></button>
        <div className="pin-head">
          <span className={`sev-pill ${a.severity}`}>{a.severity === "critical" ? "Critical" : "Watch"}</span>
          <span className="muted">{a.month ? `${MONTH_LONG[a.month - 1]} ` : ""}{a.year} · {REGION_NAME[a.region]}{a.crop ? ` · ${a.crop}` : ""}</span>
        </div>
        <h3 className="pin-title">{plain(a.title)}</h3>
        <p className="pin-why">{plain(a.why)}</p>

        <div className="pin-facts">
          <div><div className="fact-label">€ at risk this year</div><div className="fact-value">{a.eur_at_risk ?? "—"}</div></div>
          {m ? (
            <div><div className="fact-label">{MONTH_LONG[m.month - 1]} weather</div>
              <div className="fact-value small-v">rain {signed(m.precip_anom_pct, " %")} · {m.tmean_c} °C ({signed(m.tmean_anom_c, " °C")})</div></div>
          ) : null}
        </div>
        {season.length ? (
          <div className="season" aria-label="Rain each month vs normal">
            {season.map((x) => (
              <div key={x.month} className={`season-col ${x.month === a.month ? "on" : ""}`}
                title={`${MONTH[x.month - 1]}: rain ${signed(x.precip_anom_pct, " %")} vs 1991–2020, ${x.hot_days} hot days`}>
                <div className="season-bar">
                  <span className={x.precip_anom_pct >= 0 ? "wet" : "dry"}
                    style={{ height: `${(Math.abs(x.precip_anom_pct) / maxAbs) * 50}%`, [x.precip_anom_pct >= 0 ? "bottom" : "top"]: "50%" }} />
                </div>
                <span>{MONTH[x.month - 1]}</span>
              </div>
            ))}
            <span className="season-note">rain vs normal, Apr–Sep</span>
          </div>
        ) : null}

        <h4 className="pin-sub">What you can do{a.hazard ? ` about ${HAZARD_LABEL[a.hazard] ?? a.hazard}` : ""}</h4>
        {a.suggested_lever ? (
          <div className="model-pick">
            <div className="pick-label">The model's pick for this problem</div>
            <div className="solution-name">{leverLabel(a.suggested_lever).replace(/^\w/, (c) => c.toUpperCase())}</div>
            <TestIt lever={a.suggested_lever} focus={focus} />
          </div>
        ) : null}
        {options.isLoading ? <p className="muted small">Loading solutions…</p> : (
          <ul className="solutions">{shown.map((o) => <Solution key={o.option_id} o={o} focus={focus} />)}</ul>
        )}
        {opts.length > 4 ? (
          <button className="link-btn" onClick={() => setAll(!all)}>{all ? "Show fewer" : `Show all ${opts.length} solutions`}</button>
        ) : null}

        <div className="pin-foot">
          <EvidenceChips evidence={a.evidence ?? []} />
          <button className="btn-run play-on" onClick={playOn}><Play size={14} /> Keep playing</button>
        </div>
      </div>
    </Marker>
  );
}
