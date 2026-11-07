// Inline line icons (no icon library), stroke = currentColor so they follow the theme.
type P = { size?: number; className?: string };
const svg = (d: React.ReactNode, { size = 20, className }: P) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.7}
    strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">{d}</svg>
);

export const Leaf = (p: P) => svg(<><path d="M12 21c0-6 0-9-6-12 6 0 9 2 10 6" /><path d="M12 21c0-7 2-11 9-13-1 7-4 10-9 10" /></>, p);
export const MapIcon = (p: P) => svg(<><path d="M9 4 3 6v14l6-2 6 2 6-2V4l-6 2-6-2z" /><path d="M9 4v14M15 6v14" /></>, p);
export const Chart = (p: P) => svg(<><path d="M5 20v-6M12 20V8M19 20v-9" /></>, p);
export const Layers = (p: P) => svg(<><path d="m12 3 9 5-9 5-9-5 9-5z" /><path d="m3 13 9 5 9-5" /></>, p);
export const Gear = (p: P) => svg(<><circle cx={12} cy={12} r={3} /><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3h.1a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8v.1a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" /></>, p);
export const Check = (p: P) => svg(<><path d="M9 11l3 3 8-8" /><path d="M20 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" /></>, p);
export const Chat = (p: P) => svg(<><path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z" /></>, p);
export const Bell = (p: P) => svg(<><path d="M18 8a6 6 0 1 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" /><path d="M13.7 21a2 2 0 0 1-3.4 0" /></>, p);
export const Play = (p: P) => svg(<path d="M8 5v14l11-7z" fill="currentColor" stroke="none" />, p);
export const Pause = (p: P) => svg(<><path d="M8 5v14M16 5v14" strokeWidth={3} /></>, p);
export const Drop = (p: P) => svg(<path d="M12 3s7 7.5 7 12a7 7 0 0 1-14 0c0-4.5 7-12 7-12z" />, p);
export const Euro = (p: P) => svg(<><path d="M17 6.5A7 7 0 1 0 17 17.5" /><path d="M4 10h9M4 14h9" /></>, p);
export const Sun = (p: P) => svg(<><circle cx={12} cy={12} r={4} /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></>, p);
export const Max = (p: P) => svg(<><path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7" /></>, p);
export const Min = (p: P) => svg(<><path d="M4 14h6v6M20 10h-6V4M14 10l7-7M3 21l7-7" /></>, p);
export const Dock = (p: P) => svg(<><rect x={3} y={4} width={18} height={16} rx={2} /><path d="M15 4v16" /></>, p);
export const Close = (p: P) => svg(<path d="M6 6l12 12M18 6 6 18" />, p);
export const Send = (p: P) => svg(<><path d="m22 2-7 20-4-9-9-4z" /><path d="M22 2 11 13" /></>, p);
export const Mic = (p: P) => svg(<><rect x={9} y={2} width={6} height={12} rx={3} /><path d="M5 10a7 7 0 0 0 14 0M12 19v3" /></>, p);
export const Pin = (p: P) => svg(<><path d="M12 22s7-6.5 7-12a7 7 0 0 0-14 0c0 5.5 7 12 7 12z" /><circle cx={12} cy={10} r={2.5} /></>, p);
export const Help = (p: P) => svg(<><circle cx={12} cy={12} r={9} /><path d="M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.7.3-1 .9-1 1.6v.4" /><path d="M12 17h.01" /></>, p);
export const Reset = (p: P) => svg(<><path d="M3 12a9 9 0 1 0 3-6.7L3 8" /><path d="M3 3v5h5" /></>, p);
