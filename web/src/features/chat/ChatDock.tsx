import { useEffect, useRef, useState } from "react";
import { useActiveScenario, useAsk, useIntentQuery } from "../../api/hooks";
import type { ReportRef, ScenarioSpec, Table } from "../../api/types";
import { liveOrder, useSearch } from "../../state/search";
import { useStore, type ChatMsg } from "../../state/store";
import { Chat, Close, Mic, Send } from "../../components/Icons";
import { PlansTable } from "../plans/PlansTable";
import { SimCard } from "./SimCard";
import { EvidenceChips } from "../ask/EvidenceChips";
import { ReportButton } from "../ask/ReportButton";
import { ResultTable } from "../ask/ResultTable";
import { useSpeech } from "../voice/useSpeech";

const FIND_BEST = "Find the best plan for me";
const SUGGESTIONS: { text: string; kind: "search" | "what-if" | "ask" }[] = [
  { text: FIND_BEST, kind: "search" },
  { text: "What if we irrigate the driest pea fields and move to a 70/30 Finland–Sweden split?", kind: "what-if" },
  { text: "What if we plant a heat-tolerant pea from 2030?", kind: "what-if" },
  { text: "How did pea deliveries from Swedish farms in 2026 compare with 2021?", kind: "ask" },
  { text: "Where does the 2024 Scope 1 number come from?", kind: "ask" },
];

/** Minimal markdown: **bold**, *italic*, `code`, "- " bullets and "> " quotes; everything else is plain text. */
function Md({ text }: { text: string }) {
  const inline = (s: string) =>
    s.split(/(\*\*[^*]+\*\*|`[^`]+`|\*[^*]+\*)/g).map((part, i) =>
      part.startsWith("**") ? <strong key={i}>{part.slice(2, -2)}</strong>
        : part.startsWith("`") ? <code key={i}>{part.slice(1, -1)}</code>
          : part.startsWith("*") && part.length > 2 ? <em key={i}>{part.slice(1, -1)}</em> : part);
  return (
    <div className="md">
      {text.split("\n").filter((l) => l.trim() !== "").map((l, i) =>
        l.startsWith("- ") ? <div key={i} className="md-li">• {inline(l.slice(2))}</div>
          : l.startsWith(">") ? <blockquote key={i}>{inline(l.replace(/^>\s?/, ""))}</blockquote>
            : <p key={i}>{inline(l)}</p>)}
    </div>
  );
}

function AskAnswer({ m }: { m: ChatMsg }) {
  const a = useAsk(m.text, m.history);
  if (a.isLoading) return <div className="bubble bot typing"><span /><span /><span /></div>;
  if (a.error) return <div className="bubble bot err">{String(a.error)}</div>;
  if (!a.data) return null;
  const d = a.data;
  return (
    <div className="bubble bot">
      {d.status === "not_in_data" ? <div className="tag">Not in the data</div> : null}
      <Md text={d.answer_md} />
      <ResultTable table={d.table as Table | null} />
      <EvidenceChips evidence={d.evidence} />
      <ReportButton report={d.report as ReportRef | null} />
      {d.pending_approval ? <div className="small muted">Uses draft results pending expert approval.</div> : null}
    </div>
  );
}

function SimAnswer({ spec, heard, problems }: { spec: ScenarioSpec; heard: string[]; problems: string[] }) {
  return (
    <>
      {heard.length || problems.length ? (
        <div className="bubble bot">
          <p>I heard a what-if:</p>
          <div className="chips">{heard.map((h) => <span key={h} className="chip">{h}</span>)}</div>
          {problems.length ? <ul className="problems">{problems.map((p) => <li key={p}>{p}</li>)}</ul> : null}
        </div>
      ) : null}
      <SimCard spec={spec} heard={heard} />
    </>
  );
}

