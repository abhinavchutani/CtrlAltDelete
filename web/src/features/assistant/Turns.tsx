// One assistant turn per mode. Ask: retrieval with its receipt. Simulate: the yield model on a described plan.
// Teach: a note from a person, filed by deterministic rules, always unverified until a second person confirms.
import { useEffect, useState } from "react";
import { useConfirmNote, useFileNote, useGraph, useIntentQuery, useInterview, useRadarAsk, useRefileNote, useSimulation, useTopics } from "../../api/hooks";
import type { Filed, ScenarioSpec, Table } from "../../api/types";
import { SearchIcon, SourceChip, SproutIcon, TrendIcon, Typing } from "../../components/ui";
import { leverLabel } from "../../domain";
import { SolutionCards } from "./SolutionCards";
import { useStore, type Mode, type Turn } from "../../state/store";

export const MODE_ICON: Record<Mode, JSX.Element> = { ask: <SearchIcon />, simulate: <TrendIcon />, teach: <SproutIcon /> };
const FOLLOW_ICON = MODE_ICON;
const NAME_KEY = "fieldradar.teach.name";
const loadName = () => { try { return localStorage.getItem(NAME_KEY) ?? ""; } catch { return ""; } };
const saveName = (n: string) => { try { localStorage.setItem(NAME_KEY, n); } catch { /* private window */ } };

