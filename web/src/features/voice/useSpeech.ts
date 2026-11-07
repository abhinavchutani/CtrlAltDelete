// Browser Web Speech API (Chrome/Edge/Safari). When missing, `supported` is false and the text box is the way in.
import { useCallback, useRef, useState } from "react";

export type SpeechLang = "en-US" | "fi-FI" | "sv-SE";

type Rec = {
  lang: string; interimResults: boolean; maxAlternatives: number;
  start: () => void; stop: () => void;
  onresult: ((e: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null;
  onerror: ((e: { error: string }) => void) | null;
  onend: (() => void) | null;
};

const Ctor = (): (new () => Rec) | undefined => {
  const w = window as unknown as { SpeechRecognition?: new () => Rec; webkitSpeechRecognition?: new () => Rec };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition;
};

export function useSpeech(onText: (text: string) => void) {
  const [listening, setListening] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const rec = useRef<Rec | null>(null);
  const supported = typeof window !== "undefined" && !!Ctor();

  const start = useCallback((lang: SpeechLang = "en-US") => {
    const C = Ctor();
    if (!C) return setError("speech not supported in this browser: type instead");
    const r = new C();
    r.lang = lang; r.interimResults = false; r.maxAlternatives = 1;
    r.onresult = (e) => { const t = e.results[0]?.[0]?.transcript; if (t) onText(t); };
    r.onerror = (e) => setError(e.error);
    r.onend = () => setListening(false);
    rec.current = r; setError(null); setListening(true); r.start();
  }, [onText]);

  const stop = useCallback(() => rec.current?.stop(), []);
  return { supported, listening, error, start, stop };
}
