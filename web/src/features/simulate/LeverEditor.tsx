import { useState } from "react";
import { useActiveScenario } from "../../api/hooks";
import { withLever } from "../../domain";
import { useStore } from "../../state/store";
import { DEFAULT_FORM, LEVER_TYPES, RANGE, defaultValue, toLever, type LeverForm, type LeverType } from "./leverForm";

const CROPS = ["pea", "potato", "carrot", "spinach", "turnip_rape", "wheat", "barley", "oats"];

export function LeverEditor() {
  const [f, setF] = useState<LeverForm>(DEFAULT_FORM);
  const sim = useActiveScenario();
  const runSpec = useStore((s) => s.runSpec);
  const range = RANGE[f.type];
  const set = (p: Partial<LeverForm>) => setF({ ...f, ...p });
  return (
    <form className="row" aria-label="add a lever" onSubmit={(e) => { e.preventDefault(); if (sim.data) runSpec(withLever(sim.data.spec, toLever(f))); }}>
      <select value={f.type} onChange={(e) => { const t = e.target.value as LeverType; set({ type: t, value: defaultValue(t) }); }}>
        {LEVER_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
      </select>
      {f.type === "irrigate" || f.type === "earlier_sowing" || f.type === "crop_area" ? (
        <select value={f.crop} onChange={(e) => set({ crop: e.target.value })}>
          {(f.type === "irrigate" ? ["pea", "potato"] : f.type === "earlier_sowing" ? ["all", ...CROPS] : CROPS).map((c) => <option key={c}>{c}</option>)}
        </select>
      ) : null}
      {f.type === "irrigate" ? (
        <select value={f.target} onChange={(e) => set({ target: e.target.value as LeverForm["target"] })}>
          <option value="drought_exposed">drought-exposed</option><option value="all">all</option>
        </select>
      ) : null}
      {f.type === "crop_area" ? (
        <select value={f.region} onChange={(e) => set({ region: e.target.value as LeverForm["region"] })}><option>FI_SW</option><option>SE_SKANE</option></select>
      ) : null}
      {f.type === "heat_tolerant_variety" ? (
        <label>from <input type="number" min={2027} max={2060} value={f.fromYear} onChange={(e) => set({ fromYear: Number(e.target.value) })} /></label>
      ) : null}
      {range ? (
        <label>{range.label} <input type="number" min={range.min} max={range.max} step={range.step} value={f.value} onChange={(e) => set({ value: Number(e.target.value) })} /></label>
      ) : null}
      <button type="submit" disabled={!sim.data}>Add and run</button>
    </form>
  );
}
