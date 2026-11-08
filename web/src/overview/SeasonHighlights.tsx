// "Upcoming season": three headlines about next season, one at a time, each for 10 s (pause on hover or focus;
// the dots pick one). 1 = crops vs their normal yield, 2 = rain at pea flowering (June), 3 = the next bad season ahead.
// All on the chosen climate path: one plausible weather path, not a forecast.
import { useEffect, useState } from "react";
import { useMonths } from "../api/hooks";
import type { Climate, Outlook, Status } from "../api/types";
import { REGION_NAME, StatusMark } from "../components/ui";
import { typeLabel } from "./data";

const CROP: Record<string, string> = { pea: "Pea", potato: "Potato", carrot: "Carrot", spinach: "Spinach", turnip_rape: "Turnip rape" };
const FLOWERING = 6;
const ROTATE_MS = 10_000;
const sign = (n: number) => (n > 0 ? `+${n}` : n < 0 ? `−${Math.abs(n)}` : "±0");
const yieldStatus = (pct: number): Status => (pct <= -20 ? "risk" : pct <= -10 ? "watch" : "ok");
const rainStatus = (pct: number): Status => (pct >= -10 ? "ok" : pct >= -25 ? "watch" : "risk");

type Headline = { status: Status; text: React.ReactNode; label: string };

function useHeadlines(o: Outlook, climate: Climate): Headline[] {
  const fi = useMonths("FI_SW", o.next_season, climate);
  const se = useMonths("SE_SKANE", o.next_season, climate);
  const out: Headline[] = [];
  const sorted = [...o.next_contracts].sort((a, b) => a.change_pct - b.change_pct);
  const worst = sorted[0], best = sorted[sorted.length - 1];
  if (worst) {
    const s = yieldStatus(worst.change_pct);
    const nm = (c: typeof worst) => `${CROP[c.crop] ?? c.crop} ${REGION_NAME[c.region]}`;
    out.push(s === "ok"
      ? { status: s, label: "crops", text: <>All {o.next_contracts.length} crops near normal yield. Best: <b>{nm(best)} {sign(best.change_pct)}%</b></> }
      : { status: s, label: "crops", text: <><b>{nm(worst)} {sign(worst.change_pct)}%</b> below its normal yield</> });
  }
  const june = [
    { region: "FI_SW" as const, m: fi.data?.months.find((m) => m.month === FLOWERING) },
    { region: "SE_SKANE" as const, m: se.data?.months.find((m) => m.month === FLOWERING) },
  ].filter((x) => x.m).sort((a, b) => a.m!.precip_anom_pct - b.m!.precip_anom_pct)[0];
  if (june?.m) {
    const s = rainStatus(june.m.precip_anom_pct);
    out.push({ status: s, label: "flowering rain", text: s === "ok"
      ? <>Rain at pea flowering (June) <b>near normal</b> in both regions</>
      : <>June rain in {REGION_NAME[june.region]} <b>{sign(june.m.precip_anom_pct)}%</b> as peas flower</> });
  }
  const next = o.issues.filter((i) => i.year >= o.next_season).sort((a, b) => a.year - b.year)[0];
  if (next) {
    out.push({ status: next.status, label: "next bad season", text: next.year === o.next_season
      ? <><b>This season</b>: {typeLabel(next.type).toLowerCase()} in {REGION_NAME[next.region]}</>
      : <>Next bad season: <b>{next.year}</b>, {typeLabel(next.type).toLowerCase()} in {REGION_NAME[next.region]}</> });
  }
  return out;
}

export function SeasonHighlights({ o, climate }: { o: Outlook; climate: Climate }) {
  const items = useHeadlines(o, climate);
  const [i, setI] = useState(0);
  const [paused, setPaused] = useState(false);
  useEffect(() => {
    if (paused || items.length < 2) return;
    const t = setInterval(() => setI((x) => (x + 1) % items.length), ROTATE_MS);
    return () => clearInterval(t);
  }, [paused, items.length]);
  const h = items[i % Math.max(1, items.length)];
  return (
    <div className="hl" onMouseEnter={() => setPaused(true)} onMouseLeave={() => setPaused(false)}
      onFocus={() => setPaused(true)} onBlur={() => setPaused(false)}>
      {h ? (
        <p key={i} className="hl-text" aria-live="polite"><StatusMark status={h.status} size={16} /><span>{h.text}</span></p>
      ) : <span className="skeleton" style={{ height: 60, display: "block" }} />}
      <div className="hl-dots" role="tablist" aria-label="Headlines">
        {items.map((x, k) => (
          <button key={x.label} type="button" role="tab" aria-selected={k === i} aria-label={`Show headline ${k + 1}: ${x.label}`}
            className={k === i ? "on" : ""} onClick={() => setI(k)} />
        ))}
      </div>
    </div>
  );
}
