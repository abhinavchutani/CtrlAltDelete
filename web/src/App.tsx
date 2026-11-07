// Layout only: no data logic here. The map is always mounted (switching tabs keeps its place and data); the
// Overview sits over a dimmed map, and the assistant and the all-plans table float over whichever is open.
import { useState } from "react";
import { ChatDock } from "./features/chat/ChatDock";
import { ViewPanel } from "./features/fieldradar/ViewPanel";
import { YearBar } from "./features/fieldradar/YearBar";
import { MapView } from "./features/map/MapView";
import { PlanFinder } from "./features/plans/PlanFinder";
import { PlansModal } from "./features/plans/PlansModal";
import { Overview } from "./overview/Overview";
import { TopBar } from "./shell/TopBar";
import { useStore } from "./state/store";
import { Tour } from "./tour/Tour";

export default function App() {
  const tab = useStore((s) => s.tab);
  const [allPlans, setAllPlans] = useState(false);
  const openAll = () => setAllPlans(true);
  return (
    <div className={`fr tab-${tab}`}>
      <main className="stage">
        <MapView />
        <TopBar />
        {tab === "map" ? (
          <>
            <ViewPanel />
            <div className="right-stack"><PlanFinder onAll={openAll} /></div>
            <YearBar />
          </>
        ) : (
          <div className="page-layer"><Overview onAll={openAll} /></div>
        )}
        <ChatDock />
        {allPlans ? <PlansModal onClose={() => setAllPlans(false)} /> : null}
      </main>
      <Tour />
    </div>
  );
}
