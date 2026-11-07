// The Map tab: the map, the lens card (top-left), the plan bar / plan sheet (top-right), the season pill (bottom).
import { useEffect, useMemo, useState } from "react";
import { useOutlook } from "../../api/hooks";
import type { Region } from "../../api/types";
import { Pause, Play } from "../../components/Icons";
import { Assumption, REGION_NAME, SeasonStrip, Segmented, StatusLegend } from "../../components/ui";
import { seasonMarks, useBestPlan } from "../../overview/data";
import { FUTURE_LABEL, holds } from "../plans/planMeta";
import { HORIZON, START_YEAR, useStore, type Lens } from "../../state/store";
import { LENS_RULE, useFieldData } from "../fieldradar/useFieldData";
import { MapView } from "./MapView";
import { useIsolate } from "./isolate";

const LENSES: { key: Lens; label: string }[] = [
  { key: "overall", label: "Overall" }, { key: "drought", label: "Drought" }, { key: "heat", label: "Heat" }, { key: "rain", label: "Rain" },
];
const PLAY_MS = 1400;
const LENS_WORD: Record<Lens, string> = { overall: "have a bad year", drought: "are very dry at flowering", heat: "are hot at flowering", rain: "are short of rain" };

function LensCard({ satellite, setSatellite }: { satellite: boolean; setSatellite: (v: boolean) => void }) {
  const year = useStore((s) => s.year);
  const lens = useStore((s) => s.lens);
  const setLens = useStore((s) => s.setLens);
  const d = useFieldData();
  const ref = useIsolate<HTMLElement>();
  const worst = (Object.entries(d.counts) as [Region, { risk: number; watch: number; ok: number }][])
    .sort((a, b) => b[1].risk - a[1].risk)[0];
  const total = Object.values(d.counts).reduce((s, c) => s + c.risk, 0);
  return (
    <section className="lens-card glass glass-strong" ref={ref} aria-label="What the map shows" data-tour="lens">
      <div className="eyebrow">{year} season · Pea</div>
      <h2>Which farms have a bad year?</h2>
      <p aria-live="polite">{d.pending && !total ? "Loading the season…" : total
        ? `${total.toLocaleString("en-GB")} pea fields ${LENS_WORD[lens]}${worst && worst[1].risk ? `, most in ${REGION_NAME[worst[0]]}` : ""}.`
        : `No pea fields ${LENS_WORD[lens].replace(/^(have|are) /, "")} this season.`}</p>
      <Segmented label="Colour the fields by" value={lens} onChange={setLens} options={LENSES} />
      <div title={lens === "overall" ? "Farm yield vs its normal: 20 %+ below is a bad year, 10 %+ below is watch" : LENS_RULE[lens].rule}>
        <StatusLegend />
      </div>
      <button type="button" className="link" style={{ marginTop: 10, fontWeight: 500, fontSize: 13 }} aria-pressed={satellite}
        onClick={() => setSatellite(!satellite)}>{satellite ? "Back to the light map" : "Satellite view"}</button>
    </section>
  );
}

