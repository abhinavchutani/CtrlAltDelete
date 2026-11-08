// The top of the Overview: Apetit's three problems, each with its answer, the proof and the next action.
//   1 · Data is scattered and messy       → one checked dataset (issues found, fixes waiting for sign-off)
//   2 · Reports are built by hand         → the inventory rebuilt from source, traced, scored, draft checked
//   3 · Sweden 2026 must not happen again → the replay: the warning was there weeks before the profit warning
// Every number comes from GET /api/brief (deterministic, from the snapshot). Nothing is typed here.
import { useState, type MouseEvent } from "react";
import { useBrief, useInventoryReport, useIssues, type Brief } from "../api/brief";
import { Crumbs, Segmented, Sheet } from "../components/ui";
import { CheckIcon } from "../components/ui";
import { useStore } from "../state/store";

const n0 = (v: number) => v.toLocaleString("en-GB");
const kt = (t: number) => (t >= 1e6 ? `${(t / 1e6).toFixed(1)}M` : t >= 1e4 ? `${Math.round(t / 1e3)}k` : n0(t));
const CAT: Record<string, string> = {
  cat01_purchased_goods_services: "Purchased goods", cat09_downstream_transport: "Downstream transport",
  cat04_upstream_transport: "Upstream transport", cat02_capital_goods: "Capital goods",
};
const rect = (e: MouseEvent) => (e.currentTarget as HTMLElement).getBoundingClientRect();

type Line = { tone: "data" | "report" | "risk"; who: string; fig: string; text: string; cta: string; go: (e: MouseEvent) => void };

/** The catch-up: three lines, one number each, one place to go. Details live in the sheets. */
export function Problems() {
  const q = useBrief();
  const b = q.data;
  const openSheet = useStore((s) => s.openSheet);
  const prefill = useStore((s) => s.prefill);

  if (q.error) return <p className="err" role="alert">Couldn't load the catch-up: {String(q.error)}</p>;
  if (!b) return <div className="catchup glass skeleton-card" aria-busy="true" />;
  const { data: d, reports: r, sweden: s } = b;
  const lines: Line[] = [
    { tone: "data", who: "Data", fig: n0(d.issues_found), cta: "Review",
      text: `errors found in ${n0(d.records_checked)} records from ${d.feeds} feeds. Fixes wait for an expert's OK.`,
      go: (e) => openSheet("data", rect(e)) },
    { tone: "report", who: "Reporting", fig: `${kt(r.total_market)} t`, cta: "Open report",
      text: `CO2e in the ${r.year} inventory, built from source and traced line by line.`,
      go: (e) => openSheet("report", rect(e)) },
    { tone: "risk", who: "Supply", fig: `${Math.round(s.lead_days / 7)} weeks`, cta: "What would help",
      text: `earlier warning of the ${s.year} Skåne pea shortfall than the profit warning.`,
      go: () => prefill("ask", "What helps against drought at flowering in pea?") },
  ];
  return (
    <section className="catchup glass" aria-labelledby="catchup-h">
      <h2 className="catchup-h eyebrow" id="catchup-h">Catch-up</h2>
      <ul className="catchup-list">
        {lines.map((l) => (
          <li key={l.tone} className={`cu cu-${l.tone}`}>
            <span className="cu-who">{l.who}</span>
            <p className="cu-line"><b className="cu-fig">{l.fig}</b> {l.text}</p>
            <button type="button" className="link cu-go" onClick={l.go}>{l.cta} ›</button>
          </li>
        ))}
      </ul>
    </section>
  );
}

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
        {q.isLoading ? [0, 1, 2, 3].map((k) => <div key={k} className="review-row skeleton" style={{ height: 76 }} />) : null}
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
      <button type="button" className={`btn btn-primary ${report.isSuccess ? "done" : ""}`} disabled={report.isPending} aria-live="polite"
        onClick={() => report.mutate(r.year, { onSuccess: (x) => { window.location.href = x.url; } })}>
        {report.isPending ? <><span className="spin" aria-hidden="true" />Building the workbook…</>
          : report.isSuccess ? <><CheckIcon size={18} />Downloaded · download again</>
            : `Download the ${r.year} inventory (Excel, with sources)`}
      </button>
      {report.isError ? <p className="err" role="alert">Couldn't build the report: {String(report.error)}</p> : null}
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
