// Layer 1: the widget grid. A widget never lists; each one is a single button that opens its Layer 2.
// Every number comes from /api/radar/outlook, /api/provenance or the plan finder stream.
import { useMemo, type MouseEvent } from "react";
import { useGeoFarms } from "../api/hooks";
import type { Outlook, Region, Status } from "../api/types";
import {
  EuroIcon, FieldsIcon, PinIcon, REGION_NAME, Ring, Segmented, SproutIcon, StatusMark, WarnIcon, shortYear,
} from "../components/ui";
import { CLIMATES, climatePath, REGION_VIEW, START_YEAR, useStore, type SheetKind } from "../state/store";
import { BUCKET_LEVEL, cap, typeLabel, useBestPlan, useTodayOutlook } from "./data";
import { OverviewSheets } from "./Sheets";
import { WeatherWatch } from "./WeatherWatch";

const BAR_H = { 1: 24, 2: 52, 3: 96 } as const;
const rect = (e: MouseEvent) => (e.currentTarget as HTMLElement).getBoundingClientRect();

function Widget({ size = "S", label, icon, right, cta, onOpen, children, tour }: {
  size?: "S" | "M" | "L"; label: string; icon: React.ReactNode; right?: React.ReactNode; cta: string;
  onOpen: (e: MouseEvent) => void; children: React.ReactNode; tour?: string;
}) {
  return (
    <button type="button" className={`w glass ${size}`} onClick={onOpen} data-tour={tour}>
      <span className="w-label">{icon}{label}{right ? <span className="right">{right}</span> : null}</span>
      {children}
      <span className="w-cta">{cta} ›</span>
    </button>
  );
}

/** The 15 seasons as bars (height = € bucket, colour = status), with the next costly season and the worst one tagged. */
function SeasonBars({ o, next }: { o: Outlook; next: number | null }) {
  const risk = o.seasons.filter((s) => s.status === "risk").length;
  return (
    <>
      <div className="bars" style={{ height: 150, marginTop: 14 }} role="img"
        aria-label={`Cost of shortfalls by season, ${o.years[0]}–${o.years[o.years.length - 1]}: ${risk} seasons over €250k; next ${next ?? "none"}, worst ${o.worst_year}`}>
        {o.seasons.map((s, i) => (
          <div key={s.year} className="col">
            {s.year === next ? <span className="bar-tag">Next</span> : s.year === o.worst_year ? <span className="bar-tag worst">Worst</span> : null}
            <div className={`bar ${s.status}`} style={{ height: BAR_H[BUCKET_LEVEL[s.bucket] as 1 | 2 | 3] }} />
            <span className="yl" style={s.year === next || s.year === o.worst_year ? { color: "var(--ink)", fontWeight: 700 } : undefined}>
              {i % 2 === 0 || s.year === next || s.year === o.worst_year ? shortYear(s.year) : "\u200b"}</span>
          </div>
        ))}
      </div>
      <div className="legend" style={{ marginTop: 10 }}>
        <span><StatusMark status="risk" size={13} /> over €250k</span>
        <span><StatusMark status="watch" size={13} /> €100–250k</span>
        <span><StatusMark status="ok" size={13} /> under €100k</span>
      </div>
    </>
  );
}

