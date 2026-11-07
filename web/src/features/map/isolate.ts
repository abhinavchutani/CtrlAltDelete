import { useCallback, useRef } from "react";

// Gestures that start on a card must not move the map (drag-pan, scroll-zoom, double-click zoom). Clicks are NOT
// stopped: React listens at the page root, above MapLibre's container, so stopping them would kill every button.
// Instead a card click is stamped, and MapView ignores the map click it also produces.
const BLOCK = ["mousedown", "pointerdown", "touchstart", "wheel", "dblclick", "contextmenu"];
let lastCardClick = 0;

/** True while handling a click that began on a card (the map's own click handler runs in the same dispatch). */
export const cardClickedJustNow = () => performance.now() - lastCardClick < 80;

/** For cards that sit on the map (react-map-gl Markers). Native listeners, attached through a callback ref so a
 *  card that appears later still gets them. */
export function useIsolate<T extends HTMLElement>() {
  const cleanup = useRef<(() => void) | null>(null);
  return useCallback((el: T | null) => {
    cleanup.current?.();
    cleanup.current = null;
    if (!el) return;
    const stop = (e: Event) => e.stopPropagation();
    const stamp = () => { lastCardClick = performance.now(); };
    for (const k of BLOCK) el.addEventListener(k, stop);
    el.addEventListener("click", stamp);
    cleanup.current = () => {
      for (const k of BLOCK) el.removeEventListener(k, stop);
      el.removeEventListener("click", stamp);
    };
  }, []);
}
