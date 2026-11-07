import { useActiveScenario } from "../../api/hooks";
import { specChips, withoutLever, leverLabel } from "../../domain";
import { useStore } from "../../state/store";
import { Panel } from "../../components/Status";

/** What we heard (pending, needs a confirm) and what is running now (levers removable). */
export function SpecChips() {
  const { pendingSpec, heard, problems, runSpec, setPending } = useStore();
  const sim = useActiveScenario();
  const spec = sim.data?.spec;
  return (
    <Panel title="Scenario">
      {pendingSpec ? (
        <div aria-label="what we heard">
          <div className="row">Heard: {(heard.length ? heard : specChips(pendingSpec)).map((c) => <span key={c} className="chip">{c}</span>)}</div>
          {problems.length ? <div className="row">{problems.map((p) => <span key={p} className="chip problem">{p}</span>)}</div> : null}
          <div className="row">
            <button onClick={() => runSpec(pendingSpec)}>Confirm and run</button>
            <button onClick={() => setPending(null)}>Cancel</button>
          </div>
        </div>
      ) : null}
      {spec ? (
        <div className="row" aria-label="running">
          {specChips({ ...spec, levers: [] }).map((c) => <span key={c} className="chip">{c}</span>)}
          {(spec.levers ?? []).map((l, i) => (
            <span key={i} className="chip">{leverLabel(l)} <button aria-label="remove lever" onClick={() => runSpec(withoutLever(spec, i))}>×</button></span>
          ))}
          {sim.isFetching ? <span className="muted">running…</span> : null}
        </div>
      ) : null}
    </Panel>
  );
}