/** Field status by farm in one season, both regions side by side (each drawn in its own box). */
function MiniMap({ o }: { o: Outlook }) {
  const farms = useGeoFarms();
  const pts = useMemo(() => {
    const status = new Map(o.farms_focus.map((f) => [f.farm_id, f.status]));
    const by: Record<Region, { x: number; y: number; s: Status }[]> = { FI_SW: [], SE_SKANE: [] };
    for (const f of farms.data?.features ?? []) {
      const s = status.get(f.properties.farm_id);
      if (s) by[f.properties.region].push({ x: f.geometry.coordinates[0], y: f.geometry.coordinates[1], s });
    }
    return by;
  }, [farms.data, o.farms_focus]);
  const W = 1000, H = 260;
  const box = (r: Region, x0: number) => {
    const p = pts[r];
    if (!p.length) return null;
    const xs = p.map((q) => q.x), ys = p.map((q) => q.y);
    const [a, b, c, d] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
    const sx = (W / 2 - 60) / Math.max(b - a, 1e-6), sy = (H - 60) / Math.max(d - c, 1e-6);
    return p.map((q, i) => (
      <rect key={`${r}${i}`} x={x0 + 30 + (q.x - a) * sx - 7} y={40 + (d - q.y) * sy - 4} width={14} height={9} rx={2}
        fill={`var(--status-${q.s})`} opacity={q.s === "ok" ? 0.75 : 0.95} />
    ));
  };
  const counts = (r: Region) => pts[r].filter((p) => p.s === "risk").length;
  return (
    <div className="minimap" role="img"
      aria-label={`Farm status in ${o.focus_year}: SW Finland ${counts("FI_SW")} farms in a bad year, Skåne ${counts("SE_SKANE")}`}>
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none">
        <line x1={W / 2} x2={W / 2} y1={0} y2={H} stroke="#D9E6EA" strokeWidth={6} />
        {box("FI_SW", 0)}{box("SE_SKANE", W / 2)}
      </svg>
      <span className="lbl" style={{ left: 12 }}>SW Finland</span>
      <span className="lbl" style={{ left: "52%" }}>Skåne</span>
    </div>
  );
}

const skel = (w: number | string, h: number) => <span className="skeleton" style={{ width: w, height: h, display: "block" }} />;

