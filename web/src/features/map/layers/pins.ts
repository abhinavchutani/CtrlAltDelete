import { IconLayer, ScatterplotLayer } from "@deck.gl/layers";
import type { AlertPin } from "../../fieldradar/useFieldData";

// A map pin drawn as SVG (white outline + severity fill), anchored at its tip.
const W = 64, H = 84;
const pinSvg = (fill: string) =>
  `data:image/svg+xml;charset=utf-8,${encodeURIComponent(
    `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 64 84">` +
    `<path d="M32 4C18.7 4 8 14.7 8 28c0 18 24 50 24 50s24-32 24-50C56 14.7 45.3 4 32 4z" fill="${fill}" fill-opacity="0.85" stroke="#fff" stroke-width="4"/>` +
    `<circle cx="32" cy="28" r="8" fill="#fff"/></svg>`,
  )}`;
const ICON = {
  critical: { url: pinSvg("#de6846"), id: "pin-critical", width: W, height: H, anchorY: H - 4 },
  notable: { url: pinSvg("#e2a842"), id: "pin-notable", width: W, height: H, anchorY: H - 4 },
};
const HALO: Record<string, [number, number, number]> = { critical: [222, 104, 70], notable: [226, 168, 66] };
const sev = (p: AlertPin) => (p.alerts[0].severity === "critical" ? "critical" : "notable");

/** The year's alerts as pins on their worst-hit parcel, with a soft halo; click → the alert card. */
export function alertPinLayers(pins: AlertPin[], selectedAlertId: string | null) {
  const halo = new ScatterplotLayer<AlertPin>({
    id: "alert-halo",
    data: pins,
    getPosition: (p) => p.position,
    getRadius: (p) => (p.alerts.some((a) => a.id === selectedAlertId) ? 26 : 18),
    radiusUnits: "pixels",
    getFillColor: (p) => [...HALO[sev(p)], 45],
    getLineColor: (p) => [...HALO[sev(p)], 160],
    stroked: true,
    lineWidthUnits: "pixels",
    getLineWidth: 1.5,
    updateTriggers: { getRadius: [selectedAlertId] },
  });
  const icons = new IconLayer<AlertPin>({
    id: "alert-pins",
    data: pins,
    getPosition: (p) => p.position,
    getIcon: (p) => ICON[sev(p)],
    getSize: (p) => (p.alerts.some((a) => a.id === selectedAlertId) ? 46 : 36),
    sizeUnits: "pixels",
    pickable: true,
    updateTriggers: { getSize: [selectedAlertId] },
  });
  return [halo, icons];
}
