// The design-system primitives (handoff §9.2): status marks, ring, source chips, receipt, assumption callout,
// segmented control, season strip and the sheet (dialog with focus trap + grow-from-widget motion).
import { useEffect, useLayoutEffect, useRef, type ReactNode } from "react";
import type { Region, SourceRef, Status } from "../api/types";
import { Close } from "./Icons";

export const REGION_NAME: Record<Region, string> = { FI_SW: "SW Finland", SE_SKANE: "Skåne" };
export const STATUS_LABEL: Record<Status, string> = { ok: "On track", watch: "Watch", risk: "Bad year" };
const COLOR: Record<Status, string> = { ok: "var(--status-ok)", watch: "var(--status-watch)", risk: "var(--status-risk)" };
export const shortYear = (y: number) => String(y).slice(2);

/** ● on track (ok fill + leaf outline), ▲ watch, ◆ bad year. Never colour alone: pass `label` to say it. */
export function StatusMark({ status, size = 14, label }: { status: Status; size?: number; label?: boolean }) {
  const s = size;
  const shape = status === "ok"
    ? <circle cx={s / 2} cy={s / 2} r={s / 2 - 1.5} fill={COLOR.ok} stroke="var(--leaf)" strokeWidth={1.5} />
    : status === "watch"
      ? <path d={`M${s / 2} 1 L${s - 0.5} ${s - 1.5} L0.5 ${s - 1.5} Z`} fill={COLOR.watch} />
      : <path d={`M${s / 2} 0.5 L${s - 0.5} ${s / 2} L${s / 2} ${s - 0.5} L0.5 ${s / 2} Z`} fill={COLOR.risk} />;
  return (
    <>
      <svg className="mark" width={s} height={s} viewBox={`0 0 ${s} ${s}`} role={label ? undefined : "img"}
        aria-label={label ? undefined : STATUS_LABEL[status]} aria-hidden={label ? true : undefined}>{shape}</svg>
      {label ? <span>{STATUS_LABEL[status]}</span> : null}
    </>
  );
}

export function StatusLegend({ labels }: { labels?: Partial<Record<Status, string>> }) {
  return (
    <div className="legend">
      {(["ok", "watch", "risk"] as Status[]).map((s) => (
        <span key={s}><StatusMark status={s} size={13} /> {labels?.[s] ?? STATUS_LABEL[s]}</span>
      ))}
    </div>
  );
}

/** A donut split into parts (fractions of the whole). */
export function Ring({ parts, size = 110, stroke = 14, label }: { parts: { value: number; color: string }[]; size?: number; stroke?: number; label: string }) {
  const r = (size - stroke) / 2, c = 2 * Math.PI * r;
  const total = Math.max(1, parts.reduce((s, p) => s + p.value, 0));
  let off = 0;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label={label} style={{ flex: "none" }}>
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--surface-sunk)" strokeWidth={stroke} />
      {parts.map((p, i) => {
        const len = (p.value / total) * c;
        const el = (
          <circle key={i} cx={size / 2} cy={size / 2} r={r} fill="none" stroke={p.color} strokeWidth={stroke}
            strokeDasharray={`${len} ${c - len}`} strokeDashoffset={-off} transform={`rotate(-90 ${size / 2} ${size / 2})`} />
        );
        off += len;
        return el;
      })}
    </svg>
  );
}

export function SourceChip({ s, onClick }: { s: Pick<SourceRef, "kind" | "label" | "detail">; onClick?: () => void }) {
  const body = <><span className={`dot ${s.kind}`} aria-hidden="true" />{s.label}{s.detail ? ` · ${s.detail}` : ""}</>;
  return onClick
    ? <button type="button" className="source-chip" onClick={onClick}>{body}</button>
    : <span className="source-chip">{body}</span>;
}

/** Layer 3: what a number is built on. */
export function Receipt({ sources, foot, open = true }: { sources: SourceRef[]; foot?: ReactNode; open?: boolean }) {
  return (
    <details className="receipt" open={open}>
      <summary><ReceiptIcon /> How do we know?</summary>
      <div className="receipt-rows">
        {sources.map((s) => (
          <div key={s.node_id + s.label} className="receipt-row">
            <span className={`dot ${s.kind}`} aria-hidden="true" />{s.label}<span className="val">{s.detail}</span>
          </div>
        ))}
      </div>
      {foot ? <p className="receipt-foot">{foot}</p> : null}
    </details>
  );
}

export function Assumption({ children }: { children: ReactNode }) {
  return <div className="assumption"><strong>Assumption</strong> · {children}</div>;
}

