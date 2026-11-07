// The top of the Overview: Apetit's three problems, each with its answer, the proof and the next action.
//   1 · Data is scattered and messy       → one checked dataset (issues found, fixes waiting for sign-off)
//   2 · Reports are built by hand         → the inventory rebuilt from source, traced, scored, draft checked
//   3 · Sweden 2026 must not happen again → the replay: the warning was there weeks before the profit warning
// Every number comes from GET /api/brief (deterministic, from the snapshot). Nothing is typed here.
import { useState, type MouseEvent, type ReactNode } from "react";
import { useBrief, useInventoryReport, useIssues, type Brief } from "../api/brief";
import { CheckCircle, Crumbs, Segmented, Sheet } from "../components/ui";
import { REGION_VIEW, useStore } from "../state/store";

const n0 = (v: number) => v.toLocaleString("en-GB");
const kt = (t: number) => (t >= 1e6 ? `${(t / 1e6).toFixed(1)}M` : t >= 1e4 ? `${Math.round(t / 1e3)}k` : n0(t));
const MONTH = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const dayMonth = (iso: string) => new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short" });
const CAT: Record<string, string> = {
  cat01_purchased_goods_services: "Purchased goods", cat09_downstream_transport: "Downstream transport",
  cat04_upstream_transport: "Upstream transport", cat02_capital_goods: "Capital goods",
};
const rect = (e: MouseEvent) => (e.currentTarget as HTMLElement).getBoundingClientRect();

function Pillar({ n, tone, problem, answer, children, proof, actions }: {
  n: number; tone: "data" | "report" | "risk"; problem: string; answer: string; children: ReactNode;
  proof: ReactNode[]; actions: ReactNode;
}) {
  return (
    <article className={`pb glass pb-${tone}`} aria-labelledby={`pb-${n}`}>
      <header className="pb-head">
        <span className="pb-num" aria-hidden="true">{n}</span>
        <p className="pb-problem"><span className="sr-only">Problem: </span>{problem}</p>
      </header>
      <h2 className="pb-answer" id={`pb-${n}`}>{answer}</h2>
      <div className="pb-body">{children}</div>
      <ul className="pb-proof">
        {proof.map((p, i) => <li key={i}><CheckCircle size={16} /><span>{p}</span></li>)}
      </ul>
      <div className="pb-actions">{actions}</div>
    </article>
  );
}

function SourceBars({ d }: { d: Brief["data"] }) {
  const max = Math.max(...d.by_source.map((s) => s.n), 1);
  return (
    <div className="hbars" role="img" aria-label={`Errors by source: ${d.by_source.map((s) => `${s.label} ${s.n}`).join(", ")}`}>
      {d.by_source.slice(0, 5).map((s) => (
        <div key={s.key} className="hbar">
          <span className="hbar-l">{s.label}</span>
          <span className="hbar-t"><span style={{ width: `${(100 * s.n) / max}%` }} /></span>
          <span className="hbar-n">{s.n}</span>
        </div>
      ))}
    </div>
  );
}

function ScopeBar({ r }: { r: Brief["reports"] }) {
  const parts = [
    { k: "Scope 1", v: r.scope1, c: "var(--blue)" },
    { k: "Scope 2", v: r.scope2_market, c: "var(--purple)" },
    { k: "Scope 3", v: r.scope3, c: "var(--accent)" },
  ];
  return (
    <div className="scopebar">
      <div className="scopebar-track" role="img" aria-label={parts.map((p) => `${p.k} ${n0(p.v)} t`).join(", ")}>
        {parts.map((p) => <span key={p.k} style={{ flexGrow: Math.max(p.v, r.total_market * 0.012), background: p.c }} />)}
      </div>
      <div className="scopebar-legend">
        {parts.map((p) => <span key={p.k}><i style={{ background: p.c }} />{p.k} <b>{n0(p.v)} t</b></span>)}
      </div>
    </div>
  );
}

