// "Upcoming season": two lines about next season. Line 1 is the crops (harvest vs the 1991–2020 normal per region ×
// crop, from /api/radar/outlook); line 2 is rain at pea flowering (June, /api/weather/months). Both on the chosen
// climate path: one plausible weather path, not a forecast (the widget says "one weather path").
import { useMonths } from "../api/hooks";
import type { Climate, Contract, Status } from "../api/types";
import { REGION_NAME, StatusMark } from "../components/ui";

const CROP: Record<string, string> = { pea: "Pea", potato: "Potato", carrot: "Carrot", spinach: "Spinach", turnip_rape: "Turnip rape" };
const FLOWERING = 6;
const sign = (n: number) => (n > 0 ? `+${n}` : n < 0 ? `−${Math.abs(n)}` : "±0");
const yieldStatus = (pct: number): Status => (pct <= -20 ? "risk" : pct <= -10 ? "watch" : "ok");
const rainStatus = (pct: number): Status => (pct >= -10 ? "ok" : pct >= -25 ? "watch" : "risk");
const name = (c: Contract) => `${CROP[c.crop] ?? c.crop} ${REGION_NAME[c.region]}`;

export function SeasonHighlights({ year, climate, contracts }: { year: number; climate: Climate; contracts: Contract[] }) {
  const fi = useMonths("FI_SW", year, climate);
  const se = useMonths("SE_SKANE", year, climate);
  const june = [
    { region: "FI_SW" as const, m: fi.data?.months.find((m) => m.month === FLOWERING) },
    { region: "SE_SKANE" as const, m: se.data?.months.find((m) => m.month === FLOWERING) },
  ].filter((x) => x.m).sort((a, b) => a.m!.precip_anom_pct - b.m!.precip_anom_pct);
  const sorted = [...contracts].sort((a, b) => a.change_pct - b.change_pct);
  const worst = sorted[0], best = sorted[sorted.length - 1];
  const ys = worst ? yieldStatus(worst.change_pct) : "ok";
  const dry = june[0];
  const rs = dry?.m ? rainStatus(dry.m.precip_anom_pct) : "ok";
  return (
    <ul className="highlights">
      {worst ? (
        <li><StatusMark status={ys} size={14} />
          <span>{ys === "ok"
            ? <>All {contracts.length} crops near normal; best <b>{name(best)} {sign(best.change_pct)}%</b></>
            : <><b>{name(worst)} {sign(worst.change_pct)}%</b> vs normal yield</>}</span></li>
      ) : null}
      {dry?.m ? (
        <li><StatusMark status={rs} size={14} />
          <span>{rs === "ok"
            ? <>June rain at pea flowering <b>near normal</b></>
            : <>June rain {REGION_NAME[dry.region]} <b>{sign(dry.m.precip_anom_pct)}%</b> at pea flowering</>}</span></li>
      ) : null}
    </ul>
  );
}
