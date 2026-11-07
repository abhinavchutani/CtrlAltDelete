import { useActiveScenario, useScenarios } from "../../api/hooks";
import { useStore, type ColorBy, type View } from "../../state/store";
import { RISK } from "./useFieldData";

const LAYERS: { key: ColorBy; label: string; dot: keyof typeof RISK }[] = [
  { key: "health", label: "Farm health", dot: "low" },
  { key: "risk", label: "€ risk", dot: "medium" },
  { key: "drought", label: "Drought", dot: "medium" },
  { key: "heat", label: "Heat", dot: "high" },
];
const JUMP: Record<string, View> = {
  Skåne: { longitude: 13.33, latitude: 55.85, zoom: 12.3, pitch: 0, bearing: 0 },
  "SW Finland": { longitude: 22.2, latitude: 61.11, zoom: 12.3, pitch: 0, bearing: 0 },
};
const rgb = (c: number[]) => `rgb(${c.join(",")})`;

/** Scenario, year and which layer colours the fields (one at a time, so the colours always mean one thing). */
export function LayerPanel() {
  const presets = useScenarios();
  const sim = useActiveScenario();
  const { scenarioId, customSpec, pickPreset, year, setYear, colorBy, setColorBy, setView } = useStore();
  const years = sim.data?.years ?? [year];
  return (
    <section className="glass layer-panel" aria-label="Scenario and layers">
      <label className="field-label" htmlFor="scenario">Scenario</label>
      <select id="scenario" className="select" value={customSpec ? "" : scenarioId}
        onChange={(e) => e.target.value && pickPreset(e.target.value)}>
        {customSpec ? <option value="">Your idea: {customSpec.label ?? "custom"}</option> : null}
        {(presets.data ?? []).map((p) => <option key={p.scenario_id} value={p.scenario_id}>{p.label}</option>)}
      </select>
      <label className="field-label" htmlFor="year">Year {year}</label>
      <select id="year" className="select" value={year} onChange={(e) => setYear(Number(e.target.value))}>
        {years.map((y) => <option key={y} value={y}>Year {y}</option>)}
      </select>
      <div className="field-label">Colour fields by</div>
      <ul className="layer-list">
        {LAYERS.map((l) => (
          <li key={l.key}>
            <span className="dot" style={{ background: rgb(RISK[l.dot]) }} />
            <span>{l.label}</span>
            <button role="switch" aria-checked={colorBy === l.key} className={`switch ${colorBy === l.key ? "on" : ""}`}
              onClick={() => setColorBy(l.key)} aria-label={l.label} />
          </li>
        ))}
      </ul>
      <div className="jump-row">
        {Object.entries(JUMP).map(([name, v]) => <button key={name} className="chip" onClick={() => setView(v)}>{name}</button>)}
      </div>
    </section>
  );
}
