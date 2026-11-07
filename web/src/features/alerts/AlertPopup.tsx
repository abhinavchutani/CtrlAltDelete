import { useActiveScenario, useOptions } from "../../api/hooks";
import { leverLabel, withLever } from "../../domain";
import { useStore } from "../../state/store";
import { EvidenceChips } from "../ask/EvidenceChips";

export function AlertPopup() {
  const { selectedAlert: a, selectAlert, runSpec } = useStore();
  const sim = useActiveScenario();
  const options = useOptions(a?.hazard ?? null, a?.crop ?? null);
  if (!a) return null;
  const tryIt = () => sim.data && a.suggested_lever && runSpec(withLever(sim.data.spec, a.suggested_lever));
  return (
    <aside className="popup" aria-label="alert">
      <div className="row"><strong className={`sev-${a.severity}`}>{a.severity}</strong> <span>{a.year}{a.month ? `-${String(a.month).padStart(2, "0")}` : ""}</span>
        <button onClick={() => selectAlert(null)} aria-label="close">×</button></div>
      <h4>{a.title}</h4>
      <p>{a.why}</p>
      <p>€ at risk: <strong>{a.eur_at_risk ?? "—"}</strong> {a.hazard ? `· hazard ${a.hazard}` : ""}</p>
      {a.suggested_lever ? (
        <p>Suggested: {leverLabel(a.suggested_lever)} <button onClick={tryIt}>Try it</button></p>
      ) : null}
      {options.data?.length ? (
        <details><summary>Options for {a.hazard} ({options.data.length})</summary>
          <ul>{options.data.map((o) => <li key={o.option_id}>{o.option_id} {o.option} · {o.window} · {o.simulated}{o.reviewed_by ? "" : " · not yet reviewed"}</li>)}</ul>
        </details>
      ) : null}
      <EvidenceChips evidence={a.evidence ?? []} />
    </aside>
  );
}
