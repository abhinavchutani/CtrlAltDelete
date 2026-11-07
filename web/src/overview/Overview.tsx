// The landing page: the problem (money at risk from weather), the fix the model found, what it is built on, then the
// chosen year at a glance. Every number comes from the API; € only as bands. Synthetic data, said on the page.
import { useEffect } from "react";
import { useProvenance } from "../api/hooks";
import type { Alert, Region } from "../api/types";
import { Drop, Euro, Leaf, Play } from "../components/Icons";
import { CLIMATE_LABEL } from "../domain";
import { DecisionBoard } from "../features/board/DecisionBoard";
import { cropName, droughtLevel, REGION_NAME, useFieldData } from "../features/fieldradar/useFieldData";
import { HedgeChart } from "../features/hedge/HedgeChart";
import { Meters } from "../features/meters/Meters";
import { PathwaysGantt } from "../features/pathways/PathwaysGantt";
import { holds } from "../features/plans/planMeta";
import { useSearch } from "../state/search";
import { START_YEAR, useStore } from "../state/store";

const LEVEL = { low: "Low", medium: "Medium", high: "High" } as const;
const KIND: Record<string, string> = {
  drought_flowering: "× drought at flowering", heat_flowering: "× heat at flowering", waterlogging: "× waterlogging",
  wet_harvest: "× wet harvest", blight_weather: "× blight weather", beetle_weather: "× pollen-beetle weather",
  supply_shortfall: "× supply shortfall", risk_threshold: "× risk threshold", assumption: "× assumption",
};
const plain = (s: string) => s.replace(/SE_SKANE/g, "Skåne").replace(/FI_SW/g, "SW Finland");
const fmt = (n: number) => n.toLocaleString("en-GB");
const millions = (n: number) => (n >= 1e6 ? `${(n / 1e6).toFixed(1)} million` : fmt(n));

function Hero({ onAll }: { onAll: () => void }) {
  const d = useFieldData();
  const s = useSearch();
  const setTab = useStore((x) => x.setTab);
  const setYear = useStore((x) => x.setYear);
  const setPlaying = useStore((x) => x.setPlaying);
  const selectAlert = useStore((x) => x.selectAlert);
  const spec = d.sim.data?.spec;
  const climate = spec?.climate ?? "ssp245", horizon = spec?.horizon_end ?? 2040;
  useEffect(() => { void s.start(climate, horizon); }, [climate, horizon]); // eslint-disable-line react-hooks/exhaustive-deps
  const best = s.best ? s.candidates[s.best] : null;
  const h = best ? holds(best) : null;
  // what the alerts on this path are about, counted (e.g. "6 flowering droughts, 2 heat at flowering")
  const kinds = new Map<string, number>();
  for (const a of d.sim.data?.alerts ?? []) kinds.set(a.kind, (kinds.get(a.kind) ?? 0) + 1);
  const causes = [...kinds.entries()].sort((a, b) => b[1] - a[1])
    .map(([k, n]) => `${n} ${(KIND[k] ?? k.replace(/_/g, " "))}`).join(", ");
  const watch = () => { selectAlert(null); setTab("map"); setYear(START_YEAR); setPlaying(true); };
  const runShow = useStore((x) => x.runSpec);
  return (
    <section className="hero" data-tour="hero">
      <div className="hero-kicker">{START_YEAR}–{horizon} · {CLIMATE_LABEL[climate]} · today's plan · synthetic data</div>
      <h1 className="hero-title">
        {s.plan ? <>On this weather path, <em>{s.plan.eur_at_risk_per_year}</em> a year of contract-crop supply is at risk.</>
          : "Working out what the weather puts at risk…"}
      </h1>
      {s.plan ? (
        <p className="hero-sub">{s.plan.costly_years} of the {s.years} years put €250k or more at risk; the worst year, {s.plan.worst_year}.
          {causes ? ` The alerts on this path: ${causes}.` : ""}</p>
      ) : null}
      <div className="hero-fix">
        <div className="hero-fix-label">{s.status === "done" ? `The best of ${Object.keys(s.candidates).length} simulated plans` : "Finding the best plan"}</div>
        {s.status === "running" ? (
          <div className="finder-run">
            <div className="finder-count">Simulating plan {Math.max(1, s.done)} of {s.total || "…"}</div>
            <div className="bar"><span style={{ width: `${s.total ? (100 * s.done) / s.total : 0}%` }} /></div>
          </div>
        ) : best ? (
          <>
            <div className="hero-fix-plan">{best.label}</div>
            <div className="hero-fix-stats">
              <span><strong className="vs-better">saves {best.saves}</strong> a year</span>
              <span>years over €250k: {best.plan_costly_years} → <strong>{best.costly_years}</strong></span>
              {h ? <span>{h.ok === h.of ? "still better in both other futures" : `better in ${h.ok} of ${h.of} other futures`}</span> : null}
            </div>
          </>
        ) : s.status === "done" ? <div className="muted">No plan beat today's plan on this path.</div>
          : s.status === "error" ? <div className="sev-critical small">{s.error}</div> : null}
        <div className="hero-actions">
          <button className="btn-run" onClick={watch}><Play size={14} /> Watch the years on the map</button>
          {best ? <button className="btn-ghost" onClick={() => runShow({ climate, horizon_end: horizon, levers: best.levers, label: best.label })}>Show the best plan</button> : null}
          {s.status === "done" ? <button className="btn-ghost" onClick={onAll}>All {Object.keys(s.candidates).length} plans</button> : null}
        </div>
      </div>
    </section>
  );
}

