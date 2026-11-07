import type { Alert } from "../../api/types";

export function EventDot({ alert, x, y, onSelect }: { alert: Alert; x: number; y: number; onSelect: (a: Alert) => void }) {
  return (
    <circle cx={x} cy={y} r={alert.severity === "critical" ? 6 : 4} className={`dot-${alert.severity}`} onClick={() => onSelect(alert)}>
      <title>{`${alert.year}: ${alert.title} (${alert.eur_at_risk ?? "€ n/a"})`}</title>
    </circle>
  );
}