export function Segmented<T extends string>({ options, value, onChange, label, className = "" }: {
  options: { key: T; label: string }[]; value: T; onChange: (v: T) => void; label: string; className?: string;
}) {
  return (
    <div className={`seg ${className}`} role="group" aria-label={label}>
      {options.map((o) => (
        <button key={o.key} type="button" aria-pressed={o.key === value} onClick={() => onChange(o.key)}>{o.label}</button>
      ))}
    </div>
  );
}

/** One marker per season (a year may hold two). Click picks the year; the selected year is ringed in ink. */
export function SeasonStrip({ years, marks, selected, onPick, labelEvery = 1, full = false }: {
  years: number[]; marks: Record<number, Status[]>; selected: number | null; onPick: (y: number) => void;
  labelEvery?: number; full?: boolean;
}) {
  return (
    <div className="strip" role="group" aria-label="Seasons">
      {years.map((y, i) => {
        const m = marks[y] ?? [];
        const show = i % labelEvery === 0 || y === selected || i === years.length - 1;
        return (
          <button key={y} type="button" className={y === selected ? "on" : ""} aria-pressed={y === selected} onClick={() => onPick(y)}
            aria-label={`${y}: ${m.length ? m.map((s) => STATUS_LABEL[s]).join(", ") : "no issue"}`}>
            <span className="marks">{m.length ? m.map((s, j) => <StatusMark key={j} status={s} size={16} />) : <span className="nodot" />}</span>
            <span>{show ? (full ? y : shortYear(y)) : "​"}</span>
          </button>
        );
      })}
    </div>
  );
}

const FOCUSABLE = 'a[href],button:not([disabled]),input,textarea,select,summary,[tabindex]:not([tabindex="-1"])';

/** A dialog that grows from the widget that opened it (FLIP), traps focus, closes on Esc and returns focus. */
export function Sheet({ label, from, onClose, children, side = false }: {
  label: string; from?: DOMRect | null; onClose: () => void; children: ReactNode; side?: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const opener = useRef<Element | null>(document.activeElement);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (!from || reduce) { el.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 180, easing: "ease-out" }); return; }
    // Grow out of the opener: a uniform scale from its centre (non-uniform scale squashes the text).
    const to = el.getBoundingClientRect();
    const ox = from.left + from.width / 2 - to.left, oy = from.top + from.height / 2 - to.top;
    el.style.transformOrigin = `${ox}px ${Math.max(0, Math.min(to.height, oy))}px`;
    el.style.willChange = "transform, opacity";
    el.animate([
      { transform: "scale(.92)", opacity: 0 },
      { transform: "none", opacity: 1 },
    ], { duration: 340, easing: "cubic-bezier(.22,1,.36,1)" }).onfinish = () => { el.style.transformOrigin = ""; el.style.willChange = ""; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => {
    const el = ref.current;
    const first = el?.querySelector<HTMLElement>(FOCUSABLE);
    first?.focus({ preventScroll: true });
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") { e.stopPropagation(); onClose(); return; }
      if (e.key !== "Tab" || !el) return;
      const f = [...el.querySelectorAll<HTMLElement>(FOCUSABLE)].filter((x) => x.offsetParent !== null);
      if (!f.length) return;
      if (e.shiftKey && document.activeElement === f[0]) { e.preventDefault(); f[f.length - 1].focus(); }
      else if (!e.shiftKey && document.activeElement === f[f.length - 1]) { e.preventDefault(); f[0].focus(); }
    };
    document.addEventListener("keydown", onKey);
    const back = opener.current;
    return () => { document.removeEventListener("keydown", onKey); (back as HTMLElement | null)?.focus?.({ preventScroll: true }); };
  }, [onClose]);
  return (
    <>
      <div className="scrim" onMouseDown={onClose} aria-hidden="true" />
      <div ref={ref} className={`sheet glass glass-strong ${side ? "side" : ""}`} role="dialog" aria-modal="true" aria-label={label}>
        <button type="button" className="icon-btn sheet-close" onClick={onClose} aria-label="Close"><Close size={18} /></button>
        {children}
      </div>
    </>
  );
}

export function Crumbs({ items }: { items: { label: string; onClick?: () => void }[] }) {
  return (
    <nav className="crumbs" aria-label="Breadcrumb">
      {items.map((it, i) => (
        <span key={it.label} style={{ display: "contents" }}>
          {i ? <span aria-hidden="true">›</span> : null}
          {it.onClick ? <button type="button" onClick={it.onClick}>{it.label}</button> : <span>{it.label}</span>}
        </span>
      ))}
    </nav>
  );
}

