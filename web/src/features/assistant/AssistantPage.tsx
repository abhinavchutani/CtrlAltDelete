// The Assistant tab: the conversation, and the adaptive database beside it when opened (a newly filed note opens it). Three modes: Ask, Simulate, Teach.
import { useEffect, useRef } from "react";
import { useGraph } from "../../api/hooks";
import { GraphIcon, Mic } from "../../components/Icons";
import { ArrowRight } from "../../components/ui";
import { useStore, type Mode } from "../../state/store";
import { useSpeech } from "../voice/useSpeech";
import { KnowledgeGraph } from "./KnowledgeGraph";
import { MODE_ICON, TurnView } from "./Turns";

const MODES: { key: Mode; title: string; promise: string; starters: string[] }[] = [
  { key: "ask", title: "Ask", promise: "Answers from your data, with the receipt.",
    starters: ["What helps against drought at flowering in pea?", "How did Swedish pea deliveries in 2026 compare with 2021?"] },
  { key: "simulate", title: "Simulate", promise: "Runs the yield model on a plan you describe.",
    starters: ["What if we irrigate the driest pea fields?", "What if we plant a heat-tolerant pea from 2030?"] },
  { key: "teach", title: "Teach", promise: "Tell it what you know, or let it interview the field team.",
    starters: ["F0112's lower field waterlogs most Aprils, so they sow peas two weeks later.", "Interview the team about the gaps"] },
];
const PLACEHOLDER: Record<Mode, string> = {
  ask: "Ask, simulate, or teach it something…", simulate: "Describe a plan: “What if we…”", teach: "Tell it something your team knows…",
};
const LABEL: Record<Mode, string> = { ask: "Ask", simulate: "Simulate", teach: "Teach" };

function Composer() {
  const mode = useStore((s) => s.mode);
  const setMode = useStore((s) => s.setMode);
  const draft = useStore((s) => s.draft);
  const setDraft = useStore((s) => s.setDraft);
  const send = useStore((s) => s.send);
  const input = useRef<HTMLInputElement>(null);
  const speech = useSpeech((t) => setDraft(t));
  useEffect(() => { input.current?.focus(); }, [draft === "", mode]); // eslint-disable-line react-hooks/exhaustive-deps
  const submit = () => { const t = draft.trim(); if (t) send(t, mode); };
  return (
    <div className="composer glass glass-strong">
      <div className="mode-chips" role="group" aria-label="Mode">
        {MODES.map((m) => (
          <button key={m.key} type="button" className={`mode-chip ${m.key}`} aria-pressed={mode === m.key} onClick={() => setMode(m.key)}>
            {MODE_ICON[m.key]} {LABEL[m.key]}
          </button>
        ))}
      </div>
      <form onSubmit={(e) => { e.preventDefault(); submit(); }}>
        <input ref={input} value={draft} onChange={(e) => setDraft(e.target.value)} placeholder={PLACEHOLDER[mode]} aria-label="Message" />
        {speech.supported ? (
          <button type="button" className={`icon-btn mic ${speech.listening ? "rec" : ""}`} aria-label={speech.listening ? "Stop listening" : "Speak"}
            aria-pressed={speech.listening} onClick={() => (speech.listening ? speech.stop() : speech.start())}><Mic size={18} /></button>
        ) : null}
        <button type="submit" className="send" aria-label="Send"><ArrowRight size={20} /></button>
      </form>
    </div>
  );
}

function Empty() {
  const send = useStore((s) => s.send);
  const prefill = useStore((s) => s.prefill);
  const g = useGraph();
  const gaps = (g.data?.nodes ?? []).filter((n) => n.kind === "gap");
  const first = gaps[0];
  // a Teach example goes into the composer to edit, never straight into the knowledge log
  const start = (m: Mode, s: string) =>
    m !== "teach" ? send(s, m) : s.startsWith("Interview") ? (first ? send(`Fill the gap: ${first.label}`, "teach", { gap: first.id }) : undefined) : prefill("teach", s);
  return (
    <div>
      <h1>What do you want to decide?</h1>
      <p className="asst-lede">Three ways to use it. Everything it says links back to its adaptive database.</p>
      <div className="modes">
        {MODES.map((m) => (
          <section key={m.key} className={`mode-card ${m.key} ${m.key !== "teach" ? "glass" : ""}`} aria-label={m.title}>
            <h2><span className="mode-ic">{MODE_ICON[m.key]}</span>{m.title}</h2>
            <p>{m.promise}</p>
            {m.starters.map((s) => (
              <button key={s} type="button" className="starter" onClick={() => start(m.key, s)}>
                {s.startsWith("Interview") ? `Interview the team about ${gaps.length || "the"} gap${gaps.length === 1 ? "" : "s"}` : m.key === "teach" ? `Tell it: “${s}”` : s}
              </button>
            ))}
          </section>
        ))}
      </div>
      {first ? (
        <div className="gap-banner glass">
          <span className="gap-q" aria-hidden="true">?</span>
          <span><strong>{gaps.length} thing{gaps.length === 1 ? "" : "s"} nobody has told it yet</strong>, like {first.question ?? first.label.replace(/\?$/, "")}.
            <span className="muted"> The people who own that data know these.</span></span>
          <button type="button" className="link tacit cu-go" style={{ marginLeft: "auto", flex: "none" }}
            onClick={() => send(`Fill the gap: ${first.label}`, "teach", { gap: first.id })}>Ask them ›</button>
        </div>
      ) : null}
    </div>
  );
}

/** Shows the adaptive database beside the chat. A dot says the latest answer lit nodes you haven't looked at yet. */
function GraphToggle() {
  const g = useGraph();
  const setOpen = useStore((s) => s.setGraphOpen);
  const unseen = useStore((s) => s.litUnseen);
  const lit = useStore((s) => s.litNodes.filter((n) => n !== "crop:pea").length);
  const n = g.data?.nodes.length;
  return (
    <button type="button" className="kg-toggle glass glass-strong" data-tour="graph" aria-expanded={false} onClick={() => setOpen(true)}>
      <GraphIcon size={18} />
      <span>Adaptive database{n ? <span className="muted"> · {n}</span> : null}</span>
      {unseen && lit ? <span className="kg-toggle-badge">{lit} used</span> : null}
    </button>
  );
}

export function AssistantPage() {
  const turns = useStore((s) => s.turns);
  const open = useStore((s) => s.graphOpen);
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [turns.length]);
  return (
    <main className={`asst ${open ? "graph-open" : ""}`} aria-label="Assistant">
      <div className="asst-main">
        <div className="convo" aria-live="polite">
          {turns.length === 0 ? <Empty /> : turns.map((t, i) => <TurnView key={t.id} t={t} latest={i === turns.length - 1} />)}
          <div ref={end} />
        </div>
        <Composer />
      </div>
      {open ? <KnowledgeGraph /> : <GraphToggle />}
    </main>
  );
}
