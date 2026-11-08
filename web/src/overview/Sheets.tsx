// Layers 2 + 3 of the Overview: the sheets that open over the grid. Each ends in its receipt.
import { useState } from "react";
import { useOutlook, useSolutions } from "../api/hooks";
import type { Issue, Outlook, Status } from "../api/types";
import {
  Crumbs, Receipt, REGION_NAME, Segmented, Sheet, SourceChip, StatusMark, shortYear,
} from "../components/ui";
import { PlansTable } from "../features/plans/PlansTable";
import { climatePath, useStore } from "../state/store";
import { BUCKET_LEVEL, cap, issueHeadline, mostlyIn, typeLabel, useBestPlan, word } from "./data";

const CLIMATE_NOTE = { ssp126: "Low emissions = SSP1-2.6", ssp245: "Middle path = SSP2-4.5", ssp585: "High emissions = SSP5-8.5" } as const;
const sign = (n: number) => (n > 0 ? `+${n}` : n < 0 ? `−${Math.abs(n)}` : "0");

function IssuesSheet({ o, onClose }: { o: Outlook; onClose: () => void }) {
  const sheet = useStore((s) => s.sheet);
  const climate = useStore((s) => s.climate);
  const [sel, setSel] = useState<string | null>(sheet?.issueId ?? o.issues.find((i) => i.status === "risk")?.id ?? o.issues[0]?.id ?? null);
  const issue = o.issues.find((i) => i.id === sel) ?? null;
  const groups = new Map<string, Issue[]>();
  for (const i of o.issues) groups.set(i.type, [...(groups.get(i.type) ?? []), i]);
  const seasons = new Set(o.issues.map((i) => i.year)).size;
  const send = useStore((s) => s.send);
  const hz = issue ? ({ drought: "H1", heat: "H2" } as Record<string, string>)[issue.type] : undefined;
  const sols = useSolutions(hz ? [hz] : [], climate);
  const help = (i: Issue) => send(`What helps against ${typeLabel(i.type).toLowerCase()} in pea?`, "ask");
  return (
    <Sheet label="Issues ahead" from={sheet?.from} onClose={onClose}>
      <div className="sheet-head"><div>
        <Crumbs items={[{ label: "Overview", onClick: onClose }, { label: "Issues ahead" }]} />
        <h2 className="sheet-title">{o.issues.length} issues in {seasons} seasons</h2>
        <p className="sheet-sub">{cap(climatePath(climate))}, {o.years[0]}–{o.years[o.years.length - 1]}. Tap one to see what happens that season.</p>
      </div></div>
      <div className="issues-body">
        <div>
          {[...groups.entries()].map(([type, list]) => (
            <section key={type} aria-label={typeLabel(type)}>
              <h3 className="group-h eyebrow"><StatusMark status={list.some((i) => i.status === "risk") ? "risk" : "watch"} size={13} />
                {typeLabel(type)} · {list.length}</h3>
              {list.map((i) => (
                <button key={i.id} type="button" className="issue-row" aria-current={i.id === sel} onClick={() => setSel(i.id)}>
                  <StatusMark status={i.status} size={16} />
                  <span className="yr">{i.year}</span>
                  <span>{typeLabel(i.type)} <span className="muted">· {REGION_NAME[i.region]}</span></span>
                  <span className="eur">{i.eur_at_risk ?? "—"} at risk</span>
                  <span className="chev" aria-hidden="true">›</span>
                </button>
              ))}
            </section>
          ))}
        </div>
        {issue ? (
          <aside className="detail" aria-live="polite">
            <div className={`detail-kicker ${issue.status}`}><StatusMark status={issue.status} size={13} /> {issue.year} · {typeLabel(issue.type)}</div>
            <h3>{issueHeadline(issue)}</h3>
            <div className="stat-tiles">
              <div className="stat-tile rain"><div className="k">Rain at flowering</div>
                <div className="v">{issue.rain_vs_normal_pct === null ? "—" : `${sign(issue.rain_vs_normal_pct)}%`}</div>
                <div className="s">vs 1991–2020 normal</div></div>
              <div className="stat-tile temp"><div className="k">Temperature</div>
                <div className="v">{issue.temp_vs_normal_c === null ? "—" : `${sign(issue.temp_vs_normal_c)} °C`}</div>
                <div className="s">vs normal</div></div>
            </div>
            <p className="line">{issue.fields_below.toLocaleString("en-GB")} pea fields on {issue.farms_below} farms in {REGION_NAME[issue.region]} fall 10 %+ below their normal yield. {issue.eur_at_risk ? `${issue.eur_at_risk} at risk.` : ""}</p>
            {sols.data?.length ? (
              <div className="helps">
                <div className="eyebrow">What helps, from research</div>
                <ul>{sols.data.slice(0, 3).map((x) => (
                  <li key={x.id}><b>{x.title}</b><span className="muted"> · {x.evidence.length} source{x.evidence.length === 1 ? "" : "s"}</span></li>
                ))}</ul>
              </div>
            ) : null}
            <div className="actions">
              <button type="button" className="btn btn-primary" onClick={() => help(issue)}>See every measure and its sources</button>
            </div>
            <div className="know">How do we know? {issue.sources.map((s) => <SourceChip key={s.node_id + s.label} s={s} />)}</div>
          </aside>
        ) : null}
      </div>
    </Sheet>
  );
}

