import { useState } from "react";
import { useSpeech, type SpeechLang } from "./useSpeech";

export function MicButton({ onText }: { onText: (t: string) => void }) {
  const [lang, setLang] = useState<SpeechLang>("en-US");
  const s = useSpeech(onText);
  if (!s.supported) return <span className="muted">(no speech in this browser)</span>;
  return (
    <span className="row">
      <select value={lang} onChange={(e) => setLang(e.target.value as SpeechLang)} aria-label="language">
        <option value="en-US">EN</option><option value="fi-FI">FI</option><option value="sv-SE">SV</option>
      </select>
      <button onClick={() => (s.listening ? s.stop() : s.start(lang))} aria-pressed={s.listening}>{s.listening ? "Stop" : "Speak"}</button>
      {s.error ? <span className="sev-critical">{s.error}</span> : null}
    </span>
  );
}
