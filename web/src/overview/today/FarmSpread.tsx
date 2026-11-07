// ④ How the farms are spread: each farm's dryness so far as a percentile of its own field's normal, per region.
// The bar runs from the 10th to the 90th farm, the tick is the middle farm; the shaded end is ≥ 90th (bad-year zone).
import type { FarmSpread as Spread } from "../../api/types";
import { REGION_NAME } from "../../components/ui";
import { ordinal, pct, useWidth } from "./shared";

const H = 30;

function Bar({ f }: { f: Spread }) {
  const [ref, W] = useWidth<HTMLDivElement>();
  const x = (p: number) => 6 + (p / 100) * (W - 12);
  return (
    <div ref={ref} className="spread-bar">
      <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} role="img"
        aria-label={`${REGION_NAME[f.region]}: middle farm at the ${ordinal(f.p50)} percentile, ${pct(f.share_ge_90)} of ${f.farms} farms at the 90th or drier`}>
        <rect x={x(90)} y={0} width={x(100) - x(90)} height={H} fill="var(--risk-soft)" rx={4} />
        <line x1={x(0)} x2={x(100)} y1={H / 2} y2={H / 2} stroke="var(--line)" strokeWidth={2} />
        <rect x={x(f.p10)} y={H / 2 - 7} width={Math.max(4, x(f.p90) - x(f.p10))} height={14} rx={7} fill="var(--status-watch)" opacity={0.55} />
        <line x1={x(f.p50)} x2={x(f.p50)} y1={2} y2={H - 2} stroke="var(--ink)" strokeWidth={3} />
      </svg>
    </div>
  );
}

export function FarmSpread({ farms }: { farms: Spread[] }) {
  return (
    <div className="spread">
      {farms.map((f) => (
        <div key={f.region} className="spread-row">
          <span className="unusual-name">{REGION_NAME[f.region]}</span>
          <Bar f={f} />
          <span className="spread-share"><b>{pct(f.share_ge_90)}</b> ≥90th</span>
        </div>
      ))}
      <div className="unusual-axis"><span>0th</span><span>50th percentile</span><span>100th</span></div>
    </div>
  );
}

export const spreadLine = (farms: Spread[]) =>
  farms.length ? `${farms.reduce((s, f) => s + f.farms, 0)} farms, each against its own field's 1991–2020 normal` : "";
