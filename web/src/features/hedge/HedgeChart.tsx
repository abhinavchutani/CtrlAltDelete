import { useActiveScenario, useHedge } from "../../api/hooks";
import { EUR_BANDS } from "../../domain";
import { Panel, Status } from "../../components/Status";
import { H, PAD, W, path, xOf, yOf } from "./hedgeGeometry";

export function HedgeChart() {
  const sim = useActiveScenario();
  const hedge = useHedge(sim.data?.spec.climate ?? "ssp245");
  const pts = hedge.data?.points ?? [];
  const now = pts.find((p) => p.is_now), best = pts.find((p) => p.is_best);
  return (
    <Panel title="Sourcing hedge (pea, Finland share)">
      <Status loading={hedge.isLoading} error={hedge.error} empty={!hedge.isLoading && !pts.length} />
      {pts.length ? (
        <svg className="chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="hedge frontier">
          <line className="axis" x1={PAD} x2={W - PAD} y1={H - PAD} y2={H - PAD} />
          {EUR_BANDS.map((b, i) => <text key={b} x={0} y={yOf(i) + 3}>{b}</text>)}
          {[0, 0.5, 1].map((s) => <text key={s} x={xOf(s) - 8} y={H - PAD + 14}>{s * 100}%</text>)}
          <path className="line-expected" d={path(pts, "expected_loss")} />
          <path className="line-tail" d={path(pts, "tail_loss")} />
          {now ? <circle className="now" cx={xOf(now.fi_share)} cy={H - PAD} r={5}><title>today</title></circle> : null}
          {best ? <circle className="best" cx={xOf(best.fi_share)} cy={H - PAD} r={5}><title>best</title></circle> : null}
        </svg>
      ) : null}
      <p className="small">solid: expected loss · dashed: 1-in-10-year loss · grey: today{now ? ` (${Math.round(now.fi_share * 100)} %)` : ""} · green: best{best ? ` (${Math.round(best.fi_share * 100)} %)` : ""}</p>
      {hedge.data ? <p>{hedge.data.why}</p> : null}
    </Panel>
  );
}
