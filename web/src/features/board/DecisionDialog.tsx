import { useState } from "react";
import { useDecide } from "../../api/hooks";
import type { BoardRow, Decision } from "../../api/types";
import { Status } from "../../components/Status";

/** A human approves / edits / rejects with their typed name and a reason. Code never fills the name. */
export function DecisionDialog({ row, onClose }: { row: BoardRow; onClose: () => void }) {
  const [status, setStatus] = useState<Decision["status"]>("approved");
  const [name, setName] = useState("");
  const [reason, setReason] = useState("");
  const [action, setAction] = useState(row.action);
  const decide = useDecide();
  const ok = name.trim().length > 0 && reason.trim().length > 0;
  const submit = () =>
    decide.mutate(
      { rowId: row.row_id, decision: { status, decided_by: name.trim(), reason: reason.trim(), action: status === "edited" ? action : null } },
      { onSuccess: onClose },
    );
  return (
    <dialog open aria-label="decision">
      <h4>{row.risk}: {row.crop} {row.region}</h4>
      <div className="row">
        {(["approved", "edited", "rejected"] as const).map((s) => (
          <label key={s}><input type="radio" checked={status === s} onChange={() => setStatus(s)} /> {s}</label>
        ))}
      </div>
      {status === "edited" ? <label>Action <input value={action} onChange={(e) => setAction(e.target.value)} size={50} /></label> : null}
      <label>Your name <input value={name} onChange={(e) => setName(e.target.value)} /></label>
      <label>Reason <input value={reason} onChange={(e) => setReason(e.target.value)} size={40} /></label>
      <div className="row">
        <button disabled={!ok || decide.isPending} onClick={submit}>Save decision</button>
        <button onClick={onClose}>Cancel</button>
        <Status loading={decide.isPending} error={decide.error} />
      </div>
    </dialog>
  );
}
