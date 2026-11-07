import { useStore } from "../../state/store";
import { Chart, Chat, Check, Leaf, MapIcon } from "../../components/Icons";

/** Left rail: map (closes drawers), insights, decisions, assistant. */
export function Sidebar() {
  const { drawer, setDrawer, chatMode, setChatMode } = useStore();
  const item = (active: boolean, label: string, icon: React.ReactNode, onClick: () => void) => (
    <button className={`rail-btn ${active ? "on" : ""}`} onClick={onClick} aria-label={label} title={label}>{icon}</button>
  );
  return (
    <nav className="rail" aria-label="Main">
      <div className="rail-logo"><Leaf size={30} /></div>
      {item(drawer === "none", "Map", <MapIcon />, () => drawer !== "none" && setDrawer(drawer))}
      {item(drawer === "insights", "Scenario insights", <Chart />, () => setDrawer("insights"))}
      {item(drawer === "decisions", "Decision board", <Check />, () => setDrawer("decisions"))}
      {item(chatMode !== "collapsed", "Assistant", <Chat />, () => setChatMode(chatMode === "collapsed" ? "docked" : "collapsed"))}
    </nav>
  );
}
