// Layer 1: the widget grid. A widget never lists; each one is a single button that opens its Layer 2.
// Every number comes from /api/radar/outlook, /api/provenance or the plan finder stream.
import type { MouseEvent } from "react";
import type { Outlook, Status } from "../api/types";
import {
  ArrowRight, Ring, Segmented, StatusMark, shortYear,
} from "../components/ui";
import { CLIMATES, useStore, type SheetKind } from "../state/store";
import { BUCKET_LEVEL, cap, typeLabel, useBestPlan, useTodayOutlook } from "./data";
import { OverviewSheets } from "./Sheets";
import { SeasonHighlights } from "./SeasonHighlights";
import { rect, skel, Widget } from "./Widget";

const ASK_FALLBACK = "What helps against drought at flowering in pea?";
const REGION_SHORT: Record<string, string> = { FI_SW: "SW Finland", SE_SKANE: "Skåne" };
/** The Ask tile's prompt, built from the next real issue on this weather path: its year, region and € at risk. */
function askPrompt(o: Outlook | undefined): string {
  const next = o?.issues.filter((i) => i.year >= o.next_season).sort((a, b) => a.year - b.year)[0];
  if (!next || (next.type !== "drought" && next.type !== "heat")) return ASK_FALLBACK;
  const what = next.type === "drought" ? "drought" : "heat";
  return `${next.eur_at_risk ? `${next.eur_at_risk} at risk in ${next.year}: h` : "H"}ow do we protect ${REGION_SHORT[next.region]} peas from ${what} at flowering${next.eur_at_risk ? "" : ` in ${next.year}`}?`;
}
const BAR_H = { 1: 24, 2: 52, 3: 96 } as const;
/** The 15 seasons as bars (height = € bucket, colour = status), next season ringed. */
function SeasonBars({ o }: { o: Outlook }) {
  const risk = o.seasons.filter((s) => s.status === "risk").length;
  return (
    <>
      <div className="bars" style={{ height: 150, marginTop: 30 }} role="img"
        aria-label={`Seasons at risk, ${o.years[0]}–${o.years[o.years.length - 1]}: ${risk} over €250k`}>
        {o.seasons.map((s, i) => (
          <div key={s.year} className={`col ${s.year === o.next_season ? "now" : ""}`}>
            <div className={`bar ${s.status}`} style={{ height: BAR_H[BUCKET_LEVEL[s.bucket] as 1 | 2 | 3] }} />
            <span className="yl">{i % 2 === 0 || s.year === o.next_season ? shortYear(s.year) : "\u200b"}</span>
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

/** A 10 × 10 grid with the share filled: "x in 100". */
function Waffle({ share }: { share: number }) {
  const n = Math.round(share * 100);
  return (
    <svg width={74} height={74} viewBox="0 0 100 100" role="img" aria-label={`${n} in 100 pea fields`} style={{ flex: "none" }}>
      {Array.from({ length: 100 }, (_, i) => (
        <rect key={i} x={(i % 10) * 10 + 1} y={Math.floor(i / 10) * 10 + 1} width={8} height={8} rx={1.5}
          fill={i < n ? "var(--status-risk)" : "var(--surface-sunk)"} />
      ))}
    </svg>
  );
}

/** Farms by how many bad years they get from next season on: the repeat cases are where help pays off. */
function RepeatFarms({ o }: { o: Outlook }) {
  const [none, one, two, more] = o.repeat_bins;
  const rows: { label: string; n: number; s: Status }[] = [
    { label: "3+ bad years", n: more, s: "risk" }, { label: "2 bad years", n: two, s: "risk" },
    { label: "1 bad year", n: one, s: "watch" }, { label: "none", n: none, s: "ok" },
  ];
  const max = Math.max(...rows.map((r) => r.n), 1);
  return (
    <div className="repeat">
      <div>
        <span key={two + more} className="w-fig fig-risk">{(two + more).toLocaleString("en-GB")} farms</span>
        <span className="w-sub" style={{ display: "block" }}>hit 2 or more times by {o.repeat_years[1]}</span>
      </div>
      <div className="hbars" role="img" aria-label={rows.map((r) => `${r.n} farms with ${r.label}`).join(", ")}>
        {rows.map((r) => (
          <div key={r.label} className="hrow">
            <span className="hlab">{r.label}</span>
            <span className="htrack"><span className={`bar ${r.s}`} style={{ width: `${Math.max(2, (100 * r.n) / max)}%` }} /></span>
            <span className="hn">{r.n}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function Overview() {
  const climate = useStore((s) => s.climate);
  const setClimate = useStore((s) => s.setClimate);
  const sheet = useStore((s) => s.sheet);
  const openSheet = useStore((s) => s.openSheet);
  const prefill = useStore((s) => s.prefill);
  const q = useTodayOutlook();
  const plan = useBestPlan();
  const o = q.data;
  const open = (k: SheetKind) => (e: MouseEvent) => openSheet(k, rect(e));
  const risk = o?.issues.filter((i) => i.status === "risk").length ?? 0;
  const watch = o?.issues.filter((i) => i.status === "watch").length ?? 0;
  const byType = new Map<string, number>();
  for (const i of o?.issues ?? []) byType.set(i.type, (byType.get(i.type) ?? 0) + 1);
  const best = plan.best;

  return (
    <main className="page" aria-label="Overview">

      <div className="ov-head" id="radar">
        <h1 className="ov-title">Contract crop overview</h1>
        <div className="ov-controls">
          <Segmented className="glass" label="Weather path" value={climate} onChange={setClimate}
            options={CLIMATES.map((c) => ({ key: c.key, label: c.label }))} />
        </div>
      </div>
      <>
      {q.error ? <p className="err" role="alert">Couldn't load the outlook: {String(q.error)}</p> : null}

      <div className={`grid ${sheet ? "dim" : ""}`} aria-hidden={sheet ? true : undefined}>
        <Widget size="L" label="Crops at risk" cta="See what drives it" onOpen={open("money")} tour="money">
          {o ? (() => {
            const hit = o.next_contracts.filter((c) => c.status !== "ok");
            const tone = hit.some((c) => c.status === "risk") ? "fig-risk" : hit.length ? "fig-harvest" : "fig-leaf";
            return <span key={`${climate}${hit.length}`} className={`w-fig ${tone}`}>{hit.length} of {o.next_contracts.length} crops</span>;
          })() : skel("70%", 64)}
          <span className="w-sub">at risk of costing €100k+ to buy in, next season ({o?.next_season ?? "…"})</span>
          {o ? <SeasonBars o={o} /> : null}
        </Widget>

        <Widget label="Issues ahead" cta={o ? `See the ${o.issues.length}` : "See them"} onOpen={open("issues")} tour="issues">
          <span className="w-row">
            <Ring size={88} stroke={13} label={`${risk} bad-year issues and ${watch} to watch`}
              parts={[{ value: watch, color: "var(--status-watch)" }, { value: risk, color: "var(--status-risk)" }]} />
            <span key={`${climate}${o?.issues.length}`} className="w-fig">{o ? o.issues.length : "…"}</span>
          </span>
          <span className="w-sub">{[...byType.entries()].map(([t, n]) => `${n} ${typeLabel(t).toLowerCase().replace(" at flowering", "")}`).join(" · ")}{byType.size ? " at flowering" : ""}</span>
        </Widget>

        <Widget label="Fields at risk soon" cta="See the farms" onOpen={open("farms-near")}>
          {o ? (
            <span className="w-row" style={{ gap: 14 }}>
              <Waffle share={o.near_fields_hit / Math.max(1, o.pea_fields)} />
              <span key={`${climate}${o.near_fields_hit}`} className="w-fig fig-risk">{Math.round((100 * o.near_fields_hit) / Math.max(1, o.pea_fields))}%</span>
            </span>
          ) : skel(80, 56)}
          <span className="w-sub">of pea fields have a bad year in {o ? `${o.near_years[0]}–${shortYear(o.near_years[1])}` : "…"}</span>
        </Widget>

        <Widget size="M" label="Yield optimizer"
          right={plan.status === "done" ? undefined : "testing plans…"}
          cta={plan.status === "done" ? `See all ${plan.tested} plans` : "See the plans"} tour="plan" onOpen={open("plans")}>
          <div className="w-split">
            <div>
              {best ? <span key={`${climate}${best.saves}`} className="w-fig fig-leaf">Saves {best.saves}</span>
                : plan.status === "done" ? <span className="w-sub">No plan beat today's plan on this path.</span>
                  : plan.status === "error" ? <span className="w-sub err">{plan.error}</span>
                    : <><span className="w-sub">Simulating plan {Math.max(1, plan.done)} of {plan.total || "…"}</span>
                      <div className="progress" style={{ marginTop: 8 }}><span style={{ width: `${plan.total ? (100 * plan.done) / plan.total : 0}%` }} /></div></>}
              {best ? <span className="w-sub">a year · {cap(best.label.toLowerCase())}</span> : null}
            </div>
            {best ? (
              <div className="minibars" role="img" aria-label={`Bad seasons (over €250k) to 2040: ${best.plan_costly_years} today, ${best.costly_years} with the plan`}>
                {[["Today", best.plan_costly_years, "risk"], ["With plan", best.costly_years, "apetit"]].map(([l, n, c]) => (
                  <div key={l as string} className="col">
                    <span className="n">{n}</span>
                    <div className={`bar ${c}`} style={{ height: 8 + 7 * (n as number) }} />
                    <span className="cap">{l}</span>
                  </div>
                ))}
              </div>
            ) : null}
          </div>
        </Widget>

        <section className="w glass S season-tile" aria-label="Upcoming season, on one plausible weather path (not a forecast)"
          title="One plausible weather path on the chosen climate future, not a forecast">
          <span className="w-label">Upcoming season<span className="right">{o?.next_season ?? "…"}</span></span>
          {o ? <SeasonHighlights o={o} climate={climate} /> : skel("90%", 80)}
        </section>

        <button type="button" className="w glass S ask-tile" onClick={() => prefill("ask", askPrompt(o))} data-tour="ask"
          aria-label={`Ask. For example: ${askPrompt(o)}`}>
          <span className="ask-head"><span className="w-fig">Ask</span><span className="ask-arrow" aria-hidden="true"><ArrowRight size={36} /></span></span>
          <span className="w-sub">“{askPrompt(o)}”</span>
        </button>

        <Widget size="M" label="Hit again and again"
          right={o ? `${o.repeat_bins.reduce((x, y) => x + y, 0)} farms, ${o.repeat_years[0]}–${o.repeat_years[1]}` : undefined}
          cta="See the farms" onOpen={open("farms-repeat")}>
          {o ? <RepeatFarms o={o} /> : <div className="minimap skeleton" />}
        </Widget>
      </div>
      </>
      {o ? <OverviewSheets o={o} /> : null}
    </main>
  );
}
