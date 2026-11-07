import { useActiveScenario, useBoard } from "../../api/hooks";
import { useStore } from "../../state/store";
import { Panel, Status } from "../../components/Status";
import { EvidenceChips } from "../ask/EvidenceChips";
import { DecisionDialog } from "./DecisionDialog";

/** Decision board (on fixtures while retrieval is on hold). */
export function DecisionBoard() {
  const sim = useActiveScenario();
  const board = useBoard(sim.data?.scenario_id);
  const { boardDialogRow, openDecision } = useStore();
  const rows = board.data ?? [];
  const open = rows.find((r) => r.row_id === boardDialogRow);
  return (
    <Panel title="Decision board">
      <Status loading={board.isLoading} error={board.error} empty={!board.isLoading && !rows.length} />
      {rows.length ? (
        <table>
          <thead><tr>{["Risk", "Crop / region", "€ at risk", "1-in-10", "Hazard", "Action", "Owner", "Decide by", "Trigger", "Evidence", "Status", ""].map((h) => <th key={h}>{h}</th>)}</tr></thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.row_id}>
                <td>{r.risk}</td><td>{r.crop} / {r.region}</td><td>{r.eur_at_risk}</td><td>{r.eur_tail ?? "—"}</td><td>{r.hazard}</td>
                <td>{r.action} <span className="small">({r.simulated}, {r.robustness})</span></td><td>{r.owner}</td>
                <td>{r.decide_by ?? "—"}</td><td>{r.trigger}</td><td><EvidenceChips evidence={r.evidence} /></td>
                <td>{r.status}{r.decided_by ? ` by ${r.decided_by}` : ""}{r.reason ? `: ${r.reason}` : ""}</td>
                <td><button onClick={() => openDecision(r.row_id)}>Decide</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
      {open ? <DecisionDialog row={open} onClose={() => openDecision(null)} /> : null}
    </Panel>
  );
}
