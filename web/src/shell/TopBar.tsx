import { useHealth } from "../api/hooks";
import { Help, Leaf } from "../components/Icons";
import { useStore, type Tab } from "../state/store";

const TABS: { key: Tab; label: string }[] = [
  { key: "overview", label: "Overview" },
  { key: "map", label: "Map" },
];

/** Brand, the three places (Overview · Map · Assistant), the synthetic-data note (always visible) and help. */
export function TopBar() {
  const tab = useStore((s) => s.tab);
  const setTab = useStore((s) => s.setTab);
  const setTourOpen = useStore((s) => s.setTourOpen);
  const assistantOpen = useStore((s) => s.assistantOpen);
  const setAssistantOpen = useStore((s) => s.setAssistantOpen);
  const health = useHealth();
  const status = health.error ? "API not reachable" : health.data?.mock ? "mock fixtures" : health.data?.warming ? "model warming up" : null;
  return (
    <header className="topbar">
      <div className="brand"><Leaf size={22} /> FIELD RADAR</div>
      <nav className="tabs" aria-label="Main">
        {TABS.map((t) => (
          <button key={t.key} className={`tab ${tab === t.key && !assistantOpen ? "on" : ""}`}
            onClick={() => { setAssistantOpen(false); setTab(t.key); }}
            aria-current={tab === t.key ? "page" : undefined} data-tour={`tab-${t.key}`}>
            {t.label}
          </button>
        ))}
        <button className={`tab ${assistantOpen ? "on" : ""}`} onClick={() => setAssistantOpen(!assistantOpen)}
          aria-expanded={assistantOpen} data-tour="tab-assistant">Assistant</button>
      </nav>
      <div className="topbar-right">
        <span className="synthetic" role="note" title="Synthetic data: not Apetit's real figures, not facts about real farms. Futures are one plausible weather path.">
          Synthetic data, not Apetit's real figures · one plausible weather path{status ? ` · ${status}` : ""}
        </span>
        <button className="help-btn" onClick={() => setTourOpen(true)} aria-label="Show the tour" data-tour="help">
          <Help size={20} />
        </button>
      </div>
    </header>
  );
}