/** Rain vs normal, month by month, Skåne 2026: the flowering month, the day the signal was complete, the warning. */
function RainReplay({ s }: { s: Brief["sweden"] }) {
  const W = 320, H = 150, top = 20, mid = 74, scale = 0.62, bw = 24;
  const x = (m: number) => 14 + (m - 1) * ((W - 28) / 9);
  const sig = new Date(s.signal_date), ev = new Date(s.event.date);
  const xd = (d: Date) => x(d.getMonth() + 1) + (bw * d.getDate()) / 31 + 4;
  return (
    <svg className="replay" viewBox={`0 0 ${W} ${H}`} role="img"
      aria-label={`Skåne rain vs normal in ${s.year}: ${s.months.map((m) => `${MONTH[m.month]} ${m.rain_anom_pct}%`).join(", ")}. Signal complete ${dayMonth(s.signal_date)}, profit warning ${dayMonth(s.event.date)}.`}>
      <rect x={x(s.flowering_month) - 3} y={top - 6} width={bw + 6} height={H - top - 14} rx={7} className="replay-flower" />
      <text x={x(s.flowering_month) + bw / 2} y={top + 2} className="replay-cap" textAnchor="middle">flowering</text>
      <line x1={8} x2={W - 8} y1={mid} y2={mid} className="replay-zero" />
      {s.months.map((m) => {
        const h = Math.min(mid - top - 4, Math.abs(m.rain_anom_pct) * scale);
        const dry = m.rain_anom_pct < 0;
        return (
          <g key={m.month}>
            <rect x={x(m.month) + 4} width={bw - 8} rx={3} y={dry ? mid : mid - h} height={Math.max(2, h)}
              className={dry ? (m.rain_anom_pct <= -30 ? "replay-dry" : "replay-dryish") : "replay-wet"} />
            <text x={x(m.month) + bw / 2} y={H - 4} className="replay-m" textAnchor="middle">{MONTH[m.month]}</text>
          </g>
        );
      })}
      <line x1={xd(sig)} x2={xd(sig)} y1={top - 4} y2={H - 16} className="replay-sig" />
      <line x1={xd(ev)} x2={xd(ev)} y1={top - 4} y2={H - 16} className="replay-ev" />
      <text x={xd(ev) + 5} y={mid + 22} className="replay-cap replay-ev-t">profit</text>
      <text x={xd(ev) + 5} y={mid + 34} className="replay-cap replay-ev-t">warning</text>
      <text x={xd(sig) - 5} y={mid + 52} className="replay-cap" textAnchor="end">signal clear</text>
      <text x={14} y={top - 8} className="replay-axis">rain vs normal (0 % = normal)</text>
    </svg>
  );
}

