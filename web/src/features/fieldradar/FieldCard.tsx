// Layer 2 on the map: the clicked field. Status, yield vs normal, up to two weather reasons, and its receipt.
import { useState } from "react";
import { Marker } from "react-map-gl/maplibre";
import type { Status } from "../../api/types";
import { Close } from "../../components/Icons";
import { REGION_NAME, SourceChip, STATUS_LABEL, StatusMark } from "../../components/ui";
import { useStore } from "../../state/store";
import { useIsolate } from "../map/isolate";
import { centroid, LENS_RULE, useFieldData } from "./useFieldData";

const sign = (n: number, d = 0) => (n > 0 ? "+" : n < 0 ? "−" : "") + Math.abs(n).toFixed(d);

export function FieldCard() {
  const p = useStore((s) => s.selectedParcel);
  const selectParcel = useStore((s) => s.selectParcel);
  const year = useStore((s) => s.year);
  const prefill = useStore((s) => s.prefill);
  const d = useFieldData();
  const ref = useIsolate<HTMLElement>();
  const [receipt, setReceipt] = useState(false);
  if (!p) return null;
  const [lon, lat] = centroid(p.ring);
  const status = d.farmRisk.get(p.farm_id) ?? null;
  const change = d.farmChange.get(p.farm_id);
  const region = d.farmRegion.get(p.farm_id);
  const cell = d.cellOf(p.farm_id);
  const reasons: { status: Status; text: string }[] = [];
  if (cell) {
    reasons.push({ status: LENS_RULE.rain.status(cell), text: `Rain this season ${sign(cell.precip_anom_pct)}% vs normal` });
    const heat = LENS_RULE.heat.status(cell);
    reasons.push(cell.hot_days_flowering > 0
      ? { status: heat, text: `${cell.hot_days_flowering} hot day${cell.hot_days_flowering === 1 ? "" : "s"} (≥ 27 °C) at flowering` }
      : { status: heat, text: `${sign(cell.tmax_anom_c, 1)} °C warmer than normal` });
  }
  reasons.sort((a, b) => ["risk", "watch", "ok"].indexOf(a.status) - ["risk", "watch", "ok"].indexOf(b.status));
  const field = p.parcel_id.split("-P")[1]?.replace(/^0+/, "") ?? p.parcel_id;
  const crop = (p.crop ?? "unknown crop").replace(/_/g, " ");
  return (
    <Marker longitude={lon} latitude={lat} anchor="left" offset={[18, 0]} style={{ zIndex: 6 }}>
      <section className="field-card glass glass-strong" ref={ref} aria-label={`Farm ${p.farm_id}, field ${field}`}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          {status ? <span className={`status-pill ${status}`}><StatusMark status={status} size={12} /> {STATUS_LABEL[status]}</span> : <span />}
          <button type="button" className="icon-btn sm" onClick={() => selectParcel(null)} aria-label="Close field card"><Close size={16} /></button>
        </div>
        <h3>Farm {p.farm_id} · Field {field}</h3>
        <div className="muted">{crop.charAt(0).toUpperCase() + crop.slice(1)} · {year} season{region ? ` · ${REGION_NAME[region]}` : ""}</div>
        <div style={{ display: "flex", alignItems: "baseline", gap: 12, marginTop: 14 }}>
          <span className={`fig ${status === "risk" ? "fig-risk" : status === "watch" ? "fig-harvest" : "fig-leaf"}`}>
            {change === undefined ? "—" : `${sign(change)}%`}</span>
          <span className="muted">farm yield vs its normal</span>
        </div>
        <ul className="reasons">
          {reasons.slice(0, 2).map((r) => <li key={r.text}><StatusMark status={r.status} size={13} />{r.text}</li>)}
        </ul>
        {receipt ? (
          <div className="chips" style={{ marginBottom: 12 }}>
            <SourceChip s={{ kind: "model", label: "Yield model", detail: `farm × ${year}` }} />
            {cell ? <SourceChip s={{ kind: "data", label: `Weather cell ${cell.cell_id}`, detail: year <= 2026 ? "observed" : "climate path" }} /> : null}
            <SourceChip s={{ kind: "data", label: "Fields & crops", detail: "2025 crop mix" }} />
          </div>
        ) : null}
        <div className="links">
          <button type="button" className="link" aria-expanded={receipt} onClick={() => setReceipt(!receipt)}>How do we know?</button>
          <button type="button" className="link tacit" onClick={() => prefill("teach", `About farm ${p.farm_id}: `)}>Ask the field officer</button>
        </div>
      </section>
    </Marker>
  );
}
