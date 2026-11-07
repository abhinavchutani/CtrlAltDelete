import { useEffect } from "react";
import { Close } from "../../components/Icons";
import { useSearch } from "../../state/search";
import { PlansTable } from "./PlansTable";

/** Every plan the plan finder simulated, over the map. */
export function PlansModal({ onClose }: { onClose: () => void }) {
  const s = useSearch();
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="assistant-backdrop" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <section className="assistant plans-modal glass" role="dialog" aria-modal="true" aria-label="All simulated plans">
        <header className="assistant-head">
          <div className="assistant-title">{Object.keys(s.candidates).length} simulated plans, best first</div>
          <span className="muted small">Same engine, weather path and 2025 field mix for every plan</span>
          <button className="icon-btn" onClick={onClose} aria-label="Close"><Close size={18} /></button>
        </header>
        <div className="chat-body"><PlansTable /></div>
      </section>
    </div>
  );
}