export function Overview() {
  const climate = useStore((s) => s.climate);
  const setClimate = useStore((s) => s.setClimate);
  const sheet = useStore((s) => s.sheet);
  const openSheet = useStore((s) => s.openSheet);
  const setTab = useStore((s) => s.setTab);
  const setYear = useStore((s) => s.setYear);
  const setLens = useStore((s) => s.setLens);
  const flyTo = useStore((s) => s.flyTo);
  const showPlan = useStore((s) => s.showPlan);
  const setPlanSheet = useStore((s) => s.setPlanSheet);
  const q = useTodayOutlook();
  const plan = useBestPlan();
  const o = q.data;
  const open = (k: SheetKind) => (e: MouseEvent) => openSheet(k, rect(e));
  const toMap = (year?: number, region?: Region | null) => {
    if (year) setYear(year);
    setLens("overall");
    if (region) flyTo(REGION_VIEW[region]);
    setTab("map");
  };
  const risk = o?.issues.filter((i) => i.status === "risk").length ?? 0;
  const watch = o?.issues.filter((i) => i.status === "watch").length ?? 0;
  const byType = new Map<string, number>();
  for (const i of o?.issues ?? []) byType.set(i.type, (byType.get(i.type) ?? 0) + 1);
  const next = o?.seasons.find((x) => x.status === "risk" && x.year > START_YEAR)?.year ?? null;
  const best = plan.best;

  return (
    <main className="page" aria-label="Overview">
      <div className="ov-head">
        <div>
          <div className="eyebrow">Contract crop supply outlook</div>
          <h1 className="ov-title">Next 15 seasons, {climatePath(climate)}</h1>
        </div>
        <Segmented className="glass" label="Weather path" value={climate} onChange={setClimate}
          options={CLIMATES.map((c) => ({ key: c.key, label: c.label }))} />
      </div>
      {q.error ? <p className="err" role="alert">Couldn't load the outlook: {String(q.error)}</p> : null}

      <div className={`grid ${sheet ? "dim" : ""}`} aria-hidden={sheet ? true : undefined}>
        <Widget size="L" label="What weather shortfalls will cost us" icon={<EuroIcon />} cta="See what drives it" onOpen={open("money")} tour="money">
          {o ? <span className="w-fig fig-harvest">{o.costly_years} of {o.seasons.length} seasons</span> : skel("70%", 64)}
          <span className="w-sub">cost over €250k each: the extra we pay to buy in the contract crops our farms can't deliver.</span>
          {o ? <SeasonBars o={o} next={next} /> : null}
          {o ? (
            <span className="w-story">
              {next ? <>Next one: <b>{next}</b>. </> : null}Worst: <b>{o.worst_year}</b>, {o.worst_band}. On average <b>{o.money}</b> a year.
            </span>
          ) : null}
        </Widget>

        <Widget label="Issues ahead" icon={<WarnIcon />} cta={o ? `See the ${o.issues.length}` : "See them"} onOpen={open("issues")} tour="issues">
          <span className="w-row">
            <Ring size={88} stroke={13} label={`${risk} bad-year issues and ${watch} to watch`}
              parts={[{ value: watch, color: "var(--status-watch)" }, { value: risk, color: "var(--status-risk)" }]} />
            <span className="w-fig">{o ? o.issues.length : "…"}</span>
          </span>
          <span className="w-sub">{[...byType.entries()].map(([t, n]) => `${n} ${typeLabel(t).toLowerCase().replace(" at flowering", "")}`).join(" · ")}{byType.size ? " at flowering" : ""}</span>
        </Widget>

        <Widget label="Fields at risk" icon={<FieldsIcon />} cta="Show on the map" onOpen={() => toMap(o?.focus_year, o?.worst_region)}>
          {o ? <span className="w-fig fig-risk">{o.fields_risk.toLocaleString("en-GB")}</span> : skel(80, 56)}
          <span className="w-sub">of {o?.pea_fields.toLocaleString("en-GB") ?? "…"} pea fields in {o?.focus_year ?? "…"}</span>
          <span className="w-sub" style={{ color: "var(--risk-ink)", display: "flex", alignItems: "center", gap: 8 }}>
            <StatusMark status="risk" size={12} /> Bad year, worst season
          </span>
        </Widget>

        <Widget size="M" label={plan.status === "done" ? `Best of ${plan.tested} plans` : "Finding the best plan"} icon={<SproutIcon />}
          cta="Open the plan" tour="plan"
          onOpen={() => { if (best) { showPlan(best.levers, best.label); setPlanSheet(true); } else setPlanSheet(true); toMap(); }}>
          <div className="w-split">
            <div>
              {best ? <span className="w-fig fig-leaf">Saves {best.saves}</span>
                : plan.status === "done" ? <span className="w-sub">No plan beat today's plan on this path.</span>
                  : plan.status === "error" ? <span className="w-sub err">{plan.error}</span>
                    : <><span className="w-sub">Simulating plan {Math.max(1, plan.done)} of {plan.total || "…"}</span>
                      <div className="progress" style={{ marginTop: 8 }}><span style={{ width: `${plan.total ? (100 * plan.done) / plan.total : 0}%` }} /></div></>}
              {best ? <span className="w-sub">a year · {cap(best.label.toLowerCase())}</span> : null}
            </div>
            {best ? (
              <div className="minibars" role="img" aria-label={`Seasons over €250k: ${best.plan_costly_years} today, ${best.costly_years} with the plan`}>
                {[["Today", best.plan_costly_years, "risk"], ["With plan", best.costly_years, "apetit"]].map(([l, n, c]) => (
                  <div key={l as string} className="col">
                    <span className="n">{n}</span>
                    <div className={`bar ${c}`} style={{ height: 12 + 10 * (n as number) }} />
                    <span className="cap">{l}</span>
                  </div>
                ))}
              </div>
            ) : null}
          </div>
        </Widget>

        <Widget size="M" label={`Next season's weather: ${START_YEAR + 1}`} icon={<WarnIcon />}
          right="one plausible path, not a forecast" cta="Watch it on the map"
          onOpen={() => { setYear(START_YEAR + 1); toMap(START_YEAR + 1); setLens("rain"); }}>
          <WeatherWatch year={START_YEAR + 1} climate={climate} />
        </Widget>

        <Widget size="M" label={`Where it hurts in ${o?.focus_year ?? "…"}`} icon={<PinIcon />}
          right={o ? `${o.contract_farms.toLocaleString("en-GB")} contract farms${o.worst_region ? ` · ${REGION_NAME[o.worst_region]} worst` : ""}` : undefined}
          cta="Open the map"
          onOpen={() => toMap(o?.focus_year, o?.worst_region)}>
          {o ? <MiniMap o={o} /> : <div className="minimap skeleton" />}
        </Widget>
      </div>
      {o ? <OverviewSheets o={o} /> : null}
    </main>
  );
}
