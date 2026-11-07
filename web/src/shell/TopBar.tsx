import { useHealth } from "../api/hooks";
import { PodMark } from "../components/ui";
import { useStore, type Tab } from "../state/store";

const TABS: { key: Tab; label: string }[] = [
  { key: "overview", label: "Overview" },
  { key: "map", label: "Map" },
  { key: "assistant", label: "Assistant" },
];

/** Logo, the three places, the quiet synthetic-data chip (the disclosure lives here and in each receipt) and help. */
export function TopBar() {
  const tab = useStore((s) => s.tab);
  const setTab = useStore((s) => s.setTab);
  const setTourOpen = useStore((s) => s.setTourOpen);
  const health = useHealth();
  const status = health.error ? "API not reachable" : health.data?.mock ? "fixtures" : health.data?.warming ? "model warming up" : null;
  return (
    <header className="topbar glass">
      <div className="brand"><PodMark /> Field Radar</div>
      <nav className="tabs" aria-label="Main">
        {TABS.map((t) => (
          <button key={t.key} type="button" className={`tab ${tab === t.key ? "on" : ""}`} onClick={() => setTab(t.key)}
            aria-current={tab === t.key ? "page" : undefined} data-tour={`tab-${t.key}`}>{t.label}</button>
        ))}
      </nav>
      <div className="topbar-right">
        <span className="chip-synthetic" role="note"
          title="The challenge's synthetic data pack: not Apetit's real figures, not facts about real farms. Futures are one plausible weather path.">
          Synthetic data pack{status ? ` · ${status}` : ""}
        </span>
        <button type="button" className="help-btn" onClick={() => setTourOpen(true)} aria-label="Help: show the tour" data-tour="help">?</button>
      </div>
    </header>
  );
}

/** The one blurred field-and-wheat layer behind every glass surface (nothing more saturated may sit behind glass). */
export function Backdrop() {
  const blobs: [number, number, number, number, string][] = [
    [-8, 8, 560, 420, "var(--backdrop-field)"], [36, -14, 520, 380, "var(--backdrop-wheat)"],
    [62, 24, 520, 440, "var(--backdrop-field)"], [18, 52, 600, 380, "var(--backdrop-wheat)"], [72, -10, 360, 300, "var(--backdrop-oat)"],
  ];
  return (
    <div className="backdrop" aria-hidden="true">
      {blobs.map(([l, t, w, h, c], i) => <i key={i} style={{ left: `${l}%`, top: `${t}%`, width: w, height: h, background: c }} />)}
    </div>
  );
}