function PlanPanel() {
  const open = useStore((s) => s.planSheetOpen);
  const setOpen = useStore((s) => s.setPlanSheet);
  const planLevers = useStore((s) => s.planLevers);
  const showPlan = useStore((s) => s.showPlan);
  const openSheet = useStore((s) => s.openSheet);
  const prefill = useStore((s) => s.prefill);
  const plan = useBestPlan();
  const ref = useIsolate<HTMLElement>();
  const b = plan.best;
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, setOpen]);
  if (!b) {
    return plan.status === "running" ? (
      <div className="plan-bar glass glass-strong" ref={ref}>
        <div><div className="t">Finding the best plan</div><div className="s">Simulating plan {Math.max(1, plan.done)} of {plan.total || "…"}</div></div>
      </div>
    ) : null;
  }
  if (!open) {
    return (
      <div className="plan-bar glass glass-strong" ref={ref} data-tour="plan-bar">
        <div><div className="t">Best plan saves {b.saves} a year</div><div className="s">Bad years {b.plan_costly_years} → {b.costly_years}</div></div>
        <button type="button" className="btn btn-primary" onClick={() => { showPlan(b.levers, b.label); setOpen(true); }}>Show it</button>
      </div>
    );
  }
  const h = holds(b);
  const on = !!planLevers;
  const others = Object.keys(b.futures ?? {}).map((k) => FUTURE_LABEL[k]?.toLowerCase()).join(" and ");
  return (
    <section className="plan-sheet glass glass-strong" ref={ref} role="dialog" aria-label="Best plan">
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
        <div className="eyebrow">Best of {plan.tested} plans</div>
        <button type="button" className="icon-btn sm" onClick={() => setOpen(false)} aria-label="Close plan">×</button>
      </div>
      <h2>{b.label}</h2>
      <div className="saves">Saves {b.saves} a year</div>
      <Segmented className="plain wide" label="Show on the map" value={on ? "plan" : "today"}
        onChange={(v) => showPlan(v === "plan" ? b.levers : null, v === "plan" ? b.label : null)}
        options={[{ key: "today", label: "Today's plan" }, { key: "plan", label: "With this plan" }]} />
      <div className="tiles2">
        <div className="tile"><div className="k">Bad years</div><div className="v">{b.plan_costly_years} → {b.costly_years}</div></div>
        <div className="tile"><div className="k">Other futures</div>
          <div className="v leaf">{!h ? "Checking…" : h.ok === h.of ? `Still best in ${h.of === 2 ? "both" : "all"}` : `Better in ${h.ok} of ${h.of}`}</div>
          {others ? <div className="k" style={{ fontSize: 13 }}>{others}</div> : null}</div>
      </div>
      {b.assumption ? <Assumption>Heat-tolerant pea benefit is estimated (a 30 % cut in heat losses), not measured.</Assumption> : null}
      <div style={{ display: "flex", gap: 12, marginTop: "auto", flexWrap: "wrap" }}>
        <button type="button" className="btn btn-ghost" onClick={() => prefill("simulate", "What if we ")}>Build my own plan</button>
        <button type="button" className="btn btn-ghost" onClick={(e) => openSheet("plans", e.currentTarget.getBoundingClientRect())}>All {plan.tested}</button>
      </div>
    </section>
  );
}

function SeasonPill() {
  const climate = useStore((s) => s.climate);
  const planLevers = useStore((s) => s.planLevers);
  const year = useStore((s) => s.year);
  const setYear = useStore((s) => s.setYear);
  const playing = useStore((s) => s.playing);
  const setPlaying = useStore((s) => s.setPlaying);
  const o = useOutlook(climate, planLevers);
  const ref = useIsolate<HTMLElement>();
  const years = o.data?.years ?? Array.from({ length: HORIZON - START_YEAR + 1 }, (_, i) => START_YEAR + i);
  const problems = useMemo(() => (o.data?.seasons ?? []).filter((s) => s.status !== "ok").map((s) => s.year), [o.data]);
  // play steps through the problem years only, then stops
  useEffect(() => {
    if (!playing) return;
    const t = setInterval(() => {
      const y = useStore.getState().year;
      const next = problems.find((p) => p > y);
      if (next === undefined) setPlaying(false);
      else setYear(next);
    }, PLAY_MS);
    return () => clearInterval(t);
  }, [playing, problems, setYear, setPlaying]);
  const play = () => {
    if (playing) { setPlaying(false); return; }
    if (!problems.some((p) => p > year) && problems.length) setYear(problems[0]);
    setPlaying(true);
  };
  return (
    <section className="season-pill glass glass-strong" ref={ref} aria-label="Seasons" data-tour="years">
      <button type="button" className="play" onClick={play} aria-label={playing ? "Pause" : "Play the problem years"}>
        {playing ? <Pause size={18} /> : <Play size={18} />}
      </button>
      <SeasonStrip years={years} marks={o.data ? seasonMarks(o.data.seasons) : {}} selected={year} full labelEvery={2}
        onPick={(y) => { setPlaying(false); setYear(y); }} />
      <span className="big-year" aria-live="polite">{year}</span>
    </section>
  );
}

export function MapPage() {
  const [satellite, setSatellite] = useState(false);
  return (
    <>
      <MapView satellite={satellite} />
      <div className="map-ui">
        <LensCard satellite={satellite} setSatellite={setSatellite} />
        <PlanPanel />
        <SeasonPill />
      </div>
    </>
  );
}