function BuiltOn() {
  const p = useProvenance();
  if (!p.data) return null;
  const x = p.data;
  const facts: [string, string][] = [
    [fmt(x.farms), "contract farms"],
    [fmt(x.parcels), `fields, crop records ${x.crop_history_years[0]}–${x.crop_history_years[1]}`],
    [fmt(x.fi_yield_records), `Finnish harvest records, ${x.fi_yield_years[0]}–${x.fi_yield_years[1]}`],
    [fmt(x.se_delivery_records), `Skåne pea deliveries, ${x.se_delivery_years[0]}–${x.se_delivery_years[1]}`],
    [millions(x.weather_days), `days of weather, ${x.weather_cells} grid cells, ${x.weather_years[0]}–${x.weather_years[1]}`],
    [String(x.climate_paths.length), `climate futures to ${x.climate_years[1]}`],
  ];
  return (
    <section className="built-on" aria-label="What the model is built on" data-tour="built-on">
      <div className="built-head">
        <h2>Built on the Apetit data pack</h2>
        <span className="muted small">Counted from the data the model reads. The pack is synthetic: not Apetit's real figures or farms.</span>
      </div>
      <div className="built-facts">
        {facts.map(([n, l]) => <div key={l} className="built-fact"><div className="built-n">{n}</div><div className="built-l">{l}</div></div>)}
      </div>
      {x.backtest ? (
        <p className="backtest">
          <strong>Checked against harvests it never saw.</strong> Trained on years up to {x.backtest.train_until}, then tested on
          {" "}{x.backtest.test_years.join(", ")}: total production off by <strong>{x.backtest.model_error_pct} %</strong>, against
          {" "}{x.backtest.baseline_error_pct} % for a simple farm-average guess.
        </p>
      ) : null}
    </section>
  );
}

/** The landing page. */
export function Overview({ onAll }: { onAll: () => void }) {
  const d = useFieldData();
  const year = useStore((s) => s.year);
  const setTab = useStore((s) => s.setTab);
  const selectAlert = useStore((s) => s.selectAlert);
  const sim = d.sim.data;
  const w = d.stats.worst;
  const dry = (Object.entries(d.stats.drought) as [Region, number | undefined][])
    .filter(([, v]) => v !== undefined).sort((a, b) => (b[1] ?? 0) - (a[1] ?? 0))[0];
  const alerts = [...(sim?.alerts ?? [])].sort((a, b) => a.year - b.year);
  const show = (a: Alert) => { selectAlert(a); setTab("map"); };
  return (
    <div className="page overview" aria-label="Overview">
      <Hero onAll={onAll} />
      <BuiltOn />

      <header className="page-head">
        <h2 className="section-title">{year} at a glance</h2>
        <p className="muted">Change the year on the map; this follows it.</p>
      </header>
      <div className="tiles">
        <div className="tile">
          <span className="tile-icon good"><Leaf /></span>
          <div className="tile-value">{d.stats.healthPct ?? "—"}{d.stats.healthPct !== undefined ? " %" : ""}</div>
          <div className="tile-label">of farms on track</div>
        </div>
        <div className="tile">
          <span className="tile-icon warn"><Euro /></span>
          <div className="tile-value">{w?.band ?? "—"}</div>
          <div className="tile-label">at risk, worst crop{w ? `: ${REGION_NAME[w.region]} ${cropName(w.crop)}` : ""}</div>
        </div>
        <div className="tile">
          <span className="tile-icon bad"><Drop /></span>
          <div className="tile-value">{dry ? LEVEL[droughtLevel(dry[1]!)] : "—"}</div>
          <div className="tile-label">drought{dry ? `, driest region: ${REGION_NAME[dry[0]]}` : ""}</div>
        </div>
      </div>

      <section className="card">
        <h2>Problems ahead on this path</h2>
        {alerts.length === 0 ? <p className="muted">No alerts on this path.</p> : (
          <ul className="watch-list">
            {alerts.map((a) => (
              <li key={a.id}>
                <span className={`sev-dot ${a.severity}`} aria-label={a.severity} />
                <span className="watch-year">{a.year}</span>
                <span className="watch-title">{plain(a.title)}</span>
                <span className="watch-eur">{a.eur_at_risk ?? ""}</span>
                <button className="link-btn" onClick={() => show(a)}>Show on map</button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <details className="card more">
        <summary>More detail: meters, hedge, pathways, decision board</summary>
        <div className="more-body">
          <Meters />
          <HedgeChart />
          <PathwaysGantt />
          <DecisionBoard />
        </div>
      </details>
    </div>
  );
}