/** Plain text from a little markdown (bold/italic/code markers dropped). */
const plain = (s: string) => s.replace(/\*\*([^*]+)\*\*/g, "$1").replace(/\*([^*]+)\*/g, "$1").replace(/`([^`]+)`/g, "$1");

/** Signed changes and percentages in the headline, in harvest ink (the figure the answer is about). */
const figures = (s: string) =>
  s.split(/([+−-]\d[\d,.]*\s?%)/g).map((part, i) => (i % 2 ? <em key={i}>{part}</em> : part));

function Followups({ items }: { items: { mode: Mode; label: string; prompt: string }[] }) {
  const prefill = useStore((s) => s.prefill);
  return (
    <div className="followups">
      {items.map((f) => (
        <button key={f.label} type="button" className={`followup ${f.mode}`} onClick={() => prefill(f.mode, f.prompt)}>
          {FOLLOW_ICON[f.mode]} {f.label}
        </button>
      ))}
    </div>
  );
}

function TableView({ t }: { t: Table }) {
  return (
    <div style={{ overflowX: "auto" }}>
      <table>
        <thead><tr>{t.columns.map((c) => <th key={c} scope="col">{c}</th>)}</tr></thead>
        <tbody>{t.rows.map((r, i) => <tr key={i}>{r.map((v, j) => <td key={j}>{v === null ? "—" : typeof v === "number" ? v.toLocaleString("en-GB") : v}</td>)}</tr>)}</tbody>
      </table>
    </div>
  );
}

function AskTurn({ t, latest }: { t: Turn; latest: boolean }) {
  const a = useRadarAsk(t.text, t.history);
  const light = useStore((s) => s.light);
  useEffect(() => { if (latest && a.data) light(a.data.used_node_ids); }, [latest, a.data, light]);
  if (a.isLoading) return <Typing />;
  if (a.error) return <div className="answer glass err" role="alert">{String(a.error)}</div>;
  const d = a.data!;
  if (d.solutions?.length) {
    const head = d.answer_md.split("\n")[0];
    return (
      <article className="answer glass">
        <div className="answer-eyebrow ask eyebrow">{MODE_ICON.ask} Ask · from crop research and farm guides</div>
        <h2>{plain(head)}</h2>
        <p className="reason">Matched to the problem by fixed rules; every source quote is verbatim. Not yet reviewed by a person.</p>
        <div className="chips">{d.sources.map((s) => <SourceChip key={s.node_id} s={s} />)}</div>
        <SolutionCards items={d.solutions} />
      </article>
    );
  }
  const paras = d.answer_md.split(/\n\s*\n/).map((p) => plain(p.trim())).filter(Boolean);
  const [head, ...rest] = paras;
  const sweden = /swed|skåne|skane|foodhills/i.test(t.text);
  return (
    <article className="answer glass">
      <div className="answer-eyebrow ask eyebrow">{MODE_ICON.ask} Ask · {d.status === "answered" ? "from the data" : "not in the data"}</div>
      <h2 style={head && head.length > 110 ? { fontSize: 18, lineHeight: "26px" } : undefined}>{figures(head ?? "")}</h2>
      {rest.length ? <p className="reason">{rest.join(" ")}</p> : null}
      {d.sources.length ? <div className="chips">{d.sources.map((s) => <SourceChip key={s.node_id} s={s} />)}</div> : null}
      {d.pending_approval ? <p className="reason">Uses draft results pending expert approval.</p> : null}
      {d.table ? <details><summary>Show the numbers</summary><TableView t={d.table as Table} /></details> : null}
      {d.status === "answered" ? (
        <Followups items={sweden
          ? [{ mode: "simulate", label: "Simulate a 70/30 Finland–Sweden split", prompt: "What if we move pea sourcing to a 70/30 Finland–Sweden split?" },
            { mode: "teach", label: "Ask Skåne growers why", prompt: "Skåne growers say: " }]
          : [{ mode: "simulate", label: "Simulate irrigating the driest pea fields", prompt: "What if we irrigate the driest pea fields?" },
            { mode: "teach", label: "Tell it what explains this", prompt: "What explains this: " }]} />
      ) : null}
    </article>
  );
}

function SimTurn({ t, latest }: { t: Turn; latest: boolean }) {
  const climate = useStore((s) => s.climate);
  const light = useStore((s) => s.light);
  const base: ScenarioSpec = { climate, horizon_end: 2040, levers: [], label: null };
  const intent = useIntentQuery(t.text, base);
  const spec = intent.data?.door === "simulate" && intent.data.spec ? (intent.data.spec as ScenarioSpec) : null;
  const sim = useSimulation(spec ? { ...spec, horizon_end: 2040 } : null);
  useEffect(() => {
    if (latest && sim.data) light(["crop:pea", "model:yield", "data:raw_weather_daily", "data:raw_contract_prices_and_replacement_premiums"]);
  }, [latest, sim.data, light]);
  if (intent.isLoading || sim.isLoading) return <Typing />;
  const err = intent.error ?? sim.error;
  if (err) return <div className="answer glass err" role="alert">{String(err)}</div>;
  if (!spec) {
    return (
      <article className="answer glass">
        <div className="answer-eyebrow simulate eyebrow">{MODE_ICON.simulate} Simulate</div>
        <h2>I couldn't find a plan to run in that.</h2>
        <p className="reason">Try a change the model can run: irrigate pea or potato fields, sow earlier, move the Finland–Sweden pea split, or a heat-tolerant pea from a year.</p>
        {intent.data?.problems?.length ? <p className="reason">{intent.data.problems.join(" ")}</p> : null}
      </article>
    );
  }
  const d = sim.data!;
  const m = d.meters;
  const levers = (spec.levers ?? []).map(leverLabel);
  const vs = { better: "less than today's plan", same: "about the same as today's plan", worse: "more than today's plan" }[m.vs_current_plan];
  const pea = d.regions.filter((r) => r.crop === "pea");
  return (
    <article className="answer glass">
      <div className="answer-eyebrow simulate eyebrow">{MODE_ICON.simulate} Simulate · yield model, {d.years.length} seasons</div>
      <h2><em>{m.eur_at_risk_per_year}</em> a year at risk, {vs}.</h2>
      <p className="reason">Plan: {levers.join(" + ") || "today's plan"}. Confidence {m.confidence}: {m.confidence_why.join("; ")}.</p>
      {intent.data?.problems?.length ? <p className="reason">Note: {intent.data.problems.join(" ")}</p> : null}
      <div className="chips">
        <SourceChip s={{ kind: "model", label: "Yield model", detail: `${d.years[0]}–${d.years[d.years.length - 1]}` }} />
        <SourceChip s={{ kind: "data", label: "Weather", detail: spec.climate ?? "ssp245" }} />
        <SourceChip s={{ kind: "data", label: "Contract prices" }} />
      </div>
      <details><summary>Show the numbers</summary>
        <TableView t={{ columns: ["Year", "Region", "Pea vs normal", "€ at risk"],
          rows: pea.map((r) => [r.year, r.region === "FI_SW" ? "SW Finland" : "Skåne", `${r.change_vs_baseline_pct > 0 ? "+" : ""}${r.change_vs_baseline_pct} %`, r.eur_at_risk]) }} />
      </details>
      <Followups items={[{ mode: "ask", label: "Which farms are hit hardest today?", prompt: "Which pea farms had the lowest yields in 2025?" },
        { mode: "teach", label: "Ask the field team if it's realistic", prompt: "Field team view on this plan: " }]} />
    </article>
  );
}

function FiledCard({ f: initial }: { f: Filed }) {
  const [f, setF] = useState(initial);
  const [step, setStep] = useState<"ask" | "done" | "edit" | "confirm">("ask");
  const [reviewer, setReviewer] = useState("");
  const topics = useTopics();
  const refile = useRefileNote();
  const confirm = useConfirmNote();
  const [verified, setVerified] = useState(f.verified);
  return (
    <article className="answer glass">
      <h2>Got it, and I filed it myself.</h2>
      <ol className="steps">
        <li><span className="n">1</span><div><div className="t">Placed under {f.path.join(" › ")}</div>
          <div className="s">{f.siblings ? `Next to ${f.siblings} older note${f.siblings === 1 ? "" : "s"} on ${f.topic.toLowerCase()}` : `The first note on ${f.topic.toLowerCase()}`}</div></div></li>
        <li><span className="n">2</span><div><div className="t">Linked to {f.linked_labels.join(" and ")}</div>
          <div className="s">So the yield model can test it against past seasons</div></div></li>
        <li><span className="n">3</span><div><div className="t">{verified ? "Confirmed by a second person" : "Marked unverified"}</div>
          <div className="s">{verified ? "It now shows solid in the graph." : "Becomes solid when a second person or a harvest record agrees"}</div></div></li>
      </ol>
      {step === "ask" ? (
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
          <button type="button" className="btn btn-tacit" onClick={() => setStep("done")}>Looks right</button>
          <button type="button" className="btn btn-ghost" onClick={() => setStep("edit")}>Edit where it went</button>
        </div>
      ) : step === "edit" ? (
        <form className="teach-form" onSubmit={(e) => { e.preventDefault(); }}>
          <label>Topic
            <select value={f.topic} onChange={(e) => refile.mutate({ id: f.note_id, topic: e.target.value }, { onSuccess: (x) => { setF(x); setStep("done"); } })}>
              {(topics.data ?? [f.topic]).map((t) => <option key={t}>{t}</option>)}
            </select>
          </label>
          {refile.error ? <p className="err">{String(refile.error)}</p> : null}
        </form>
      ) : step === "confirm" ? (
        <form className="teach-form" onSubmit={(e) => {
          e.preventDefault();
          confirm.mutate({ id: f.note_id, reviewer }, { onSuccess: () => { setVerified(true); setStep("done"); } });
        }}>
          <label>Your name (not the person who said it)<input value={reviewer} onChange={(e) => setReviewer(e.target.value)} required /></label>
          {confirm.error ? <p className="err" role="alert">{String(confirm.error).replace(/^Error: \d+: /, "")}</p> : null}
          <div><button type="submit" className="btn btn-tacit">Confirm it</button></div>
        </form>
      ) : !verified ? (
        <p className="reason">Filed as {f.note_id}. <button type="button" className="link tacit" onClick={() => setStep("confirm")}>I can confirm it (second person)</button></p>
      ) : null}
    </article>
  );
}

function NoteForm({ onFile, busy, error, label, cta }: { onFile: (name: string, role: string) => void; busy: boolean; error: unknown; label: string; cta: string }) {
  const [name, setName] = useState(loadName());
  const [role, setRole] = useState("Field officer");
  return (
    <form className="teach-form" onSubmit={(e) => { e.preventDefault(); saveName(name); onFile(name, role); }}>
      <p className="reason">{label}</p>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
        <label>Who is telling it?<input value={name} onChange={(e) => setName(e.target.value)} required placeholder="Your name" /></label>
        <label>Role<input value={role} onChange={(e) => setRole(e.target.value)} /></label>
      </div>
      {error ? <p className="err" role="alert">{String(error)}</p> : null}
      <div><button type="submit" className="btn btn-tacit" disabled={busy}>{busy ? "Filing…" : cta}</button></div>
    </form>
  );
}

function TeachTurn({ t, latest }: { t: Turn; latest: boolean }) {
  const file = useFileNote();
  const light = useStore((s) => s.light);
  const markNew = useStore((s) => s.markNew);
  const setMode = useStore((s) => s.setMode);
  const graph = useGraph();
  const gapId = t.context?.gap ?? null;
  const gap = graph.data?.nodes.find((n) => n.id === gapId);
  const interview = useInterview(gapId);
  const [answer, setAnswer] = useState("");
  const [sent, setSent] = useState<string | null>(null);
  useEffect(() => { setMode("teach"); }, [setMode]);
  useEffect(() => {
    if (latest && file.data) { markNew(`tacit:${file.data.note_id}`); light(file.data.linked_node_ids); }
  }, [latest, file.data, light, markNew]);
  const doFile = (text: string, name: string, role: string) =>
    file.mutate({ text, contributed_by: name, role, farm_id: null, gap_id: gapId });

  if (gapId) {
    return (
      <>
        <article className="answer glass">
          <div className="answer-eyebrow teach eyebrow">{MODE_ICON.teach} Teach · filling a gap</div>
          <p>Nobody has told me about <strong>{gap?.question ?? gap?.label.replace(/\?$/, "") ?? "this"}</strong>.
            {interview.data ? ` Here's a ${interview.data.questions.length}-question interview for the ${interview.data.recipient.split(",")[0].toLowerCase()}. Nothing is sent: share it, or answer here.` : ""}</p>
          {interview.data ? (
            <>
              <ol className="reason" style={{ margin: 0, paddingLeft: 20 }}>{interview.data.questions.map((q) => <li key={q}>{q}</li>)}</ol>
              <details><summary>Message to send</summary><p className="reason" style={{ marginTop: 8 }}>{interview.data.draft_message}</p></details>
            </>
          ) : null}
          {!sent ? (
            <form className="teach-form" onSubmit={(e) => { e.preventDefault(); if (answer.trim()) setSent(answer.trim()); }}>
              <label>Answer (as {interview.data?.recipient.split(",")[0] ?? "the owner"}, via the interview link)
                <textarea rows={3} value={answer} onChange={(e) => setAnswer(e.target.value)} required /></label>
              <div><button type="submit" className="btn btn-ghost">Add the answer</button></div>
            </form>
          ) : null}
        </article>
        {sent ? (
          <div className="officer">
            <div className="who">{interview.data?.recipient.split(",")[0] ?? "Owner"} · via interview link</div>
            <p>{sent}</p>
          </div>
        ) : null}
        {sent && !file.data ? <article className="answer glass"><NoteForm busy={file.isPending} error={file.error}
          label="Who gave this answer? A note always carries the person's name." cta="File it" onFile={(n, r) => doFile(sent, n, r)} /></article> : null}
        {file.data ? <FiledCard f={file.data} /> : null}
      </>
    );
  }
  return (
    <>
      <div className="officer"><div className="who">You · Teach</div><p>{t.text}</p></div>
      {file.data ? <FiledCard f={file.data} /> : (
        <article className="answer glass">
          <div className="answer-eyebrow teach eyebrow">{MODE_ICON.teach} Teach</div>
          <NoteForm busy={file.isPending} error={file.error} cta="File it"
            label="I'll file this under the crop, place and topic it's about, and link it to the data it touches. It stays unverified until a second person confirms it."
            onFile={(n, r) => doFile(t.text, n, r)} />
        </article>
      )}
    </>
  );
}

export function TurnView({ t, latest }: { t: Turn; latest: boolean }) {
  return (
    <>
      {t.mode !== "teach" ? <div className="bubble-me">{t.text}</div> : null}
      {t.mode === "ask" ? <AskTurn t={t} latest={latest} /> : t.mode === "simulate" ? <SimTurn t={t} latest={latest} /> : <TeachTurn t={t} latest={latest} />}
    </>
  );
}
