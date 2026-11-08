// A short guided tour. It opens by itself on a visitor's first visit (remembered in this browser), with ?tour in
// the URL, or from the help button. Each step spotlights one part of the screen ([data-tour="…"]).
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { useStore } from "../state/store";

type Step = { target: string | null; title: string; body: string; tab: "overview" | "map" | "assistant" };
const STEPS: Step[] = [
  { tab: "overview", target: null, title: "Welcome to Apetit Radar",
    body: "What the weather could cost the farms that grow for Apetit, season by season to 2040, and the changes that cut it. It runs on the challenge's synthetic data pack." },
  { tab: "overview", target: "money", title: "One number, then the reasons",
    body: "Each card gives one answer. Tap it to see what drives it, and at the bottom, how we know." },
  { tab: "overview", target: "plan", title: "The best plan",
    body: "The model simulates every change it can, alone and combined, and re-checks the best in hotter and cooler futures." },
  { tab: "map", target: "lens", title: "Read the map",
    body: "Fields are coloured by how their season goes: ● on track, ▲ watch, ◆ bad year. Switch the lens to see drought, heat or rain." },
  { tab: "map", target: "years", title: "Play the problem years",
    body: "Press play to step through the seasons with a problem, or tap any year." },
  { tab: "assistant", target: "graph", title: "Ask, simulate, teach",
    body: "Ask the data, run a plan through the yield model, or tell it what your team knows. The graph lights up what each answer used." },
  { tab: "assistant", target: "help", title: "That's it", body: "Replay this tour any time from this button." },
];
const SEEN_KEY = "fieldradar.tour.seen.v4"; // v4: the redesign, so everyone sees it once more
const PAD = 8, CARD_W = 340, GAP = 16;

function seen(): boolean {
  try { return localStorage.getItem(SEEN_KEY) === "1"; } catch { return false; }
}
function markSeen() {
  try { localStorage.setItem(SEEN_KEY, "1"); } catch { /* private window: the tour just shows again next time */ }
}

type Box = { top: number; left: number; width: number; height: number };
const measure = (target: string | null): Box | null => {
  const el = target ? document.querySelector(`[data-tour="${target}"]`) : null;
  if (!el) return null;
  el.scrollIntoView({ block: "nearest" });
  const r = el.getBoundingClientRect();
  return { top: r.top - PAD, left: r.left - PAD, width: r.width + 2 * PAD, height: r.height + 2 * PAD };
};

/** Where the card goes: beside the spotlight if it fits (right, left, below, above), else centred. */
function cardPos(box: Box | null, cardH: number): { top: number; left: number } {
  const vw = window.innerWidth, vh = window.innerHeight;
  const centre = { top: (vh - cardH) / 2, left: (vw - CARD_W) / 2 };
  if (!box || box.width * box.height > 0.45 * vw * vh) return centre;
  const clampTop = (t: number) => Math.min(Math.max(16, t), vh - cardH - 16);
  const clampLeft = (l: number) => Math.min(Math.max(16, l), vw - CARD_W - 16);
  if (box.left + box.width + GAP + CARD_W < vw - 16) return { top: clampTop(box.top), left: box.left + box.width + GAP };
  if (box.left - GAP - CARD_W > 16) return { top: clampTop(box.top), left: box.left - GAP - CARD_W };
  if (box.top + box.height + GAP + cardH < vh - 16) return { top: box.top + box.height + GAP, left: clampLeft(box.left) };
  return { top: Math.max(16, box.top - GAP - cardH), left: clampLeft(box.left) };
}

export function Tour() {
  const open = useStore((s) => s.tourOpen);
  const setOpen = useStore((s) => s.setTourOpen);
  const setTab = useStore((s) => s.setTab);
  const [i, setI] = useState(0);
  const [box, setBox] = useState<Box | null>(null);
  const [cardH, setCardH] = useState(200);
  const card = useRef<HTMLDivElement>(null);
  const next = useRef<HTMLButtonElement>(null);
  const step = STEPS[i];

  // first visit (or ?tour): open by itself, once the panels have rendered
  useEffect(() => {
    const forced = new URLSearchParams(window.location.search).has("tour");
    if (!forced && (seen() || new URLSearchParams(window.location.search).has("notour"))) return;
    const t = setTimeout(() => setOpen(true), 600);
    return () => clearTimeout(t);
  }, [setOpen]);
  useEffect(() => { if (open) setI(0); }, [open]);
  // each step shows its own tab
  useEffect(() => { if (open) setTab(step.tab); }, [open, step.tab, setTab]);

  const close = useCallback(() => { markSeen(); setOpen(false); }, [setOpen]);
  const go = useCallback((d: number) => {
    if (i + d >= STEPS.length) close();
    else setI(Math.max(0, i + d));
  }, [i, close]);

  // follow the target while this step is up (panels can move as data loads or the window resizes)
  useLayoutEffect(() => {
    if (!open) return;
    const update = () => { setBox(measure(step.target)); if (card.current) setCardH(card.current.offsetHeight); };
    update();
    const late = [setTimeout(update, 120), setTimeout(update, 450), setTimeout(update, 900)]; // after a tab switch
    window.addEventListener("resize", update);
    return () => { late.forEach(clearTimeout); window.removeEventListener("resize", update); };
  }, [open, step.target, step.tab]);
  useEffect(() => { if (open) next.current?.focus(); }, [open, i]);
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
      else if (e.key === "ArrowRight") go(1);
      else if (e.key === "ArrowLeft") go(-1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, go, close]);

  if (!open) return null;
  const spot = box ?? { top: window.innerHeight / 2, left: window.innerWidth / 2, width: 0, height: 0 };
  const pos = cardPos(box, cardH);
  const last = i === STEPS.length - 1;
  return (
    <div className="tour-scrim" role="dialog" aria-modal="true" aria-labelledby="tour-title">
      <div className="tour-hole" style={spot} />
      <div className="tour-card glass glass-strong" ref={card} style={{ top: pos.top, left: pos.left, width: CARD_W }}>
                <h2 id="tour-title">{step.title}</h2>
        <p>{step.body}</p>
        <div className="tour-nav">
          <span className="muted">{i + 1} of {STEPS.length}</span>
          {last ? null : <button type="button" className="link" onClick={close}>Skip</button>}
          {i > 0 ? <button type="button" className="btn btn-ghost" onClick={() => go(-1)}>Back</button> : null}
          <button type="button" className="btn btn-primary" ref={next} onClick={() => go(1)}>{i === 0 ? "Show me" : last ? "Done" : "Next"}</button>
        </div>
      </div>
    </div>
  );
}
