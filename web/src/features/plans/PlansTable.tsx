// Every plan the plan finder simulated, best first, with what each one does to the money at risk.
import { useAllOptions } from "../../api/hooks";
import type { PlanCandidate } from "../../api/types";
import { liveOrder, useSearch } from "../../state/search";
import { useStore } from "../../state/store";
import { COST_LABEL, FUTURE_LABEL, planCost } from "./planMeta";

const VS = { better: "✓", same: "≈", worse: "✗" } as const;

export function PlansTable({ limit }: { limit?: number }) {
  const s = useSearch();
  const options = useAllOptions();
  const sim = useStore((x) => x.customSpec);
  const runSpec = useStore((x) => x.runSpec);
  const climate = s.key?.split(":")[0] ?? "ssp245";
  const rows = liveOrder(s).slice(0, limit);
  const show = (c: PlanCandidate) => runSpec({ climate: climate as never, horizon_end: Number(s.key?.split(":")[1] ?? 2040) as never,
    levers: c.levers, label: c.label });
  if (!rows.length) return <p className="muted">No plans simulated yet.</p>;
  const others = Object.keys(FUTURE_LABEL).filter((k) => k !== climate);
  return (
    <div className="plans-table-wrap">
      <table className="plans-table">
        <thead>
          <tr>
            <th>#</th><th>Plan</th><th>€ at risk a year</th><th>Saves</th><th>Costly years</th><th>Worst year</th>
            {others.map((k) => <th key={k} title={`Still better than today's plan in the ${FUTURE_LABEL[k].toLowerCase()} future?`}>{FUTURE_LABEL[k]}</th>)}
            <th>Cost</th><th />
          </tr>
        </thead>
        <tbody>
          {rows.map((c, i) => {
            const cost = planCost(c.levers, options.data);
            const on = sim?.label === c.label;
            return (
              <tr key={c.id} className={`${c.id === s.best ? "best" : ""} ${on ? "on" : ""}`}>
                <td className="muted">{i + 1}</td>
                <td className="plan-cell">{c.label}{c.assumption ? <span className="tag-assume">assumption</span> : null}
                  <span className="muted small">{c.phase === "combo" ? "combined" : "single change"}</span></td>
                <td>{c.eur_at_risk_per_year}</td>
                <td className={c.saves ? "vs-better" : "muted"}>{c.saves ?? (c.vs_current_plan === "worse" ? "costs more" : "—")}</td>
                <td>{c.plan_costly_years} → <strong>{c.costly_years}</strong></td>
                <td>{c.worst_year}</td>
                {others.map((k) => <td key={k} className={`fut vs-${c.futures?.[k]?.vs_current_plan ?? ""}`}>{c.futures?.[k] ? VS[c.futures[k].vs_current_plan] : <span className="muted">·</span>}</td>)}
                <td className="muted">{cost ? COST_LABEL[cost] : "—"}</td>
                <td><button className="link-btn" onClick={() => show(c)}>Show on map</button></td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="muted small">Saves = € at risk avoided a year vs today's plan, before the cost of the change. Costly years: years with
        €250k or more at risk. Futures: re-simulated under the other climate paths (top plans only).</p>
    </div>
  );
}
