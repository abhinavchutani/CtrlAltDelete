// The right-hand panel on the map: let the model test every plan it can simulate and say which is best,
// or build your own plan from every change the engine knows.
import { useEffect, useState } from "react";
import { useActiveScenario, useAllOptions } from "../../api/hooks";
import type { Lever } from "../../api/types";
import { leverLabel } from "../../domain";
import { Reset } from "../../components/Icons";
import { liveOrder, useSearch } from "../../state/search";
import { useStore } from "../../state/store";
import { COST_LABEL, FUTURE_LABEL, holds, planCost } from "./planMeta";

const VS = { better: "Better than today's plan", same: "About the same as today's plan", worse: "Worse than today's plan" } as const;

function Progress() {
  const s = useSearch();
  const lead = liveOrder(s)[0];
  const last = s.last ? s.candidates[s.last] : null;
  const pct = s.total ? (100 * s.done) / s.total : 0;
  return (
    <div className="finder-run" aria-live="polite">
      <div className="finder-count">Simulating plan {Math.max(1, s.done)} of {s.total || "…"}</div>
      <div className="bar"><span style={{ width: `${pct}%` }} /></div>
      {last ? <div className="finder-last">{last.label}: <strong>{last.eur_at_risk_per_year}</strong> a year</div> : null}
      {lead?.saves ? <div className="finder-lead">Best so far: {lead.label} · saves {lead.saves}</div> : null}
    </div>
  );
}

function Best({ onAll }: { onAll: () => void }) {
  const s = useSearch();
  const options = useAllOptions();
  const runSpec = useStore((x) => x.runSpec);
  const customSpec = useStore((x) => x.customSpec);
  const best = s.best ? s.candidates[s.best] : null;
  if (!best) return <p className="muted">None of the {Object.keys(s.candidates).length} plans beat today's plan on this path.</p>;
  const cost = planCost(best.levers, options.data);
  const h = holds(best);
  const [climate, horizon] = (s.key ?? "ssp245:2040").split(":");
  const showing = customSpec?.label === best.label;
  return (
    <div className="best-plan">
      <div className="best-kicker">Best of {Object.keys(s.candidates).length} simulated plans</div>
      <div className="best-label">{best.label}</div>
      <div className="best-saves">Saves {best.saves} a year</div>
      <dl className="best-facts">
        <dt>€ at risk a year</dt><dd>{s.plan?.eur_at_risk_per_year} → <strong>{best.eur_at_risk_per_year}</strong></dd>
        <dt>Years over €250k</dt><dd>{best.plan_costly_years} → <strong>{best.costly_years}</strong> of {s.years}</dd>
        <dt>Worst year</dt><dd>{s.plan?.worst_year} → <strong>{best.worst_year}</strong></dd>
        {h ? <><dt>Other futures</dt><dd className={h.ok === h.of ? "vs-better" : ""}>{h.ok === h.of ? "still better in both" : `better in ${h.ok} of ${h.of}`}
          <span className="muted small"> ({Object.keys(best.futures ?? {}).map((k) => FUTURE_LABEL[k]).join(", ")})</span></dd></> : null}
        {cost ? <><dt>Cost</dt><dd>{COST_LABEL[cost]}</dd></> : null}
        <dt>Import CO2e</dt><dd>{best.co2e_direction}</dd>
      </dl>
      {best.assumption ? <p className="assume-note">Includes a heat-tolerant pea: its benefit is an assumption, not measured.</p> : null}
      <div className="best-actions">
        <button className="btn-run" disabled={showing}
          onClick={() => runSpec({ climate: climate as never, horizon_end: Number(horizon) as never, levers: best.levers, label: best.label })}>
          {showing ? "On the map" : "Show it on the map"}
        </button>
        <button className="btn-ghost" onClick={onAll}>All {Object.keys(s.candidates).length} plans</button>
      </div>
    </div>
  );
}

