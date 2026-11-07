// The glass widget shell (Layer 1): one button that opens its Layer 2. A widget never lists.
import type { MouseEvent, ReactNode } from "react";

export function Widget({ size = "S", label, icon, right, cta, onOpen, children, tour }: {
  size?: "S" | "M" | "L"; label: string; icon: ReactNode; right?: ReactNode; cta: string;
  onOpen: (e: MouseEvent) => void; children: ReactNode; tour?: string;
}) {
  return (
    <button type="button" className={`w glass ${size}`} onClick={onOpen} data-tour={tour}>
      <span className="w-label">{icon}{label}{right ? <span className="right">{right}</span> : null}</span>
      {children}
      <span className="w-cta">{cta} ›</span>
    </button>
  );
}

export const skel = (w: number | string, h: number) =>
  <span className="skeleton" style={{ width: w, height: h, display: "block" }} />;

export const rect = (e: MouseEvent) => (e.currentTarget as HTMLElement).getBoundingClientRect();
