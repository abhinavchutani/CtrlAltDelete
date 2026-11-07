import { useScenarios } from "../../api/hooks";
import { REGION_VIEW, useStore, type ColorBy } from "../../state/store";
import { RISK, scale } from "./useFieldData";

const rgb = (c: number[]) => `rgb(${c.join(",")})`;
const LAYERS: { key: ColorBy; label: string; hint: string }[] = [
  { key: "health", label: "Crop health", hint: "How each farm's yield compares with its 1991–2020 average." },
  { key: "drought", label: "Drought", hint: "How dry it is when the crop flowers." },
  { key: "heat", label: "Heat", hint: "Hot days while the crop flowers." },
];
const ramp = `linear-gradient(90deg, ${[0, 0.5, 1].map((t) => rgb(scale(t))).join(", ")})`;

/** Which future, and what the colours on the map mean. One layer at a time, so a colour always means one thing. */
export function ViewPanel() {
  const presets = useScenarios();
  const scenarioId = useStore((s) => s.scenarioId);
  const customSpec = useStore((s) => s.customSpec);
  const pickPreset = useStore((s) => s.pickPreset);
  const colorBy = useStore((s) => s.colorBy);
  const setColorBy = useStore((s) => s.setColorBy);
  const flyTo = useStore((s) => s.flyTo);
  const weatherFx = useStore((s) => s.weatherFx);
  const setWeatherFx = useStore((s) => s.setWeatherFx);
  const active = LAYERS.find((l) => l.key === colorBy)!;
  return (
    <section className="glass side-panel view-panel" aria-label="View" data-tour="view">
      <h2 className="panel-title">View</h2>
      <select className="select" aria-label="Future" value={customSpec ? "" : scenarioId}
        onChange={(e) => e.target.value && pickPreset(e.target.value)}>
        {customSpec ? <option value="">Your change: {customSpec.label ?? "custom"}</option> : null}
        {(presets.data ?? []).map((p) => <option key={p.scenario_id} value={p.scenario_id}>{p.label}</option>)}
      </select>
      <div className="seg" role="radiogroup" aria-label="Colour the map by">
        {LAYERS.map((l) => (
          <button key={l.key} role="radio" aria-checked={colorBy === l.key} className={`seg-btn ${colorBy === l.key ? "on" : ""}`}
            onClick={() => setColorBy(l.key)}>{l.label}</button>
        ))}
      </div>
      <p className="hint">{active.hint}</p>
      <div className="legend">
        {colorBy === "health" ? (
          <ul className="legend-swatches">
            <li><span className="legend-dot" style={{ background: rgb(RISK.low) }} />On track</li>
            <li><span className="legend-dot" style={{ background: rgb(RISK.medium) }} />Watch</li>
            <li><span className="legend-dot" style={{ background: rgb(RISK.high) }} />Bad year</li>
          </ul>
        ) : (
          <>
            <div className="legend-ramp" style={{ background: ramp }} />
            <div className="legend-ends"><span>{colorBy === "drought" ? "Moist" : "Few hot days"}</span><span>{colorBy === "drought" ? "Very dry" : "Many"}</span></div>
          </>
        )}
      </div>
      <button role="switch" aria-checked={weatherFx} className={`seg-btn fx ${weatherFx ? "on" : ""}`} onClick={() => setWeatherFx(!weatherFx)}>
        Weather on the map <span className="muted small">rain · heat · drought</span>
      </button>
      <div className="jump-row">
        <span className="muted small">Go to</span>
        <button className="chip" onClick={() => flyTo(REGION_VIEW.SE_SKANE)}>Skåne</button>
        <button className="chip" onClick={() => flyTo(REGION_VIEW.FI_SW)}>SW Finland</button>
      </div>
    </section>
  );
}