// ── build your own ────────────────────────────────────────────────
const CROPS = ["pea", "potato", "carrot", "spinach", "turnip_rape"] as const;
const cropLabel = (c: string) => c.replace(/_/g, " ");
type Form = {
  irrigate: boolean; irrCrop: "pea" | "potato"; irrTarget: "drought_exposed" | "all";
  sow: boolean; sowCrop: string;
  split: boolean; fiShare: number;
  heat: boolean; heatYear: number; heatCut: number;
  area: boolean; areaCrop: string; areaRegion: "FI_SW" | "SE_SKANE"; areaPct: number;
};
const START: Form = { irrigate: true, irrCrop: "pea", irrTarget: "drought_exposed", sow: false, sowCrop: "all", split: false,
  fiShare: 70, heat: false, heatYear: 2030, heatCut: 30, area: false, areaCrop: "pea", areaRegion: "SE_SKANE", areaPct: -10 };

function levers(f: Form): Lever[] {
  const out: Lever[] = [];
  if (f.irrigate) out.push({ type: "irrigate", crop: f.irrCrop, target: f.irrTarget });
  if (f.sow) out.push({ type: "earlier_sowing", crop: f.sowCrop as never });
  if (f.split) out.push({ type: "region_split", crop: "pea", fi_share: f.fiShare / 100 });
  if (f.heat) out.push({ type: "heat_tolerant_variety", crop: "pea", from_year: f.heatYear, penalty_cut: f.heatCut / 100 });
  if (f.area) out.push({ type: "crop_area", crop: f.areaCrop as never, region: f.areaRegion, change_pct: f.areaPct });
  return out;
}

function Builder() {
  const sim = useActiveScenario();
  const runSpec = useStore((x) => x.runSpec);
  const customSpec = useStore((x) => x.customSpec);
  const resetSpec = useStore((x) => x.resetSpec);
  const [f, setF] = useState<Form>(START);
  const set = <K extends keyof Form>(k: K, v: Form[K]) => setF((x) => ({ ...x, [k]: v }));
  const lv = levers(f);
  const busy = !!customSpec && sim.isFetching;
  const run = () => sim.data && runSpec({ climate: sim.data.spec.climate, horizon_end: sim.data.spec.horizon_end, levers: lv,
    label: lv.map(leverLabel).join(" + ") });
  const m = customSpec && !busy ? sim.data?.meters : undefined;
  const row = (on: boolean, toggle: () => void, title: string, body: React.ReactNode) => (
    <div className={`lever-row ${on ? "on" : ""}`}>
      <label className="lever-head"><input type="checkbox" checked={on} onChange={toggle} /> {title}</label>
      {on ? <div className="lever-body">{body}</div> : null}
    </div>
  );
  return (
    <div className="builder">
      {row(f.irrigate, () => set("irrigate", !f.irrigate), "Irrigate", <>
        <select className="select sm" value={f.irrCrop} onChange={(e) => set("irrCrop", e.target.value as Form["irrCrop"])}>
          <option value="pea">pea</option><option value="potato">potato</option></select>
        <select className="select sm" value={f.irrTarget} onChange={(e) => set("irrTarget", e.target.value as Form["irrTarget"])}>
          <option value="drought_exposed">the driest fields</option><option value="all">all fields</option></select>
      </>)}
      {row(f.sow, () => set("sow", !f.sow), "Sow earlier", (
        <select className="select sm" value={f.sowCrop} onChange={(e) => set("sowCrop", e.target.value)}>
          <option value="all">every crop</option>{CROPS.map((c) => <option key={c} value={c}>{cropLabel(c)}</option>)}</select>
      ))}
      {row(f.split, () => set("split", !f.split), "Buy pea from Finland", <>
        <input type="range" min={20} max={90} step={5} value={f.fiShare} onChange={(e) => set("fiShare", Number(e.target.value))} />
        <span className="range-val">{f.fiShare} % Finland · {100 - f.fiShare} % Skåne</span>
      </>)}
      {row(f.heat, () => set("heat", !f.heat), "Heat-tolerant pea", <>
        <select className="select sm" value={f.heatYear} onChange={(e) => set("heatYear", Number(e.target.value))}>
          {Array.from({ length: 14 }, (_, i) => 2027 + i).map((y) => <option key={y} value={y}>from {y}</option>)}</select>
        <input type="range" min={0} max={60} step={5} value={f.heatCut} onChange={(e) => set("heatCut", Number(e.target.value))} />
        <span className="range-val">cuts heat damage by {f.heatCut} % (an assumption)</span>
      </>)}
      {row(f.area, () => set("area", !f.area), "Change crop area", <>
        <select className="select sm" value={f.areaCrop} onChange={(e) => set("areaCrop", e.target.value)}>
          {CROPS.map((c) => <option key={c} value={c}>{cropLabel(c)}</option>)}</select>
        <select className="select sm" value={f.areaRegion} onChange={(e) => set("areaRegion", e.target.value as Form["areaRegion"])}>
          <option value="SE_SKANE">in Skåne</option><option value="FI_SW">in SW Finland</option></select>
        <input type="range" min={-50} max={50} step={5} value={f.areaPct} onChange={(e) => set("areaPct", Number(e.target.value))} />
        <span className="range-val">{f.areaPct > 0 ? "+" : ""}{f.areaPct} % area</span>
      </>)}
      <button className="btn-run" onClick={run} disabled={!lv.length || !sim.data || busy}>
        {busy ? "Simulating…" : `Simulate my plan (${lv.length} change${lv.length === 1 ? "" : "s"})`}
      </button>
      {customSpec ? (
        <div className="result">
          <div className="result-head">
            <span className="small muted">On the map: {customSpec.label ?? "your plan"}</span>
            <button className="link-btn" onClick={resetSpec}><Reset size={14} /> Today's plan</button>
          </div>
          {m ? (
            <dl className="result-meters">
              <dt>€ at risk a year</dt><dd>{m.eur_at_risk_per_year}</dd>
              <dt>Compared</dt><dd className={`vs-${m.vs_current_plan}`}>{VS[m.vs_current_plan]}</dd>
              <dt>Import CO2e</dt><dd>{m.co2e_direction}</dd>
              <dt>Confidence</dt><dd>{m.confidence}</dd>
            </dl>
          ) : sim.error ? <p className="small sev-critical">{String(sim.error)}</p> : <p className="small muted">Simulating…</p>}
        </div>
      ) : null}
    </div>
  );
}

