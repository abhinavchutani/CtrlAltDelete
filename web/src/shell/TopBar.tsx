import { useHealth } from "../api/hooks";
import { useStore, type Tab } from "../state/store";
import { useTheme, type ThemePref } from "../theme/theme";

const TABS: { key: Tab; label: string }[] = [
  { key: "overview", label: "Overview" },
  { key: "assistant", label: "Assistant" },
];

const ico = (d: React.ReactNode) => (
  <svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.9} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{d}</svg>
);
const THEMES: { key: ThemePref; label: string; icon: React.ReactNode }[] = [
  { key: "light", label: "Light", icon: ico(<><circle cx={12} cy={12} r={4} /><path d="M12 2.5v2M12 19.5v2M4.6 4.6l1.4 1.4M18 18l1.4 1.4M2.5 12h2M19.5 12h2M4.6 19.4 6 18M18 6l1.4-1.4" /></>) },
  { key: "system", label: "Match system", icon: ico(<><rect x={3} y={4} width={18} height={13} rx={2.5} /><path d="M8.5 21h7M12 17v4" /></>) },
  { key: "dark", label: "Dark", icon: ico(<path d="M20.5 14.5A8.5 8.5 0 0 1 9.5 3.5a8.5 8.5 0 1 0 11 11z" />) },
];

/** Brand, the three places (a floating glass tab bar), the synthetic-data disclosure, appearance and help. */
export function TopBar() {
  const tab = useStore((s) => s.tab);
  const setTab = useStore((s) => s.setTab);
  const setTourOpen = useStore((s) => s.setTourOpen);
  const pref = useTheme((s) => s.pref);
  const setPref = useTheme((s) => s.setPref);
  const health = useHealth();
  const status = health.error ? "API not reachable" : health.data?.mock ? "fixtures" : health.data?.warming ? "model warming up" : null;
  return (
    <header className="topbar">
      <div className="brand"><img src="/apetit-logo.png" alt="Apetit" /> Radar</div>
      <nav className="tabs glass" aria-label="Main">
        {TABS.map((t) => (
          <button key={t.key} type="button" className={`tab ${tab === t.key ? "on" : ""}`} onClick={() => setTab(t.key)}
            aria-current={tab === t.key ? "page" : undefined} data-tour={`tab-${t.key}`}>{t.label}</button>
        ))}
      </nav>
      <div className="topbar-right">
        <span className="chip-synthetic" role="note"
          title="The challenge's synthetic data pack: not Apetit's real figures, not facts about real farms. Futures are one plausible weather path.">
          Synthetic data{status ? ` · ${status}` : ""}
        </span>
        <div className="theme-switch glass" role="radiogroup" aria-label="Appearance">
          {THEMES.map((t) => (
            <button key={t.key} type="button" role="radio" aria-checked={pref === t.key} aria-label={t.label} title={t.label}
              onClick={() => setPref(t.key)}>{t.icon}</button>
          ))}
        </div>
        <button type="button" className="help-btn glass" onClick={() => setTourOpen(true)} aria-label="Help: show the tour" data-tour="help">?</button>
      </div>
    </header>
  );
}

/** Ambient light behind every glass surface: field, wheat and sky, softly blurred. Recolours with the theme. */
export function Backdrop() {
  const blobs: [number, number, number, number, string][] = [
    [-10, -6, 620, 480, "var(--bg-ambient-1)"], [44, -18, 560, 400, "var(--bg-ambient-2)"],
    [68, 30, 560, 480, "var(--bg-ambient-3)"], [6, 56, 620, 420, "var(--bg-ambient-2)"], [40, 70, 520, 380, "var(--bg-ambient-1)"],
  ];
  return (
    <div className="backdrop" aria-hidden="true">
      {blobs.map(([l, t, w, h, c], i) => <i key={i} style={{ left: `${l}%`, top: `${t}%`, width: w, height: h, background: c }} />)}
    </div>
  );
}
