import { useScenarios } from "../../api/hooks";
import { useStore } from "../../state/store";
import { Status } from "../../components/Status";

export function ScenarioPicker() {
  const presets = useScenarios();
  const { scenarioId, customSpec, pickPreset } = useStore();
  return (
    <label className="row">
      Scenario
      <select value={customSpec ? "" : scenarioId} onChange={(e) => e.target.value && pickPreset(e.target.value)}>
        {customSpec ? <option value="">custom: {customSpec.label ?? "your idea"}</option> : null}
        {(presets.data ?? []).map((p) => <option key={p.scenario_id} value={p.scenario_id}>{p.label}</option>)}
      </select>
      <Status loading={presets.isLoading} error={presets.error} />
    </label>
  );
}