export function PlanFinder({ onAll }: { onAll: () => void }) {
  const s = useSearch();
  const sim = useActiveScenario();
  const [own, setOwn] = useState(false);
  const climate = sim.data?.spec.climate ?? "ssp245";
  const horizon = sim.data?.spec.horizon_end ?? 2040;
  const key = `${climate}:${horizon}`;
  // a different future picked in View → its own search (the server caches each one)
  const stale = s.key !== null && s.key !== key;
  useEffect(() => { if (stale && s.status !== "running") void s.start(climate, horizon); }, [stale]); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <section className="glass side-panel finder" aria-label="Find the best plan" data-tour="change">
      <h2 className="panel-title">Find the best plan</h2>
      {s.status === "idle" ? (
        <>
          <p className="hint">The model tries every change it can simulate, alone and combined, over {sim.data?.years.length ?? 15} years
            of weather, then re-checks the best ones in the two other climate futures.</p>
          <button className="btn-run" onClick={() => s.start(climate, horizon)}>Run the plan finder</button>
        </>
      ) : s.status === "running" ? <Progress /> : s.status === "error" ? (
        <><p className="small sev-critical">{s.error}</p><button className="btn-ghost" onClick={() => { useSearch.setState({ key: null, status: "idle" }); }}>Try again</button></>
      ) : <Best onAll={onAll} />}
      <button className="own-toggle" onClick={() => setOwn(!own)} aria-expanded={own}>
        {own ? "▾" : "▸"} Build your own plan
      </button>
      {own ? <Builder /> : null}
    </section>
  );
}