export function Problems() {
  const q = useBrief();
  const b = q.data;
  const openSheet = useStore((s) => s.openSheet);
  const setTab = useStore((s) => s.setTab);
  const setYear = useStore((s) => s.setYear);
  const setLens = useStore((s) => s.setLens);
  const flyTo = useStore((s) => s.flyTo);
  const report = useInventoryReport();
  const download = () => report.mutate(2025, { onSuccess: (r) => { window.location.href = r.url; } });

  if (q.error) return <p className="err" role="alert">Couldn't load the brief: {String(q.error)}</p>;
  if (!b) return <div className="problems" aria-busy="true">{[0, 1, 2].map((i) => <div key={i} className="pb glass skeleton-card" />)}</div>;
  const { data: d, reports: r, sweden: s } = b;
  const devScores = r.dev_scores.map((x) => x.score.toFixed(1)).join(" and ");

  return (
    <section className="problems" aria-label="Apetit's three problems and how this answers them">
      <Pillar n={1} tone="data" problem={`Data scattered over ${d.feeds} feeds, full of errors`} answer="One checked dataset"
        proof={[
          <>{d.accuracy ? <><b>{d.accuracy.score}/100</b> on the public 2023–24 error labels ({d.accuracy.precision_pct}% precise)</> : "Scored on the public error labels"}</>,
          <><b>{n0(d.legit_left_alone)}</b> odd-but-correct records left alone (credit notes, tonnes, peaks)</>,
        ]}
        actions={<>
          <button type="button" className="btn btn-primary" onClick={(e) => openSheet("data", rect(e))}>Review {n0(d.awaiting_signoff)} fixes</button>
          <span className="pb-note">{d.approved ? `${n0(d.approved)} signed off` : "Nothing changes until an expert signs off"}</span>
        </>}>
        <div className="pb-fig"><span className="w-fig">{n0(d.issues_found)}</span><span className="pb-unit">errors caught</span></div>
        <p className="pb-sub">in {n0(d.records_checked)} operational and farm records · each with its evidence and a proposed fix</p>
        <SourceBars d={d} />
      </Pillar>

      <Pillar n={2} tone="report" problem="Reports built by hand, slowly, and they don't add up" answer={`The ${r.year} inventory, built from source`}
        proof={[
          <>Every line traced to <b>{n0(r.records_traced)}</b> source records and <b>{r.factors_used}</b> emission factors</>,
          <><b>{devScores}/100</b> against the known 2023 and 2024 totals</>,
        ]}
        actions={<>
          <button type="button" className="btn btn-primary" onClick={download} disabled={report.isPending}>
            {report.isPending ? "Building…" : `Download ${r.year} inventory`}
          </button>
          <button type="button" className="btn btn-ghost" onClick={(e) => openSheet("report", rect(e))}>Check the draft</button>
        </>}>
        <div className="pb-fig"><span className="w-fig">{kt(r.total_market)}</span><span className="pb-unit">t CO2e, market-based</span></div>
        <ScopeBar r={r} />
        <div className="pb-flag" role="note">
          <span className="pb-flag-ic" aria-hidden="true">!</span>
          <span>The hand-built draft's total is <b>{kt(r.draft_total)}</b> t, but its own lines add up to <b>{kt(r.draft_sum_of_parts)}</b> t.</span>
        </div>
      </Pillar>

      <Pillar n={3} tone="risk" problem="Sweden 2026: the pea crop failed before anyone saw it" answer={`Warned ${Math.round(s.lead_days / 7)} weeks earlier`}
        proof={[
          <>Trained only on data to 2023, the model called {s.year} Skåne peas at <b>{n0(s.predicted_t ?? 0)} t</b>; {n0(s.actual_t ?? 0)} t came in ({s.model_error_pct}% off)</>,
          <>Same season, Finnish peas were <b>+{s.fi_change_pct}%</b>: the two-region hedge works</>,
        ]}
        actions={<>
          <button type="button" className="btn btn-primary" onClick={() => { setYear(s.year); setLens("drought"); flyTo(REGION_VIEW.SE_SKANE); setTab("map"); }}>
            Replay {s.year} on the map
          </button>
          <a className="btn btn-ghost" href="#radar">What's coming next</a>
        </>}>
        <div className="pb-fig"><span className="w-fig fig-risk">{s.lead_days}</span><span className="pb-unit">days of warning</span></div>
        <p className="pb-sub">Pea flowering in Skåne got {Math.abs(s.flowering_rain_pct ?? 0)}% less rain than normal. The signal was complete
          on {dayMonth(s.signal_date)}; the profit warning came {dayMonth(s.event.date)}.</p>
        <RainReplay s={s} />
      </Pillar>
    </section>
  );
}

/* ── Layer 2 sheets ─────────────────────────────────────────────────────────── */

function DataSheet({ b, onClose }: { b: Brief; onClose: () => void }) {
  const sheet = useStore((s) => s.sheet);
  const [status, setStatus] = useState<"proposed" | "legitimate">("proposed");
  const [source, setSource] = useState<string | null>(null);
  const q = useIssues(status, source);
  const d = b.data;
  return (
    <Sheet label="Data review" from={sheet?.from} onClose={onClose}>
      <div className="sheet-head"><div>
        <Crumbs items={[{ label: "Overview", onClick: onClose }, { label: "Data review" }]} />
        <h2 className="sheet-title">{n0(d.issues_found)} fixes waiting for sign-off</h2>
        <p className="sheet-sub">Found by rules across {d.feeds} feeds, each with its evidence. A fix only reaches a report once an expert approves it.</p>
      </div></div>
      <div className="review-bar">
        <Segmented className="plain" label="Show" value={status} onChange={(v) => { setStatus(v); setSource(null); }}
          options={[{ key: "proposed", label: `Errors (${n0(d.issues_found)})` }, { key: "legitimate", label: `Looks odd, is fine (${n0(d.legit_left_alone)})` }]} />
        <div className="chips">
          <button type="button" className="source-chip" aria-pressed={source === null} onClick={() => setSource(null)}>All sources</button>
          {d.by_source.map((x) => (
            <button key={x.key} type="button" className="source-chip" aria-pressed={source === x.key} onClick={() => setSource(x.key)}>
              {x.label} · {x.n}
            </button>
          ))}
        </div>
      </div>
      <div className="review-list" role="list">
        {q.isLoading ? <p className="muted">Loading…</p> : null}
        {q.data?.map((i) => (
          <div key={i.issue_id} className="review-row" role="listitem">
            <div className="rr-main">
              <div className="rr-top"><span className="rr-type">{i.type_label}</span><span className="rr-src">{i.source_label} · {i.year}</span></div>
              <p className="rr-why">{i.explanation}</p>
              <code className="rr-key">{i.record_key}</code>
            </div>
            {i.field ? (
              <div className="rr-fix">
                <span className="rr-field">{i.field}</span>
                <span className="rr-old">{i.old_value ?? "—"}</span>
                <span className="rr-arrow" aria-label="becomes">→</span>
                <span className="rr-new">{i.new_value ?? "—"}</span>
              </div>
            ) : <div className="rr-fix rr-keep">Kept as is</div>}
            <span className={`rr-state ${i.signed_off ? "ok" : ""}`}>{status === "legitimate" ? "No change" : i.signed_off ? "Signed off" : "Awaiting sign-off"}</span>
          </div>
        ))}
      </div>
    </Sheet>
  );
}

