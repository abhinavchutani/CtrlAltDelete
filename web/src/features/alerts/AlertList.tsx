import { useActiveScenario } from "../../api/hooks";
import { HAZARD_LABEL } from "../../domain";
import { useStore } from "../../state/store";
import { Panel, Status } from "../../components/Status";

export function AlertList() {
  const sim = useActiveScenario();
  const selectAlert = useStore((s) => s.selectAlert);
  const alerts = sim.data?.alerts ?? [];
  return (
    <Panel title={`Alerts (${alerts.length})`}>
      <Status loading={sim.isLoading} error={sim.error} empty={!sim.isLoading && alerts.length === 0} emptyText="No critical or notable alerts on this path." />
      <ul>
        {alerts.map((a) => (
          <li key={a.id}>
            <button onClick={() => selectAlert(a)}>
              <span className={`sev-${a.severity}`}>{a.severity}</span> {a.year} · {a.title} · {a.eur_at_risk ?? "—"}
              {a.hazard ? ` · ${a.hazard} ${HAZARD_LABEL[a.hazard]}` : ""}
            </button>
          </li>
        ))}
      </ul>
    </Panel>
  );
}
