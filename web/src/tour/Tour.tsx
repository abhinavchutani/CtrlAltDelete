// A short guided tour. It opens by itself on a visitor's first visit (remembered in this browser), with ?tour in
// the URL, or from the help button. Each step spotlights one part of the screen ([data-tour="…"]).
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { useStore } from "../state/store";

type Step = { target: string | null; title: string; body: string; tab: "overview" | "map" };
const STEPS: Step[] = [
  { tab: "overview", target: null, title: "Welcome to Field Radar",
    body: "See what the weather could cost the farms that grow vegetables for Apetit, year by year to 2040, and find the changes that cut that loss before the season starts. It runs on the challenge's data pack (synthetic)." },
  { tab: "overview", target: "hero", title: "The problem, and the fix",
    body: "How much money the weather puts at risk each year on today's plan, and the best plan the model found after simulating every change it can, alone and combined." },
  { tab: "overview", target: "built-on", title: "Built on the data",
    body: "Farms, fields, harvest records, pea deliveries and decades of daily weather. The model was checked on harvests it had never seen." },
  { tab: "map", target: "map", title: "Read the map",
    body: "Each soft glow is a farm: green on track, amber watch, red a bad year. When the weather turns, you see it: rain, heat haze, dry dust." },
  { tab: "map", target: "view", title: "Choose what you see",
    body: "Pick a climate future, what the colours show (crop health, drought or heat), and switch the weather effects on or off." },
  { tab: "map", target: "years", title: "Play the years",
    body: "Press play. Each dot is a problem: playback stops there, flies to the worst-hit field and shows what happened, the month's weather and what you can do." },
  { tab: "map", target: "change", title: "Find the best plan",
    body: "The model tests every plan it can simulate and re-checks the best in hotter and cooler futures. Or build your own plan and simulate it." },
  { tab: "map", target: "tab-assistant", title: "Ask, or simulate anything",
    body: "The assistant opens over the map. Ask about the data, say a what-if and get its full simulation, or ask it to find the best plan." },
  { tab: "map", target: "help", title: "That's it",
    body: "Replay this tour any time from this button." },
];
const SEEN_KEY = "fieldradar.tour.seen.v2"; // v2: the tour changed, so everyone sees it once more
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
    if (!forced && seen()) return;
    const t = setTimeout(() => setOpen(true), 600);
    return () => clearTimeout(t);
  }, [setOpen]);
  useEffect(() => { if (open) setI(0); }, [open]);
  // each step shows its own tab; the assistant stays closed while touring
  useEffect(() => { if (open) { setTab(step.tab); useStore.getState().setAssistantOpen(false); } }, [open, step.tab, setTab]);

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
    <div className="tour" role="dialog" aria-modal="true" aria-labelledby="tour-title">
      <div className="tour-spot" style={spot} />
      <div className="tour-card glass" ref={card} style={{ top: pos.top, left: pos.left, width: CARD_W }}>
        <div className="tour-count">{i + 1} of {STEPS.length}</div>
        <h2 id="tour-title">{step.title}</h2>
        <p>{step.body}</p>
        <div className="tour-actions">
          {last ? <span /> : <button className="link-btn" onClick={close}>Skip tour</button>}
          <div className="tour-nav">
            {i > 0 ? <button className="btn-ghost" onClick={() => go(-1)}>Back</button> : null}
            <button className="btn-run" ref={next} onClick={() => go(1)}>{i === 0 ? "Show me" : last ? "Done" : "Next"}</button>
          </div>
        </div>
        <div className="tour-dots" aria-hidden="true">
          {STEPS.map((_, k) => <span key={k} className={k === i ? "on" : ""} />)}
        </div>
      </div>
    </div>
  );
}