function ReportSheet({ b, onClose }: { b: Brief; onClose: () => void }) {
  const sheet = useStore((s) => s.sheet);
  const report = useInventoryReport();
  const r = b.reports;
  return (
    <Sheet label="Inventory check" from={sheet?.from} onClose={onClose}>
      <div className="sheet-head"><div>
        <Crumbs items={[{ label: "Overview", onClick: onClose }, { label: `${r.year} inventory` }]} />
        <h2 className="sheet-title">The draft report vs the inventory rebuilt from source</h2>
        <p className="sheet-sub">The rebuilt inventory runs the GHG Protocol rules over the cleaned records. The draft is the hand-built
          preliminary summary in the pack.</p>
      </div></div>
      <table className="plans-table cmp">
        <thead><tr><th>Line</th><th>Hand-built draft</th><th>Rebuilt from source</th><th>Draft is off by</th></tr></thead>
        <tbody>
          {r.draft_checks.map((c) => (
            <tr key={c.line}><td>{c.line}</td><td>{n0(c.draft)} t</td><td><b>{n0(c.rebuilt)} t</b></td>
              <td className={c.ratio > 1.05 || c.ratio < 0.95 ? "bad" : ""}>{c.ratio}×</td></tr>
          ))}
          <tr><td>Total (market-based)</td><td>{n0(r.draft_total)} t <span className="tag-assume">≠ its own lines: {n0(r.draft_sum_of_parts)}</span></td>
            <td><b>{n0(r.total_market)} t</b></td><td /></tr>
        </tbody>
      </table>
      <div className="cards3">
        <div className="card"><span className="h">Scope 3, biggest categories</span>
          {r.scope3_top.map((c) => <span key={c.key} className="kv"><span>{CAT[c.key] ?? c.key}</span><b>{n0(c.t)} t</b></span>)}
        </div>
        <div className="card"><span className="h">Traceability</span>
          <span className="big">{n0(r.trace_links)}</span>
          <span className="muted">links from {r.year} lines to {n0(r.records_traced)} source records and {r.factors_used} factors</span>
        </div>
        <div className="card leafy"><span className="h">Checked against known years</span>
          {r.dev_scores.map((x) => <span key={x.year} className="kv"><span>{x.year}</span><b>{x.score.toFixed(1)}/100</b></span>)}
          <span className="muted">Pack scorer: each line full marks within 0 % error, none at 5 %.</span>
        </div>
      </div>
      <button type="button" className="btn btn-primary" disabled={report.isPending}
        onClick={() => report.mutate(r.year, { onSuccess: (x) => { window.location.href = x.url; } })}>
        {report.isPending ? "Building…" : `Download the ${r.year} inventory (Excel, with sources)`}
      </button>
    </Sheet>
  );
}

export function ProblemSheets() {
  const sheet = useStore((s) => s.sheet);
  const close = useStore((s) => s.closeSheet);
  const q = useBrief();
  if (!sheet || !q.data) return null;
  if (sheet.kind === "data") return <DataSheet b={q.data} onClose={close} />;
  if (sheet.kind === "report") return <ReportSheet b={q.data} onClose={close} />;
  return null;
}
