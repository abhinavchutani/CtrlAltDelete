// Every plan the plan finder simulated, best first, with what each one does to the money at risk.
import { useAllOptions } from "../../api/hooks";
import type { PlanCandidate } from "../../api/types";
import { liveOrder, useSearch } from "../../state/search";
import { useStore } from "../../state/store";
import { COST_LABEL, FUTURE_LABEL, planCost } from "./planMeta";

const VS = { better: "Still better", same: "About the same", worse: "Worse" } as const;

export function PlansTable({ limit }: { limit?: number }) {
  const s = useSearch();
  const options = useAllOptions();
  const send = useStore((x) => x.send);
  const climate = s.key?.split(":")[0] ?? "ssp245";
  const rows = liveOrder(s).slice(0, limit);
  // runs the plan straight away in the assistant (no extra press of send)
  const ask = (c: PlanCandidate) => send(`What if we ${c.label.charAt(0).toLowerCase()}${c.label.slice(1).replace(/ \(assumption\)/g, "")}?`, "simulate");
  if (!rows.length) return <p className="muted">No plans simulated yet.</p>;
  const others = Object.keys(FUTURE_LABEL).filter((k) => k !== climate);
  return (
    <div style={{ overflowX: "auto" }}>
      <table className="plans-table">
        <thead>
          <tr>
            <th scope="col">#</th><th scope="col">Plan</th><th scope="col">€ at risk a year</th><th scope="col">Saves</th>
            <th scope="col">Bad years</th>
            {others.map((k) => <th key={k} scope="col">{FUTURE_LABEL[k]}</th>)}
            <th scope="col">Cost</th><th />
          </tr>
        </thead>
        <tbody>
          {rows.map((c, i) => {
            const cost = planCost(c.levers, options.data);
            return (
              <tr key={c.id} className={c.id === s.best ? "best" : ""}>
                <td className="muted">{i + 1}</td>
                <td>{c.label}{c.assumption ? <span className="tag-assume">assumption</span> : null}</td>
                <td>{c.eur_at_risk_per_year}</td>
                <td style={{ color: c.saves ? "var(--leaf)" : undefined, fontWeight: c.saves ? 600 : undefined }}>
                  {c.saves ?? (c.vs_current_plan === "worse" ? "costs more" : "—")}</td>
                <td>{c.plan_costly_years} → <strong>{c.costly_years}</strong></td>
                {others.map((k) => <td key={k}>{c.futures?.[k] ? VS[c.futures[k].vs_current_plan] : <span className="muted">not re-run</span>}</td>)}
                <td className="muted">{cost ? COST_LABEL[cost] : "—"}</td>
                <td><button type="button" className="link" onClick={() => ask(c)}>Simulate it</button></td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="muted" style={{ fontSize: 14, marginTop: 12 }}>Saves = € at risk avoided a year vs today's plan, before the cost of the
        change. Bad years: seasons with €250k or more at risk. Other futures: re-simulated under the other climate paths (top plans only).</p>
    </div>
  );
}
