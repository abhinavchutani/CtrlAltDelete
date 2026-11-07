import { useActiveScenario } from "../../api/hooks";
import { specChips } from "../../domain";
import { useStore } from "../../state/store";
import { Panel, Status } from "../../components/Status";

export function Meters() {
  const sim = useActiveScenario();
  const runSpec = useStore((s) => s.runSpec);
  const m = sim.data?.meters;
  const better = sim.data?.better;
  return (
    <Panel title="Meters">
      <Status loading={sim.isLoading} error={sim.error} />
      {m ? (
        <dl>
          <dt>€ at risk per year</dt><dd>{m.eur_at_risk_per_year}</dd>
          <dt>vs current plan</dt><dd>{m.vs_current_plan}</dd>
          <dt>CO2e (replacement imports)</dt><dd>{m.co2e_direction}</dd>
          <dt>confidence</dt><dd>{m.confidence}<ul className="small">{m.confidence_why.map((w) => <li key={w}>{w}</li>)}</ul></dd>
        </dl>
      ) : null}
      {better ? (
        <div className="panel" aria-label="better option">
          <strong>Better option: saves {better.saves}</strong>
          <p className="small">{better.why}</p>
          <div className="row">{specChips(better.spec).map((c) => <span key={c} className="chip">{c}</span>)}</div>
          <button onClick={() => runSpec(better.spec)}>Run it</button>
        </div>
      ) : null}
    </Panel>
  );
}