export function Typing() {
  return <div className="typing glass" aria-label="Working"><span /><span /><span /></div>;
}

// ── small icons used by the redesign (stroke = currentColor) ───────
type P = { size?: number };
const ic = (d: ReactNode, size = 20) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}
    strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{d}</svg>
);
export const ReceiptIcon = ({ size = 20 }: P) => ic(<><path d="M6 3h12v18l-3-2-3 2-3-2-3 2z" /><path d="M9 8h6M9 12h6" /></>, size);
export const WarnIcon = ({ size = 20 }: P) => ic(<><path d="M12 3 2 20h20z" /><path d="M12 10v4M12 17v.5" /></>, size);
export const FieldsIcon = ({ size = 20 }: P) => ic(<><rect x={3} y={5} width={18} height={14} rx={2} /><path d="M3 12h18M12 5v14" /></>, size);
export const SproutIcon = ({ size = 20 }: P) => ic(<><path d="M12 21V11" /><path d="M12 11C12 7 9 5 5 5c0 4 3 6 7 6z" /><path d="M12 11c0-4 3-6 7-6 0 4-3 6-7 6z" /></>, size);
export const PinIcon = ({ size = 20 }: P) => ic(<><path d="M12 21s-7-6.5-7-12a7 7 0 0 1 14 0c0 5.5-7 12-7 12z" /><circle cx={12} cy={9} r={2.5} /></>, size);
export const CheckCircle = ({ size = 20 }: P) => ic(<><circle cx={12} cy={12} r={9} /><path d="m8 12 3 3 5-6" /></>, size);
export const EuroIcon = ({ size = 20 }: P) => ic(<><path d="M17 6.5A7 7 0 1 0 17 17.5" /><path d="M4 10h9M4 14h9" /></>, size);
export const SearchIcon = ({ size = 20 }: P) => ic(<><circle cx={11} cy={11} r={6} /><path d="m20 20-4.5-4.5" /></>, size);
export const TrendIcon = ({ size = 20 }: P) => ic(<path d="m3 17 6-6 4 4 8-8" />, size);
export const ChevronLeft = ({ size = 20 }: P) => ic(<path d="m15 5-7 7 7 7" />, size);
export const ChevronRight = ({ size = 20 }: P) => ic(<path d="m9 5 7 7-7 7" />, size);
export const CloseIcon = ({ size = 20 }: P) => ic(<path d="M6 6l12 12M18 6 6 18" />, size);
export const PlayIcon = ({ size = 20 }: P) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M8 5.5v13a1 1 0 0 0 1.5.86l10.5-6.5a1 1 0 0 0 0-1.72L9.5 4.64A1 1 0 0 0 8 5.5z" /></svg>
);
export const PauseIcon = ({ size = 20 }: P) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><rect x={6.5} y={5} width={4} height={14} rx={1.2} /><rect x={13.5} y={5} width={4} height={14} rx={1.2} /></svg>
);
export const CheckIcon = ({ size = 20 }: P) => ic(<path d="m5 12.5 4.5 4.5L19 7.5" />, size);
export const ArrowRight = ({ size = 20 }: P) => ic(<path d="M5 12h14M13 6l6 6-6 6" />, size);
export const PodMark = ({ size = 28 }: P) => (
  <svg width={size} height={size * 0.6} viewBox="0 0 40 24" aria-hidden="true">
    <rect x={1} y={3} width={38} height={18} rx={9} fill="var(--apetit)" />
    {[11, 20, 29].map((x) => <circle key={x} cx={x} cy={12} r={4.2} fill="var(--leaf-soft)" />)}
  </svg>
);

/** The Field Radar mark: a sweep over furrows, in a lit green squircle. */
export const BrandMark = ({ size = 30 }: P) => (
  <span className="brand-mark" style={{ width: size, height: size, borderRadius: size * 0.3 }} aria-hidden="true">
    <svg width={size * 0.66} height={size * 0.66} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round">
      <path d="M3.5 18.5a10 10 0 0 1 17 0" strokeWidth={1.8} opacity={0.55} />
      <path d="M7 18.5a6 6 0 0 1 10 0" strokeWidth={1.8} opacity={0.8} />
      <path d="M12 18.5 18.5 7" strokeWidth={2.2} />
      <circle cx={12} cy={18.5} r={1.9} fill="currentColor" stroke="none" />
    </svg>
  </span>
);