/** "Find the best plan": the plan finder, followed live in the chat. */
function SearchAnswer() {
  const s = useSearch();
  const sim = useActiveScenario();
  const climate = sim.data?.spec.climate ?? "ssp245", horizon = sim.data?.spec.horizon_end ?? 2040;
  useEffect(() => { if (s.status === "idle" || s.status === "error") void s.start(climate, horizon); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const best = s.best ? s.candidates[s.best] : null;
  const lead = liveOrder(s)[0];
  return (
    <div className="bubble bot search-answer">
      {s.status === "running" ? (
        <>
          <div className="sim-running"><span className="spinner" />Simulating plan {Math.max(1, s.done)} of {s.total || "…"} over {s.years || 15} years of weather</div>
          <div className="bar"><span style={{ width: `${s.total ? (100 * s.done) / s.total : 0}%` }} /></div>
          {lead?.saves ? <p className="small">Best so far: {lead.label} (saves {lead.saves} a year)</p> : null}
        </>
      ) : s.status === "error" ? <span className="sev-critical">{s.error}</span> : (
        <>
          <p>I simulated <strong>{Object.keys(s.candidates).length} plans</strong>: every change the model can run, then
            combinations of the ones that helped, and re-checked the best in the two other climate futures.</p>
          {best ? <p className="best-line">Best: <strong>{best.label}</strong>, saving <strong>{best.saves}</strong> a year;
            years with €250k+ at risk go from {best.plan_costly_years} to {best.costly_years}.</p>
            : <p>No plan beat today's plan on this weather path.</p>}
        </>
      )}
      <PlansTable limit={6} />
    </div>
  );
}
function Message({ m }: { m: ChatMsg }) {
  if (m.kind === "search") return <><div className="bubble me">{m.text}</div><SearchAnswer /></>;
  return <TextMessage m={m} />;
}

function TextMessage({ m }: { m: ChatMsg }) {
  const sim = useActiveScenario();
  const intent = useIntentQuery(m.text, sim.data?.spec ?? null);
  const r = intent.data;
  return (
    <>
      <div className="bubble me">{m.text}</div>
      {intent.isLoading ? <div className="bubble bot typing"><span /><span /><span /></div> : null}
      {intent.error ? <div className="bubble bot err">{String(intent.error)}</div> : null}
      {r && (r.door === "ask" || !r.spec) ? <AskAnswer m={m} /> : null}
      {r && r.door === "simulate" && r.spec ? <SimAnswer spec={r.spec as ScenarioSpec} heard={r.heard ?? []} problems={r.problems ?? []} /> : null}
    </>
  );
}

/** The assistant, floating over the map (which stays visible behind it): ask about the past (retrieval), say a
 *  what-if (simulated in full right here), or have the plan finder test every plan. Esc or the backdrop closes it. */
export function ChatDock() {
  const open = useStore((s) => s.assistantOpen);
  const setOpen = useStore((s) => s.setAssistantOpen);
  const chat = useStore((s) => s.chat);
  const sendChat = useStore((s) => s.sendChat);
  const [text, setText] = useState("");
  const speech = useSpeech((t) => { setText(t); if (t.trim()) sendChat(t.trim()); });
  const end = useRef<HTMLDivElement>(null);
  // Braces matter: newer Chromium returns a Promise from scrollIntoView, and React treats a returned value as cleanup.
  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth" }); }, [chat.length]);
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, setOpen]);
  if (!open) return null;
  const send = () => {
    const t = text.trim();
    if (!t) return;
    sendChat(t, /best plan|optimi[sz]e|what should we do/i.test(t) ? "search" : undefined);
    setText("");
  };
  return (
    <div className="assistant-backdrop" onMouseDown={(e) => { if (e.target === e.currentTarget) setOpen(false); }}>
      <section className="assistant glass" role="dialog" aria-modal="true" aria-label="Assistant">
        <header className="assistant-head">
          <div className="assistant-title"><Chat size={20} /> Assistant</div>
          <span className="muted small">Answers come from the data, with sources. What-ifs run the prediction model.</span>
          <button className="icon-btn" onClick={() => setOpen(false)} aria-label="Close"><Close size={18} /></button>
        </header>
        <div className="chat-body">
          {chat.length === 0 ? (
            <div className="chat-empty">
              {SUGGESTIONS.map((x) => (
                <button key={x.text} className={`suggestion ${x.kind}`} onClick={() => sendChat(x.text, x.kind === "search" ? "search" : undefined)}>
                  <span className="sugg-kind">{x.kind === "search" ? "Plan finder" : x.kind === "what-if" ? "Simulate" : "Ask the data"}</span>
                  {x.text}
                </button>
              ))}
            </div>
          ) : chat.map((m) => <Message key={m.id} m={m} />)}
          <div ref={end} />
        </div>
        <form className="chat-input" onSubmit={(e) => { e.preventDefault(); send(); }}>
          <input autoFocus value={text} onChange={(e) => setText(e.target.value)} placeholder="Ask, or say “What if we irrigate the driest pea fields?”" aria-label="Message" />
          {speech.supported ? (
            <button type="button" className={`icon-btn ${speech.listening ? "rec" : ""}`} onClick={() => (speech.listening ? speech.stop() : speech.start())} aria-label="Speak">
              <Mic size={18} />
            </button>
          ) : null}
          <button type="submit" className="icon-btn send" aria-label="Send"><Send size={18} /></button>
        </form>
      </section>
    </div>
  );
}
