import type { Region } from "../../api/types";
import { useStore } from "../../state/store";
import { Bell, Close } from "../../components/Icons";
import { bandLevel, healthLevel, RISK, useFieldData, type Level } from "./useFieldData";

const LEVEL_TEXT: Record<Level, string> = { low: "Low risk", medium: "Medium risk", high: "High risk" };
const rgb = (c: number[], a = 1) => `rgba(${c.join(",")},${a})`;

/** The clicked field: its outline, € band, yield change and risk level, all from the API for the chosen year. */
export function ParcelCard() {
  const { selectedParcel: p, selectParcel, watched, toggleWatch, year } = useStore();
  const d = useFieldData();
  if (!p) return null;
  const change = d.farmChange.get(p.farm_id);
  const region = d.farmRegion.get(p.farm_id) as Region | undefined;
  const band = region ? d.regionBand.get(region) : undefined;
  const level: Level = healthLevel(change) === "high" || bandLevel(band) === "high" ? "high"
    : healthLevel(change) === "medium" || bandLevel(band) === "medium" ? "medium" : "low";
  const color = RISK[level];
  // mini outline, normalised into a 100×100 box
  const xs = p.ring.map((q) => q[0]), ys = p.ring.map((q) => q[1]);
  const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
  const s = 80 / Math.max(x1 - x0, y1 - y0, 1e-9);
  const pts = p.ring.map(([x, y]) => `${10 + (x - x0) * s},${90 - (y - y0) * s}`).join(" ");
  const isWatched = watched.includes(p.parcel_id);
  return (
    <section className="glass parcel-card" aria-label={`Parcel ${p.parcel_id}`}>
      <button className="icon-btn card-close" onClick={() => selectParcel(null)} aria-label="Close"><Close size={16} /></button>
      <div className="parcel-top">
        <svg viewBox="0 0 100 100" className="parcel-thumb" aria-hidden="true">
          <polygon points={pts} fill={rgb(color, 0.45)} stroke={rgb(color)} strokeWidth={2} />
        </svg>
        <div className="parcel-id">
          <div className="parcel-title">Parcel {p.parcel_id.split("-P")[1] ?? p.parcel_id}</div>
          <div className="muted small">Farm {p.farm_id} · {p.area_ha.toFixed(1)} ha · {region ?? "…"}</div>
          <button className={`chip watch ${isWatched ? "on" : ""}`} onClick={() => toggleWatch(p.parcel_id)}>
            <Bell size={16} /> {isWatched ? "Watching" : "Watch"}
          </button>
        </div>
      </div>
      <div className="parcel-bottom">
        <div>
          <div className="big">{band ?? "—"}</div>
          <div className="muted small">€ at risk, {region === "SE_SKANE" ? "Skåne" : "SW Finland"} pea, {year}</div>
        </div>
        <div className="divider" />
        <div>
          <span className="level" style={{ color: rgb(color), borderColor: rgb(color, 0.6), background: rgb(color, 0.12) }}>
            {LEVEL_TEXT[level]}
          </span>
          <div className="muted small">yield {change === undefined ? "—" : `${change > 0 ? "+" : ""}${change.toFixed(0)} %`} vs 1991–2020</div>
        </div>
      </div>
    </section>
  );
}