const Y_AXIS = ["€250k–1M", "€100–250k", "under €100k"];

function MoneySheet({ o, onClose }: { o: Outlook; onClose: () => void }) {
  const sheet = useStore((s) => s.sheet);
  const climate = useStore((s) => s.climate);
  const openSheet = useStore((s) => s.openSheet);
  const plan = useBestPlan();
  const [withPlan, setWithPlan] = useState<"today" | "best">("today");
  const planned = useOutlook(climate, plan.best && withPlan === "best" ? plan.best.levers : null);
  const shown = withPlan === "best" && plan.best ? planned.data ?? o : o;
  const types = new Map<string, Issue[]>();
  for (const i of o.issues) types.set(i.type, [...(types.get(i.type) ?? []), i]);
  const bars = shown.seasons;
  const openPlan = () => openSheet("plans");
  return (
    <Sheet label="Money at stake" from={sheet?.from} onClose={onClose}>
      <div className="sheet-head">
        <div>
          <Crumbs items={[{ label: "Overview", onClick: onClose }, { label: "Money at stake" }]} />
          <h2 className="sheet-title"><span className="fig-harvest">{shown.money}</span> a year at stake</h2>
          <p className="sheet-sub">{cap(word(shown.costly_years))} seasons go past €250k. The worst reaches {shown.worst_band}.</p>
        </div>
        <Segmented className="plain" label="Plan" value={withPlan} onChange={setWithPlan}
          options={[{ key: "today", label: "Today's plan" }, { key: "best", label: plan.best ? "With the best plan" : "Best plan (finding…)" }]} />
      </div>
      <div className="chart-card">
        <div className="y-axis" aria-hidden="true">{Y_AXIS.map((l) => <span key={l}>{l}</span>)}</div>
        <div className="bars" role="img"
          aria-label={`${withPlan === "best" ? "With the best plan" : "Today's plan"}: ${shown.costly_years} of ${bars.length} seasons at €250k or more`}>
          {bars.map((s) => (
            <div key={s.year} className="col">
              <div className={`bar ${s.status}`} style={{ height: ({ 1: 44, 2: 104, 3: 164 } as const)[BUCKET_LEVEL[s.bucket] as 1 | 2 | 3] }}
                title={`${s.year}: ${s.band}`} />
              <span className="yl">{shortYear(s.year)}</span>
            </div>
          ))}
        </div>
      </div>
      <div className="cards3">
        {[...types.entries()].slice(0, 2).map(([t, list]) => {
          const r = mostlyIn(list);
          const status: Status = list.some((i) => i.status === "risk") ? "risk" : "watch";
          return (
            <div key={t} className="card">
              <div className="h"><StatusMark status={status} size={14} /> {typeLabel(t)}</div>
              <div className="big">{list.length} season{list.length === 1 ? "" : "s"}</div>
              <div className="muted">{r ? `Mostly ${REGION_NAME[r]}` : ""}</div>
              <button type="button" className="link" style={{ alignSelf: "flex-start" }}
                onClick={() => openSheet("issues", null, list[0]?.id)}>See the seasons ›</button>
            </div>
          );
        })}
        <div className="card leafy">
          <div className="h">What fixes most of it</div>
          {plan.best ? (
            <>
              <div className="plan">{cap(plan.best.label.toLowerCase())}</div>
              <div className="muted">Saves {plan.best.saves} a year · bad years {plan.best.plan_costly_years} → {plan.best.costly_years}</div>
              <button type="button" className="link" style={{ alignSelf: "flex-start" }} onClick={openPlan}>Open the plan ›</button>
            </>
          ) : <div className="muted">{plan.status === "running" ? `Simulating plan ${Math.max(1, plan.done)} of ${plan.total || "…"}` : "No plan beat today's plan."}</div>}
        </div>
      </div>
      <Receipt sources={o.sources} foot={<>{CLIMATE_NOTE[climate]}. Synthetic data pack, not Apetit's real figures. € at risk covers every contract crop (pea, potato, carrot, spinach, turnip rape).</>} />
    </Sheet>
  );
}

/** Layer 2 for the two field widgets: which farms, where, and in which seasons they have a bad year. */
function FarmsSheet({ o, near, onClose }: { o: Outlook; near: boolean; onClose: () => void }) {
  const sheet = useStore((s) => s.sheet);
  const [y0, y1] = near ? o.near_years : o.repeat_years;
  const rows = o.farms_hit
    .map((f) => ({ ...f, years: f.bad_years.filter((y) => y >= y0 && y <= y1) }))
    .filter((f) => (near ? f.years.length >= 1 && f.pea_fields > 0 : f.years.length >= 2));
  const fields = rows.reduce((n, f) => n + f.pea_fields, 0);
  const byRegion = new Map<string, number>();
  for (const f of rows) byRegion.set(f.region, (byRegion.get(f.region) ?? 0) + 1);
  const years = Array.from({ length: y1 - y0 + 1 }, (_, i) => y0 + i);
  return (
    <Sheet label={near ? "Fields at risk soon" : "Hit again and again"} from={sheet?.from} onClose={onClose}>
      <div className="sheet-head"><div>
        <Crumbs items={[{ label: "Overview", onClick: onClose }, { label: near ? "Fields at risk soon" : "Hit again and again" }]} />
        <h2 className="sheet-title">{near
          ? `${rows.length} farms, ${fields.toLocaleString("en-GB")} pea fields, a bad year in ${y0}–${shortYear(y1)}`
          : `${rows.length} farms hit 2 or more times by ${y1}`}</h2>
        <p className="sheet-sub">{[...byRegion.entries()].map(([r, n]) => `${n} in ${REGION_NAME[r as keyof typeof REGION_NAME]}`).join(" · ")}.
          A bad year: the farm's yield 20 %+ below its normal. One plausible weather path, not a forecast.</p>
      </div></div>
      <div className="farm-table" role="table" aria-label="Farms and their bad years"
        style={{ ["--cols" as string]: `minmax(150px, 1.4fr) 70px repeat(${years.length}, minmax(18px, 1fr))` }}>
        <div className="farm-row head" role="row">
          <span role="columnheader">Farm</span><span role="columnheader">Pea fields</span>
          {years.map((y) => <span key={y} role="columnheader" className="yc">{shortYear(y)}</span>)}
        </div>
        {rows.slice(0, 60).map((f) => (
          <div key={f.farm_id} className="farm-row" role="row">
            <span role="cell"><b>{f.farm_id}</b> <span className="muted">{REGION_NAME[f.region]}</span></span>
            <span role="cell">{f.pea_fields}</span>
            {years.map((y) => (
              <span key={y} role="cell" className="yc">{f.years.includes(y) ? <StatusMark status="risk" size={12} /> : <span className="nodot" />}</span>
            ))}
          </div>
        ))}
      </div>
      {rows.length > 60 ? <p className="muted" style={{ marginTop: 10 }}>Showing the 60 most-hit farms of {rows.length}.</p> : null}
    </Sheet>
  );
}

function PlansSheet({ onClose }: { onClose: () => void }) {
  const sheet = useStore((s) => s.sheet);
  const plan = useBestPlan();
  return (
    <Sheet label="All simulated plans" from={sheet?.from} onClose={onClose}>
      <div className="sheet-head"><div>
        <Crumbs items={[{ label: "Plans" }]} />
        <h2 className="sheet-title">{plan.tested} plans, best first</h2>
        <p className="sheet-sub">Same yield model, weather path and 2025 field mix for every plan. € as ranges, never exact.</p>
      </div></div>
      <PlansTable />
    </Sheet>
  );
}

/** Whichever Overview sheet is open. */
export function OverviewSheets({ o }: { o: Outlook }) {
  const sheet = useStore((s) => s.sheet);
  const close = useStore((s) => s.closeSheet);
  if (!sheet) return null;
  if (sheet.kind === "issues") return <IssuesSheet key={sheet.issueId ?? "issues"} o={o} onClose={close} />;
  if (sheet.kind === "money") return <MoneySheet o={o} onClose={close} />;
  if (sheet.kind === "farms-near" || sheet.kind === "farms-repeat") return <FarmsSheet o={o} near={sheet.kind === "farms-near"} onClose={close} />;
  if (sheet.kind === "plans") return <PlansSheet onClose={close} />;
  return null; // "data" / "report": Problems.tsx; "changes" / "unusual": today/TodaySheets.tsx
}

export { PlansSheet };
