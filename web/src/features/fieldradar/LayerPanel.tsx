import { useActiveScenario, useScenarios } from "../../api/hooks";
import { useStore, type ColorBy, type View } from "../../state/store";
import { BANDS, RISK, scale } from "./useFieldData";

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
const ramp = `linear-gradient(90deg, ${[0, 0.5, 1].map((t) => rgb(scale(t))).join(", ")})`;

/** What the colours mean for the active layer. Classes and band names come from the API; no thresholds typed here. */
function Legend({ colorBy }: { colorBy: ColorBy }) {
  const swatches = (items: [number[], string][]) => (
    <ul className="legend-swatches">
      {items.map(([c, label]) => <li key={label}><span className="legend-dot" style={{ background: rgb(c) }} />{label}</li>)}
    </ul>
  );
  const body = {
    health: <>
      {swatches([[RISK.low, "On track"], [RISK.medium, "Watch"], [RISK.high, "Bad year"]])}
      <p>The farm's yield vs its 1991–2020 average, in the API's ok / watch / bad classes.</p>
    </>,
    risk: <>
      <div className="legend-bands">
        {BANDS.map((b, i) => <span key={b} style={{ background: rgb(scale(i / (BANDS.length - 1))) }} title={b} />)}
      </div>
      <div className="legend-ends"><span>{BANDS[0]}</span><span>{BANDS[BANDS.length - 1]}</span></div>
      <p>€ at risk for the parcel's 2025 crop in its region. Contract crops only.</p>
    </>,
    drought: <>
      <div className="legend-ramp" style={{ background: ramp }} />
      <div className="legend-ends"><span>Moist</span><span>Very dry</span></div>
      <p>Drought at flowering in the nearest weather cell.</p>
    </>,
    heat: <>
      <div className="legend-ramp" style={{ background: ramp }} />
      <div className="legend-ends"><span>Few hot days</span><span>Many</span></div>
      <p>Hot days at pea flowering in the nearest weather cell.</p>
    </>,
  }[colorBy];
  return (
    <div className="legend" aria-label="Legend">
      {body}
      <p className="legend-none"><span className="legend-outline" /> Outline only: no value for this layer</p>
    </div>
  );
}

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
      <Legend colorBy={colorBy} />
      <div className="jump-row">
        {Object.entries(JUMP).map(([name, v]) => <button key={name} className="chip" onClick={() => setView(v)}>{name}</button>)}
      </div>
    </section>
  );
}
