// Layout only: no data logic here.
import { SyntheticBanner } from "./components/SyntheticBanner";
import { AlertList } from "./features/alerts/AlertList";
import { AlertPopup } from "./features/alerts/AlertPopup";
import { AskPanel } from "./features/ask/AskPanel";
import { DecisionBoard } from "./features/board/DecisionBoard";
import { HedgeChart } from "./features/hedge/HedgeChart";
import { MapView } from "./features/map/MapView";
import { Meters } from "./features/meters/Meters";
import { PathwaysGantt } from "./features/pathways/PathwaysGantt";
import { LeverEditor } from "./features/simulate/LeverEditor";
import { ScenarioPicker } from "./features/simulate/ScenarioPicker";
import { SpecChips } from "./features/simulate/SpecChips";
import { Timeline } from "./features/timeline/Timeline";
import { CommandBar } from "./features/voice/CommandBar";
import { useStore } from "./state/store";

export default function App() {
  const door = useStore((s) => s.door);
  const setDoor = useStore((s) => s.setDoor);
  return (
    <div className="app">
      <header>
        <strong>Navigator</strong>
        <ScenarioPicker />
        <CommandBar />
      </header>
      <SyntheticBanner />
      <main className="map">
        <MapView />
        <AlertPopup />
      </main>
      <aside className="side">
        <div className="tabs row" role="tablist">
          <button role="tab" aria-selected={door === "simulate"} onClick={() => setDoor("simulate")}>Simulate</button>
          <button role="tab" aria-selected={door === "ask"} onClick={() => setDoor("ask")}>Ask</button>
        </div>
        {door === "ask" ? <AskPanel /> : (
          <>
            <SpecChips />
            <LeverEditor />
            <Meters />
            <AlertList />
          </>
        )}
        <HedgeChart />
        <PathwaysGantt />
      </aside>
      <footer className="bottom">
        <Timeline />
        <DecisionBoard />
      </footer>
    </div>
  );
}
