import { useStore } from "../../state/store";
import { Close } from "../../components/Icons";
import { AlertList } from "../alerts/AlertList";
import { DecisionBoard } from "../board/DecisionBoard";
import { HedgeChart } from "../hedge/HedgeChart";
import { Meters } from "../meters/Meters";
import { PathwaysGantt } from "../pathways/PathwaysGantt";
import { LeverEditor } from "../simulate/LeverEditor";
import { SpecChips } from "../simulate/SpecChips";

/** Slide-over panels: the scenario's meters, alerts, hedge and pathways, or the decision board. */
export function Drawer() {
  const { drawer, setDrawer } = useStore();
  if (drawer === "none") return null;
  return (
    <aside className={`glass drawer ${drawer}`} aria-label={drawer === "insights" ? "Scenario insights" : "Decision board"}>
      <header className="drawer-head">
        <h2>{drawer === "insights" ? "Scenario insights" : "Decision board"}</h2>
        <button className="icon-btn" onClick={() => setDrawer(drawer)} aria-label="Close"><Close size={18} /></button>
      </header>
      <div className="drawer-body">
        {drawer === "insights" ? (
          <>
            <SpecChips />
            <LeverEditor />
            <Meters />
            <AlertList />
            <HedgeChart />
            <PathwaysGantt />
          </>
        ) : <DecisionBoard />}
      </div>
    </aside>
  );
}
