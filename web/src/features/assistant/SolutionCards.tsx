// Cited solutions in the assistant: one card per measure, its sources one click away. Every line under "Sources" is a
// verbatim quote from the named document (kb/solutions.json); nothing here is generated. Unreviewed until a person signs off.
import type { Solution } from "../../api/types";
import { useStore } from "../../state/store";

const WINDOW: Record<string, string> = { in_season: "This season", pre_season: "Before sowing", strategic: "Longer term" };
const COST: Record<string, string> = { low: "Low cost", low_med: "Low–medium cost", med: "Medium cost", high: "High cost" };
const SIMULATE: Record<string, string> = {
  irrigate: "What if we irrigate the driest pea fields?",
  earlier_sowing: "What if we sow peas earlier?",
  heat_tolerant_variety: "What if we plant a heat-tolerant pea from 2028?",
  region_split: "What if we move to a 70/30 Finland–Sweden split?",
};

export function SolutionCards({ items }: { items: Solution[] }) {
  const send = useStore((s) => s.send);
  return (
    <div className="sol-list">
      {items.map((s) => (
        <section key={s.id} className="sol" aria-label={s.title}>
          <div className="sol-top">
            <h3>{s.title}</h3>
            <span className="sol-tag" title="Not yet checked by a person">unreviewed</span>
          </div>
          <p className="sol-what">{s.what}</p>
          <div className="sol-meta">
            <span>{WINDOW[s.window] ?? s.window}</span><span>{s.lead_time}</span><span>{COST[s.cost] ?? s.cost}</span>
            {s.model_saves ? <span className="sol-model">Model: saves {s.model_saves} a year</span> : s.lever ? <span className="sol-model">In the yield model</span> : null}
          </div>
          <p className="sol-limits"><b>Watch out:</b> {s.limits}</p>
          <details className="sol-src">
            <summary>Sources ({s.evidence.length})</summary>
            <ol>
              {s.evidence.map((e, i) => (
                <li key={i}>
                  <blockquote>“{e.quote}”{e.translation ? <span className="sol-tr">{e.translation}</span> : null}</blockquote>
                  <span className="sol-cite">
                    <span className={`dot ${e.kind === "research" ? "model" : "doc"}`} aria-hidden="true" />
                    <span className="sol-kind">{e.kind === "research" ? "research" : "guide"}</span>
                    <span>{e.publisher} ({e.year}) · <a href={e.url} target="_blank" rel="noreferrer">{e.title}</a> · {e.locator}</span>
                  </span>
                </li>
              ))}
            </ol>
          </details>
          {s.lever && SIMULATE[s.lever] ? (
            <button type="button" className="followup simulate" onClick={() => send(SIMULATE[s.lever!], "simulate")}>
              Simulate it
            </button>
          ) : null}
        </section>
      ))}
    </div>
  );
}
