// Layout only: no data logic here. One fixed backdrop, the glass header, then the open tab.
import { useEffect } from "react";
import { AssistantPage } from "./features/assistant/AssistantPage";
import { MapPage } from "./features/map/MapPage";
import { Overview } from "./overview/Overview";
import { PlansSheet } from "./overview/Sheets";
import { Backdrop, TopBar } from "./shell/TopBar";
import { useStore } from "./state/store";
import { Tour } from "./tour/Tour";

export default function App() {
  const tab = useStore((s) => s.tab);
  const sheet = useStore((s) => s.sheet);
  const closeSheet = useStore((s) => s.closeSheet);
  const setTab = useStore((s) => s.setTab);
  // the tab lives in the URL hash (#map, #assistant), so links and the back button work
  useEffect(() => {
    const read = () => { const h = window.location.hash.slice(1); if (h === "map" || h === "assistant" || h === "overview") setTab(h); };
    window.addEventListener("hashchange", read);
    return () => window.removeEventListener("hashchange", read);
  }, [setTab]);
  useEffect(() => { if (window.location.hash.slice(1) !== tab) history.replaceState(null, "", `#${tab}`); }, [tab]);
  return (
    <div className={`app tab-${tab}`}>
      {tab !== "map" ? <Backdrop /> : null}
      <TopBar />
      {tab === "overview" ? <Overview /> : tab === "map" ? <MapPage /> : <AssistantPage />}
      {tab !== "overview" && sheet?.kind === "plans" ? <PlansSheet onClose={closeSheet} /> : null}
      <Tour />
    </div>
  );
}
