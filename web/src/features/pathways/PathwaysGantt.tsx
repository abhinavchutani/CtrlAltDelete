import { useActiveScenario, usePathways } from "../../api/hooks";
import { Panel, Status } from "../../components/Status";

const W = 520, ROW = 22, LEFT = 210, START = 2026;

export function PathwaysGantt() {
  const sim = useActiveScenario();
  const pw = usePathways(sim.data?.scenario_id);
  const end = sim.data?.spec.horizon_end ?? 2060;
  const items = pw.data ?? [];
  const x = (y: number) => LEFT + ((Math.min(Math.max(y, START), end) - START) / Math.max(1, end - START)) * (W - LEFT - 10);
  return (
    <Panel title="Adaptation pathways">
      <Status loading={pw.isLoading} error={pw.error} empty={!pw.isLoading && !items.length} />
      {items.length ? (
        <svg className="chart" viewBox={`0 0 ${W} ${ROW * items.length + 20}`} role="img" aria-label="pathways">
          {items.map((p, i) => {
            const y = i * ROW + 12;
            return (
              <g key={`${p.option_id}-${p.region}-${p.climate}`}>
                <text x={0} y={y + 4}>{`${p.crop} ${p.region} ${p.climate}: ${p.option_id}`}</text>
                {p.decide_by != null && p.tipping_year != null ? (
                  <rect className="bar" x={x(p.decide_by)} y={y - 6} width={Math.max(2, x(p.tipping_year) - x(p.decide_by))} height={12}>
                    <title>{`${p.option}: decide by ${p.decide_by <= START ? "now" : p.decide_by}, tipping ${p.tipping_year} (${p.simulated})\nsignpost: ${p.signpost}`}</title>
                  </rect>
                ) : null}
                {p.tipping_year != null ? <circle className="tip" cx={x(p.tipping_year)} cy={y} r={4}><title>{`tipping ${p.tipping_year}: ${p.threshold}`}</title></circle> : (
                  <text x={LEFT} y={y + 4} className="muted">not crossed before {end}</text>
                )}
              </g>
            );
          })}
          <text x={LEFT} y={ROW * items.length + 18}>{START}</text>
          <text x={W - 40} y={ROW * items.length + 18}>{end}</text>
        </svg>
      ) : null}
    </Panel>
  );
}
