import { useEffect, useRef, useState } from "react";
import { useActiveScenario, useAsk, useIntentQuery } from "../../api/hooks";
import type { ReportRef, ScenarioSpec, Table } from "../../api/types";
import { useStore, type ChatMsg } from "../../state/store";
import { Chat, Dock, Max, Min, Mic, Send } from "../../components/Icons";
import { EvidenceChips } from "../ask/EvidenceChips";
import { ReportButton } from "../ask/ReportButton";
import { ResultTable } from "../ask/ResultTable";
import { useSpeech } from "../voice/useSpeech";

const SUGGESTIONS = [
  "How did pea deliveries from Swedish farms in 2026 compare with 2021?",
  "What if we irrigate the driest pea fields and move to a 70/30 Finland–Sweden split?",
  "Where does the 2024 Scope 1 number come from?",
  "What data is missing for 2025?",
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
  const runSpec = useStore((s) => s.runSpec);
  const [ran, setRan] = useState(false);
  return (
    <div className="bubble bot">
      <p>I heard a what-if. I'll run it on the map once you confirm:</p>
      <div className="chips">{heard.map((h) => <span key={h} className="chip">{h}</span>)}</div>
      {problems.length ? <ul className="problems">{problems.map((p) => <li key={p}>{p}</li>)}</ul> : null}
      <button className="btn-primary" disabled={ran} onClick={() => { runSpec(spec); setRan(true); }}>
        {ran ? "Running on the map" : "Run on the map"}
      </button>
    </div>
  );
}

function Message({ m }: { m: ChatMsg }) {
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

/** The assistant beside the map: ask about the past (retrieval) or say a what-if (prediction). Collapse, dock or maximise. */
export function ChatDock() {
  const { chat, chatMode, setChatMode, sendChat } = useStore();
  const [text, setText] = useState("");
  const speech = useSpeech((t) => { setText(t); if (t.trim()) sendChat(t.trim()); });
  const end = useRef<HTMLDivElement>(null);
  // Braces matter: newer Chromium returns a Promise from scrollIntoView, and React treats a returned value as cleanup.
  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth" }); }, [chat.length]);
  if (chatMode === "collapsed") {
    return (
      <button className="glass chat-pill" onClick={() => setChatMode("docked")}>
        <Chat /> Ask Field Radar
      </button>
    );
  }
  const send = () => { if (text.trim()) { sendChat(text.trim()); setText(""); } };
  return (
    <section className={`glass chat ${chatMode}`} aria-label="Assistant">
      <header className="chat-head">
        <div className="chat-title"><Chat size={18} /> Assistant <span className="muted small">answers from the data, with sources</span></div>
        <div className="chat-actions">
          {chatMode === "max"
            ? <button className="icon-btn" onClick={() => setChatMode("docked")} aria-label="Dock beside the map"><Dock size={18} /></button>
            : <button className="icon-btn" onClick={() => setChatMode("max")} aria-label="Maximise"><Max size={18} /></button>}
          <button className="icon-btn" onClick={() => setChatMode("collapsed")} aria-label="Minimise"><Min size={18} /></button>
        </div>
      </header>
      <div className="chat-body">
        {chat.length === 0 ? (
          <div className="chat-empty">
            <p className="muted">Ask about deliveries, energy, farms and rules, or try a what-if. Every number comes from the data.</p>
            {SUGGESTIONS.map((s) => <button key={s} className="suggestion" onClick={() => sendChat(s)}>{s}</button>)}
          </div>
        ) : chat.map((m) => <Message key={m.id} m={m} />)}
        <div ref={end} />
      </div>
      <form className="chat-input" onSubmit={(e) => { e.preventDefault(); send(); }}>
        <input value={text} onChange={(e) => setText(e.target.value)} placeholder="Ask, or say “What if we irrigate the driest pea fields?”" aria-label="Message" />
        {speech.supported ? (
          <button type="button" className={`icon-btn ${speech.listening ? "rec" : ""}`} onClick={() => (speech.listening ? speech.stop() : speech.start())} aria-label="Speak">
            <Mic size={18} />
          </button>
        ) : null}
        <button type="submit" className="icon-btn send" aria-label="Send"><Send size={18} /></button>
      </form>
    </section>
  );
}
