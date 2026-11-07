// Layout only: no data logic here. Field Radar: the map fills the stage; glass panels float over it;
// the assistant docks beside it (or is maximised / collapsed).
import { SyntheticBanner } from "./components/SyntheticBanner";
import { AlertPopup } from "./features/alerts/AlertPopup";
import { ChatDock } from "./features/chat/ChatDock";
import { Drawer } from "./features/fieldradar/Drawer";
import { LayerPanel } from "./features/fieldradar/LayerPanel";
import { ParcelCard } from "./features/fieldradar/ParcelCard";
import { Sidebar } from "./features/fieldradar/Sidebar";
import { StatsBar } from "./features/fieldradar/StatsBar";
import { MapView } from "./features/map/MapView";
import { useStore } from "./state/store";

export default function App() {
  const chatMode = useStore((s) => s.chatMode);
  return (
    <div className={`fr chat-${chatMode}`}>
      <Sidebar />
      <main className="stage">
        <MapView />
        <div className="brand">FIELD RADAR</div>
        <SyntheticBanner />
        <LayerPanel />
        <Drawer />
        <div className="right-stack">
          <ParcelCard />
          <AlertPopup />
        </div>
        <StatsBar />
      </main>
      <ChatDock />
    </div>
  );
}
